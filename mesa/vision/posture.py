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


def classify_posture(landmarks: Landmarks) -> Posture:
    """Classify posture from named landmarks.

    Expected names (any subset; more enables finer classification):
    left/right_shoulder, left/right_hip, left/right_knee, left/right_ankle.
    """
    if not _have(landmarks, "left_shoulder", "right_shoulder", "left_hip", "right_hip"):
        return Posture.UNKNOWN

    shoulder = _midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
    hip = _midpoint(landmarks["left_hip"], landmarks["right_hip"])

    # Lying: torso is more horizontal than vertical.
    if _angle_from_vertical(shoulder, hip) > LYING_TORSO_ANGLE_DEG:
        return Posture.LYING

    # Upright: use knee bend to separate sitting from standing (if legs are visible).
    if _have(landmarks, "left_hip", "left_knee", "left_ankle"):
        knee_angle = _joint_angle(landmarks["left_hip"], landmarks["left_knee"], landmarks["left_ankle"])
    elif _have(landmarks, "right_hip", "right_knee", "right_ankle"):
        knee_angle = _joint_angle(landmarks["right_hip"], landmarks["right_knee"], landmarks["right_ankle"])
    else:
        return Posture.STANDING  # upright torso, legs not visible -> assume standing

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
