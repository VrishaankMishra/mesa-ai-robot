"""MediaPipe Pose wrapper with rotation fallback (VIS-009 robustness).

MediaPipe Pose is trained predominantly on upright bodies and regularly loses a lying
person outright — live testing (Jul 18) showed a person vanishing 1.5 s after lying down
and never being re-found, so the fall timer could not accumulate. The fix, measured on real
failing frames (Jul 18 experiment on the Pi): the heavy model (complexity 2) in static
mode DOES find the lying person in the original orientation, and a 180° rotation (which
preserves horizontal bodies) is the next-best signal; ±90° rotations map an upright
reading back to LYING. So when the fast primary pass finds nobody, we run a
complexity-2 static fallback on the original frame, then rotations.

The heavy inference runs only on frames where the primary already failed — exactly the
lying/absent frames, where FPS matters least. A separate Pose instance serves the
fallback so its static mode and orientations don't pollute the primary tracker.

The orientation-mapping logic is pure and unit-tested; :class:`PoseEstimator` is
camera/model glue (imports mediapipe lazily, not unit-tested).
"""

from __future__ import annotations

from dataclasses import dataclass

from mesa.vision.posture import Posture, classify_posture

# MediaPipe Pose landmark indices -> our names (single source of truth).
LANDMARK_IDS = {
    "left_shoulder": 11, "right_shoulder": 12,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}


def posture_from_rotated(rotated: Posture) -> Posture:
    """Map a posture classified in a ±90°-rotated frame back to the real frame.

    Upright-in-rotated (standing, or sitting = torso upright with bent knees) means
    horizontal-in-reality => LYING. A "lying" reading in the rotated frame would mean
    the person is actually upright — but then the primary pass should have found them,
    so treat that (and unknown) as UNKNOWN rather than guessing.
    """
    if rotated in (Posture.STANDING, Posture.SITTING):
        return Posture.LYING
    return Posture.UNKNOWN


def posture_from_180(rotated: Posture) -> Posture:
    """Map a posture classified in a 180°-rotated frame back to the real frame.

    A 180° rotation flips both axes, so horizontal stays horizontal: LYING is trusted.
    "Standing" in a 180° frame would be an upside-down person — implausible; UNKNOWN.
    """
    return Posture.LYING if rotated == Posture.LYING else Posture.UNKNOWN


def extract_named_landmarks(landmark_list):
    """MediaPipe landmark list -> ({name: (x, y)}, {name: visibility})."""
    lm = landmark_list.landmark
    points = {name: (lm[i].x, lm[i].y) for name, i in LANDMARK_IDS.items()}
    vis = {name: lm[i].visibility for name, i in LANDMARK_IDS.items()}
    return points, vis


@dataclass
class PoseReading:
    posture: Posture
    person_present: bool
    via_fallback: bool = False
    raw_result: object = None  # primary-pass mediapipe result (for drawing overlays)


class PoseEstimator:  # pragma: no cover - mediapipe/hardware glue
    def __init__(self, model_complexity: int = 1, min_visibility: float = 0.5,
                 rotation_fallback: bool = True):
        import cv2
        import mediapipe as mp

        self._cv2 = cv2
        self._mp = mp
        self.min_visibility = min_visibility
        self.rotation_fallback = rotation_fallback
        self._pose = mp.solutions.pose.Pose(model_complexity=model_complexity)
        # Fallback: heavy model, static mode, default confidence — the measured best
        # config for lying bodies (complexity 2 finds them where 1 cannot; lowering
        # min_detection_confidence made detection WORSE in the same experiment).
        self._pose_fallback = (
            mp.solutions.pose.Pose(model_complexity=2, static_image_mode=True)
            if rotation_fallback else None
        )

    def infer(self, frame_bgr) -> PoseReading:
        cv2 = self._cv2
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        result = self._pose.process(rgb)
        if result.pose_landmarks:
            points, vis = extract_named_landmarks(result.pose_landmarks)
            posture = classify_posture(points, visibility=vis,
                                       min_visibility=self.min_visibility)
            return PoseReading(posture, True, raw_result=result)

        if self._pose_fallback is not None:
            # Heavy pass on the original orientation first — the highest-yield config.
            r = self._pose_fallback.process(rgb)
            if r.pose_landmarks:
                points, vis = extract_named_landmarks(r.pose_landmarks)
                posture = classify_posture(points, visibility=vis,
                                           min_visibility=self.min_visibility)
                return PoseReading(posture, True, via_fallback=True)

            for rot, mapper in ((cv2.ROTATE_180, posture_from_180),
                                (cv2.ROTATE_90_CLOCKWISE, posture_from_rotated),
                                (cv2.ROTATE_90_COUNTERCLOCKWISE, posture_from_rotated)):
                r = self._pose_fallback.process(cv2.rotate(rgb, rot))
                if r.pose_landmarks:
                    points, vis = extract_named_landmarks(r.pose_landmarks)
                    rotated = classify_posture(points, visibility=vis,
                                               min_visibility=self.min_visibility)
                    return PoseReading(mapper(rotated), True, via_fallback=True)

        return PoseReading(Posture.UNKNOWN, False)

    def close(self) -> None:
        self._pose.close()
        if self._pose_fallback is not None:
            self._pose_fallback.close()
