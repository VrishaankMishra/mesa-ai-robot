"""Per-frame feature record (DATA-001).

One :class:`FrameFeature` is the atom of the dataset: the pose, optional hands, and the
detected bottles at a single timestep, with its capture timestamp. Coordinates are stored
exactly as MediaPipe/YOLO produce them (normalized pose image space, pixel detection
boxes); no derived features are baked in — those are computed at train time so the released
data stays minimal and authentic. See ``docs/research-dataset-design.md`` §3.1.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Fixed array shapes (documented so the writer, loader, and ST-GCN adapter agree).
POSE_N_LANDMARKS = 33          # MediaPipe Pose
POSE_N_CHANNELS = 4            # x, y, z, visibility
HAND_N_LANDMARKS = 21         # MediaPipe Hands, per hand
N_HANDS = 2                   # left, right
HAND_N_CHANNELS = 3           # x, y, z
OBJECT_N_FIELDS = 6           # class_id, confidence, x1, y1, x2, y2
UNKNOWN_CLASS_ID = -1         # bottle below confidence / unrecognized


def make_objects_array(detections, k: int) -> np.ndarray:
    """Pack detections into a fixed ``(k, 6)`` array, NaN-padded to ``k`` slots.

    ``detections`` is an iterable of ``(class_id, confidence, (x1, y1, x2, y2))``. Use
    ``class_id = UNKNOWN_CLASS_ID`` for an unknown/wrong bottle. Extra detections beyond
    ``k`` are dropped (highest-confidence kept).
    """
    arr = np.full((k, OBJECT_N_FIELDS), np.nan, dtype=np.float32)
    dets = sorted(detections, key=lambda d: d[1], reverse=True)[:k]
    for i, (class_id, conf, box) in enumerate(dets):
        x1, y1, x2, y2 = box
        arr[i] = (class_id, conf, x1, y1, x2, y2)
    return arr


@dataclass
class FrameFeature:
    """Features extracted from one camera frame.

    ``pose`` is ``(33, 4)``; ``objects`` is ``(K, 6)``; ``hands`` is an optional
    ``(2, 21, 3)`` (``None`` when hand capture is off — RES-002). ``ts`` is epoch seconds.
    """

    pose: np.ndarray
    objects: np.ndarray
    ts: float
    hands: np.ndarray | None = None

    def __post_init__(self) -> None:
        self.pose = np.asarray(self.pose, dtype=np.float32)
        self.objects = np.asarray(self.objects, dtype=np.float32)
        if self.pose.shape != (POSE_N_LANDMARKS, POSE_N_CHANNELS):
            raise ValueError(
                f"pose must be {(POSE_N_LANDMARKS, POSE_N_CHANNELS)}, got {self.pose.shape}"
            )
        if self.objects.ndim != 2 or self.objects.shape[1] != OBJECT_N_FIELDS:
            raise ValueError(
                f"objects must be (K, {OBJECT_N_FIELDS}), got {self.objects.shape}"
            )
        if self.hands is not None:
            self.hands = np.asarray(self.hands, dtype=np.float32)
            if self.hands.shape != (N_HANDS, HAND_N_LANDMARKS, HAND_N_CHANNELS):
                raise ValueError(
                    f"hands must be {(N_HANDS, HAND_N_LANDMARKS, HAND_N_CHANNELS)}, "
                    f"got {self.hands.shape}"
                )
