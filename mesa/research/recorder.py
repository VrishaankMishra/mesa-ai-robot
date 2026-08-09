"""Live research recorder (DATA-002 wiring) — the missing middle of the capture layer.

Connects the June-built pieces to the live pipeline: the vision worker feeds one
:class:`FrameFeature` per frame into the ring buffer; when the decision engine's
compliance tracker fires a ``taken`` event, the recorder snapshots the pre-event window,
writes it as a compressed ``.npz`` clip, and catalogs it in SQLite (``clips`` row,
``label_a='interact'``). Every real medication pickup thereby labels its own preceding
seconds of pose — the self-labeling dataset of docs/research-dataset-design.md.

Privacy: features only (pose landmarks + detection boxes). No pixels are ever stored.

Pure logic (feature assembly, label mapping) is unit-tested; only the wall-clock-free
paths live here so tests use synthetic timestamps.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from mesa.data.database import Database
from mesa.research.buffer import FeatureRingBuffer
from mesa.research.clip_io import write_clip
from mesa.research.features import (
    POSE_N_CHANNELS,
    POSE_N_LANDMARKS,
    UNKNOWN_CLASS_ID,
    FrameFeature,
    make_objects_array,
)

NAN_POSE = np.full((POSE_N_LANDMARKS, POSE_N_CHANNELS), np.nan, dtype=np.float32)


def pose_array_from_landmarks(landmark_list) -> np.ndarray:
    """MediaPipe 33-landmark list -> (33, 4) float32 [x, y, z, visibility].

    ``None`` (no person / fallback path without full landmarks) -> NaN array, so the
    clip timeline stays dense and dropouts are explicit in the data.
    """
    if landmark_list is None:
        return NAN_POSE.copy()
    lm = landmark_list.landmark
    return np.array([[p.x, p.y, p.z, p.visibility] for p in lm], dtype=np.float32)


def detections_to_tuples(detections, name_to_id: dict[str, int]):
    """mesa Detection objects -> (class_id, conf, box) tuples for make_objects_array.

    Unknown/wrong-medication detections map to ``UNKNOWN_CLASS_ID``.
    """
    out = []
    for d in detections:
        cid = name_to_id.get(d.label, UNKNOWN_CLASS_ID)
        out.append((cid, d.confidence, d.box))
    return out


class ResearchRecorder:
    """Owns the ring buffer, clip files, and catalog rows for one live run."""

    def __init__(
        self,
        db: Database,
        clips_dir: str | Path = "data/clips",
        buffer_seconds: float = 6.0,
        max_bottles: int = 5,
        participant: str = "household",
    ):
        self.db = db
        self.clips_dir = Path(clips_dir)
        self.max_bottles = max_bottles
        self.buffer = FeatureRingBuffer(buffer_seconds=buffer_seconds)
        self._last_detections: list = []
        self._name_to_id: dict[str, int] = {}
        self.session_id = db.create_session(
            tier=1, participant=participant, consent_flag=True,
            consent_version="household-v1",
        )
        self.clips_written = 0

    def set_class_names(self, names: dict[int, str]) -> None:
        """Give the recorder the detector's class map (id -> name) once it's loaded."""
        self._name_to_id = {v: k for k, v in names.items()}

    def on_detections(self, detections) -> None:
        """Latest YOLO detections (runs every Nth frame; reused for frames between)."""
        self._last_detections = list(detections)

    def on_frame(self, landmark_list, ts: float) -> None:
        """One camera frame's features into the ring buffer."""
        frame = FrameFeature(
            pose=pose_array_from_landmarks(landmark_list),
            objects=make_objects_array(
                detections_to_tuples(self._last_detections, self._name_to_id),
                self.max_bottles,
            ),
            ts=ts,
        )
        self.buffer.append(frame)

    def on_taken(self, event) -> Path | None:
        """Compliance fired a taken event: write the pre-event window as a clip."""
        frames = self.buffer.window()
        if not frames:
            return None
        anchor = getattr(event, "ts", None) or frames[-1].ts
        med = getattr(event, "med_name", "unknown")
        fname = f"clip_{int(anchor)}_{med}.npz"
        path = write_clip(
            self.clips_dir / fname, frames, anchor_ts=anchor,
            meta={"med_name": med,
                  "absent_seconds": float(getattr(event, "absent_seconds", 0.0)),
                  "session_id": self.session_id},
        )
        self.db.add_clip(
            session_id=self.session_id, path=str(path),
            window_seconds=self.buffer.buffer_seconds, n_frames=len(frames),
            label_a="interact", label_b=med, anchor_ts=anchor,
        )
        self.clips_written += 1
        return path

    def close(self) -> None:
        self.db.end_session(self.session_id, ended_at=time.time())
