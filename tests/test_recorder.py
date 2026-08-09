"""Tests for the live research recorder wiring (DATA-002)."""

import numpy as np

from mesa.data.database import Database
from mesa.engine.presence import TakenEvent
from mesa.research.clip_io import load_clip
from mesa.research.features import UNKNOWN_CLASS_ID
from mesa.research.recorder import (
    ResearchRecorder,
    detections_to_tuples,
    pose_array_from_landmarks,
)
from mesa.vision.detector import Detection


class FakeLm:
    def __init__(self, x):
        self.x = x
        self.y = x + 0.1
        self.z = 0.0
        self.visibility = 0.9


class FakeLandmarkList:
    def __init__(self):
        self.landmark = [FakeLm(i / 100) for i in range(33)]


def make_recorder(tmp_path):
    db = Database(":memory:")
    return ResearchRecorder(db, clips_dir=tmp_path, buffer_seconds=6.0, max_bottles=3), db


def test_pose_array_shapes_and_nan_fallback():
    arr = pose_array_from_landmarks(FakeLandmarkList())
    assert arr.shape == (33, 4) and arr.dtype == np.float32
    assert abs(arr[10, 0] - 0.10) < 1e-6
    nan = pose_array_from_landmarks(None)
    assert nan.shape == (33, 4) and np.isnan(nan).all()


def test_detection_label_mapping_and_unknown():
    name_to_id = {"advil": 0, "mylanta": 5}
    dets = [Detection("advil", 0.9, (1, 2, 3, 4)), Detection("unknown", 0.3, (5, 6, 7, 8))]
    tuples = detections_to_tuples(dets, name_to_id)
    assert tuples[0][0] == 0
    assert tuples[1][0] == UNKNOWN_CLASS_ID


def test_taken_event_writes_labeled_clip_and_catalog_row(tmp_path):
    rec, db = make_recorder(tmp_path)
    rec.set_class_names({0: "advil"})
    rec.on_detections([Detection("advil", 0.8, (10, 10, 50, 90))])
    for i in range(20):
        rec.on_frame(FakeLandmarkList(), ts=100.0 + i * 0.25)  # 5s of frames

    path = rec.on_taken(TakenEvent(med_name="advil", absent_seconds=12.0, ts=105.0))
    assert path is not None and path.exists()

    clip = load_clip(path)
    assert clip["pose"].shape == (20, 33, 4)
    assert clip["objects"].shape == (20, 3, 6)
    assert clip["meta"]["med_name"] == "advil"
    # t_rel anchored at the event: last frame (ts 104.75) is just before contact.
    assert clip["t_rel"][-1] < 0 <= clip["t_rel"][-1] + 0.5

    rows = db.conn.execute("SELECT label_a, label_b, n_frames FROM clips").fetchall()
    assert len(rows) == 1
    assert rows[0]["label_a"] == "interact" and rows[0]["label_b"] == "advil"
    assert rows[0]["n_frames"] == 20
    assert rec.clips_written == 1


def test_empty_buffer_writes_nothing(tmp_path):
    rec, db = make_recorder(tmp_path)
    assert rec.on_taken(TakenEvent(med_name="advil", absent_seconds=11.0, ts=50.0)) is None
    assert db.conn.execute("SELECT COUNT(*) c FROM clips").fetchone()["c"] == 0


def test_buffer_evicts_beyond_window(tmp_path):
    rec, _ = make_recorder(tmp_path)
    for i in range(100):
        rec.on_frame(None, ts=i * 0.5)  # 50s of frames, 6s buffer
    assert rec.buffer.duration() <= 6.0
