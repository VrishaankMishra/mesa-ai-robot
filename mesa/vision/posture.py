"""Posture classification + fall trigger (VIS-009 / VIS-010).

Classifies standing / sitting / lying from pose keypoints using simple geometry — torso
angle from vertical, plus knee bend to separate standing from sitting. All pure functions
on (x, y) landmark coordinates (MediaPipe's normalized image space, y increasing
*downward*), so it's fully unit-testable without a camera or MediaPipe.

:class:`PostureMonitor` watches for a sustained lying posture and fires a ``possible_fall``
once lying exceeds the configured duration (VIS-010). Time is injected, so it's testable.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum

Point = tuple[float, float]
Landmarks = dict[str, Point]

# Thresholds (tunable; mirror config.yaml where relevant).
LYING_TORSO_ANGLE_DEG = 50.0   # torso more horizontal than this => lying
SITTING_KNEE_ANGLE_DEG = 130.0  # knee bent more than this (smaller angle) => sitting


class Posture(Enum):
    STANDING = "standing"
    SITTING = "sitting"
    LYING = "lying"
    UNKNOWN = "unknown"


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _angle_from_vertical(top: Point, bottom: Point) -> float:
    """Angle (deg) between the top->bottom segment and the vertical axis. 0=vertical."""
    dx = bottom[0] - top[0]
    dy = bottom[1] - top[1]
    return math.degrees(math.atan2(abs(dx), abs(dy) + 1e-9))


def _joint_angle(a: Point, vertex: Point, c: Point) -> float:
    """Interior angle (deg) at ``vertex`` formed by points a-vertex-c."""
    v1 = (a[0] - vertex[0], a[1] - vertex[1])
    v2 = (c[0] - vertex[0], c[1] - vertex[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 180.0
    cos = max(-1.0, min(1.0, dot / (n1 * n2)))
    return math.degrees(math.acos(cos))


def _have(landmarks: Landmarks, *names: str) -> bool:
    return all(n in landmarks and landmarks[n] is not None for n in names)


def classify_posture(
    landmarks: Landmarks,
    visibility: dict[str, float] | None = None,
    min_visibility: float = 0.5,
) -> Posture:
    """Classify posture from named landmarks.

    Expected names (any subset; more enables finer classification):
    left/right_shoulder, left/right_hip, left/right_knee, left/right_ankle.

    If ``visibility`` (per-landmark confidence in 0..1, e.g. MediaPipe's
    ``landmark.visibility``) is supplied, leg landmarks below ``min_visibility``
    are treated as *not seen* — so an off-screen leg whose position MediaPipe is
    merely guessing can't fabricate a bogus knee angle (and thus a false
    "sitting"). With legs unavailable we fall back to torso-only (=> standing
    when upright). Omitting ``visibility`` keeps the original behaviour.
    """
    if not _have(landmarks, "left_shoulder", "right_shoulder", "left_hip", "right_hip"):
        return Posture.UNKNOWN

    shoulder = _midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
    hip = _midpoint(landmarks["left_hip"], landmarks["right_hip"])

    # Lying: torso is more horizontal than vertical.
    if _angle_from_vertical(shoulder, hip) > LYING_TORSO_ANGLE_DEG:
        return Posture.LYING

    def _leg_usable(side: str) -> bool:
        if not _have(landmarks, f"{side}_hip", f"{side}_knee", f"{side}_ankle"):
            return False
        if visibility is not None and (
            visibility.get(f"{side}_knee", 0.0) < min_visibility
            or visibility.get(f"{side}_ankle", 0.0) < min_visibility
        ):
            return False
        return True

    # Upright: use knee bend to separate sitting from standing (only if a leg is
    # actually visible; otherwise we can't tell, so assume standing).
    if _leg_usable("left"):
        knee_angle = _joint_angle(landmarks["left_hip"], landmarks["left_knee"], landmarks["left_ankle"])
    elif _leg_usable("right"):
        knee_angle = _joint_angle(landmarks["right_hip"], landmarks["right_knee"], landmarks["right_ankle"])
    else:
        return Posture.STANDING  # upright torso, legs not reliably visible

    return Posture.SITTING if knee_angle < SITTING_KNEE_ANGLE_DEG else Posture.STANDING


@dataclass(frozen=True)
class FallEvent:
    lying_seconds: float
    ts: float


class PostureMonitor:
    """Fires a possible_fall once a continuous lying spell exceeds the threshold (VIS-010)."""

    def __init__(self, lying_trigger_seconds: float = 30.0):
        self.lying_trigger_seconds = lying_trigger_seconds
        self._lying_since: float | None = None
        self._fired = False

    def update(self, posture: Posture, now: float) -> FallEvent | None:
        if posture != Posture.LYING:
            self._lying_since = None
            self._fired = False
            return None
        if self._lying_since is None:
            self._lying_since = now
        elapsed = now - self._lying_since
        if not self._fired and elapsed >= self.lying_trigger_seconds:
            self._fired = True
            return FallEvent(lying_seconds=elapsed, ts=now)
        return None


class PostureSmoother:
    """Stabilizes noisy per-frame postures via a sliding-window majority vote.

    :func:`classify_posture` runs independently per frame, so near a decision
    boundary (e.g. a knee angle hovering at the sitting/standing threshold, or a
    momentary mis-detection) the raw label chatters many times a second. Feeding
    that flicker straight into :class:`PostureMonitor` would keep resetting the
    lying timer, so the fall check-in could never accumulate.

    This holds the last ``window`` raw labels and only changes the reported
    posture when a strict majority of that window agrees. A single stray frame
    (or a brief lying spike) can't flip it, and once the person is genuinely in a
    posture for ~half the window it locks on. Pure/stateful and time-free, so the
    caller feeds it whatever cadence it runs at.
    """

    def __init__(self, window: int = 15, switch_fraction: float = 0.6):
        if window < 1:
            raise ValueError("window must be >= 1")
        if not 0.5 < switch_fraction <= 1.0:
            raise ValueError("switch_fraction must be in (0.5, 1.0]")
        self.window = window
        self.switch_fraction = switch_fraction
        self._buf: deque[Posture] = deque(maxlen=window)
        self._current = Posture.UNKNOWN

    def update(self, raw: Posture) -> Posture:
        """Add a raw per-frame posture, return the current smoothed posture."""
        self._buf.append(raw)
        winner, count = Counter(self._buf).most_common(1)[0]
        # Hysteresis: only leave the current posture when a *super*-majority of
        # the recent window agrees on a new one. At a ~50/50 boundary neither
        # side clears the bar, so the label holds steady instead of chattering.
        # max(2, ...) also stops a single frame from flipping it on startup.
        need = max(2, math.ceil(self.switch_fraction * len(self._buf)))
        if winner != self._current and count >= need:
            self._current = winner
        return self._current

    @property
    def current(self) -> Posture:
        return self._current

    def reset(self) -> None:
        self._buf.clear()
        self._current = Posture.UNKNOWN
