"""Tests for the research capture layer (DATA-001 / RES-001): feature record, ring buffer,
clip I/O, and the ST-GCN adapter. Pure array work — no camera or model."""

import numpy as np
import pytest

from mesa.research.buffer import FeatureRingBuffer
from mesa.research.clip_io import clip_to_stgcn, load_clip, write_clip
from mesa.research.features import (
    HAND_N_CHANNELS,
    HAND_N_LANDMARKS,
    N_HANDS,
    OBJECT_N_FIELDS,
    POSE_N_CHANNELS,
    POSE_N_LANDMARKS,
    UNKNOWN_CLASS_ID,
    FrameFeature,
    make_objects_array,
)


def _pose(fill=0.0):
    return np.full((POSE_N_LANDMARKS, POSE_N_CHANNELS), fill, dtype=np.float32)


def _objects(k=5):
    return np.full((k, OBJECT_N_FIELDS), np.nan, dtype=np.float32)


def _frame(ts, fill=0.0, hands=False, k=5):
    h = np.zeros((N_HANDS, HAND_N_LANDMARKS, HAND_N_CHANNELS), np.float32) if hands else None
    return FrameFeature(pose=_pose(fill), objects=_objects(k), ts=ts, hands=h)


# --- FrameFeature / make_objects_array ---


def test_frame_validates_pose_shape():
    with pytest.raises(ValueError, match="pose"):
        FrameFeature(pose=np.zeros((10, 4)), objects=_objects(), ts=0.0)


def test_frame_validates_hands_shape():
    with pytest.raises(ValueError, match="hands"):
        FrameFeature(pose=_pose(), objects=_objects(), ts=0.0, hands=np.zeros((2, 5, 3)))


def test_make_objects_array_pads_and_ranks_by_confidence():
    dets = [
        (0, 0.4, (0, 0, 10, 10)),
        (1, 0.9, (5, 5, 15, 15)),
        (UNKNOWN_CLASS_ID, 0.2, (1, 1, 2, 2)),
    ]
    arr = make_objects_array(dets, k=5)
    assert arr.shape == (5, OBJECT_N_FIELDS)
    # highest confidence first
    assert arr[0, 0] == 1 and arr[0, 1] == pytest.approx(0.9)
    assert arr[2, 0] == UNKNOWN_CLASS_ID
    # unused slots are NaN
    assert np.isnan(arr[3]).all()


def test_make_objects_array_drops_beyond_k():
    dets = [(i, 0.5 + i / 100, (0, 0, 1, 1)) for i in range(8)]
    arr = make_objects_array(dets, k=3)
    assert arr.shape == (3, OBJECT_N_FIELDS)
    assert not np.isnan(arr).any()  # all 3 slots filled


# --- FeatureRingBuffer (RES-001) ---


def test_buffer_evicts_outside_window():
    buf = FeatureRingBuffer(buffer_seconds=6.0)
    for t in range(10):  # ts 0..9
        buf.append(_frame(ts=float(t)))
    # newest is 9; keep ts >= 9 - 6 = 3 -> {3,4,5,6,7,8,9} = 7 frames
    win = buf.window()
    assert [f.ts for f in win] == [3, 4, 5, 6, 7, 8, 9]
    assert buf.duration() == pytest.approx(6.0)


def test_buffer_rejects_out_of_order():
    buf = FeatureRingBuffer()
    buf.append(_frame(ts=5.0))
    with pytest.raises(ValueError, match="non-decreasing"):
        buf.append(_frame(ts=4.0))


def test_buffer_rejects_nonpositive_window():
    with pytest.raises(ValueError):
        FeatureRingBuffer(buffer_seconds=0)


# --- clip I/O ---


def test_write_and_load_roundtrip_with_t_rel(tmp_path):
    frames = [_frame(ts=100.0 + i) for i in range(4)]  # ts 100..103
    out = write_clip(tmp_path / "clip0", frames, anchor_ts=103.0, meta={"label_a": "interact"})
    assert out.suffix == ".npz" and out.exists()

    clip = load_clip(out)
    assert clip["pose"].shape == (4, POSE_N_LANDMARKS, POSE_N_CHANNELS)
    assert clip["objects"].shape == (4, 5, OBJECT_N_FIELDS)
    # t_rel is relative to anchor (103): -3, -2, -1, 0
    np.testing.assert_allclose(clip["t_rel"], [-3, -2, -1, 0])
    assert clip["meta"] == {"label_a": "interact"}
    assert "hands" not in clip  # none captured


def test_write_clip_negative_uses_last_frame_when_no_anchor(tmp_path):
    frames = [_frame(ts=10.0 + i) for i in range(3)]  # 10,11,12
    clip = load_clip(write_clip(tmp_path / "neg", frames))
    np.testing.assert_allclose(clip["t_rel"], [-2, -1, 0])


def test_write_clip_hands_all_or_nothing(tmp_path):
    frames = [_frame(ts=0.0, hands=True), _frame(ts=1.0, hands=False)]
    clip = load_clip(write_clip(tmp_path / "h", frames))
    assert clip["hands"].shape == (2, N_HANDS, HAND_N_LANDMARKS, HAND_N_CHANNELS)
    assert not np.isnan(clip["hands"][0]).any()   # first frame had hands
    assert np.isnan(clip["hands"][1]).all()       # second NaN-filled


def test_write_empty_clip_rejected(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        write_clip(tmp_path / "x", [])


# --- ST-GCN adapter ---


def test_clip_to_stgcn_shape_and_channels():
    # pose channel values: x=1, y=2, z=3, vis=4 so we can check z is dropped
    pose = np.tile([1.0, 2.0, 3.0, 4.0], (5, POSE_N_LANDMARKS, 1)).astype(np.float32)
    tensor = clip_to_stgcn({"pose": pose})
    assert tensor.shape == (3, 5, POSE_N_LANDMARKS, 1)  # (C, T, V, M)
    # channels are x, y, visibility (z dropped)
    assert tensor[0, 0, 0, 0] == 1.0
    assert tensor[1, 0, 0, 0] == 2.0
    assert tensor[2, 0, 0, 0] == 4.0


def test_clip_to_stgcn_truncates_to_recent_frames():
    pose = np.zeros((10, POSE_N_LANDMARKS, POSE_N_CHANNELS), np.float32)
    pose[:, 0, 0] = np.arange(10)  # tag each frame by index in joint0/x
    tensor = clip_to_stgcn(pose, target_frames=4)
    assert tensor.shape == (3, 4, POSE_N_LANDMARKS, 1)
    # keeps the LAST 4 frames (closest to contact): indices 6,7,8,9
    np.testing.assert_allclose(tensor[0, :, 0, 0], [6, 7, 8, 9])


def test_clip_to_stgcn_pads_front_with_zeros():
    pose = np.ones((2, POSE_N_LANDMARKS, POSE_N_CHANNELS), np.float32)
    tensor = clip_to_stgcn(pose, target_frames=5)
    assert tensor.shape == (3, 5, POSE_N_LANDMARKS, 1)
    # first 3 frames zero-padded, last 2 are the real (x=1) frames
    assert (tensor[0, :3, 0, 0] == 0).all()
    assert (tensor[0, 3:, 0, 0] == 1).all()
