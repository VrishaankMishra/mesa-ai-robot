"""Clip serialization + ST-GCN adapter (RES-001 / RES-003).

A clip is one labeled pre-event window: the stacked per-frame features written to a single
compressed ``.npz``. The SQLite ``clips`` row (see ``mesa.data.database``) is the catalog
entry that points at the file; this module owns the file format itself.

:func:`write_clip` stacks a list of :class:`~mesa.research.features.FrameFeature` and
computes ``t_rel`` (seconds relative to the anchor event). :func:`load_clip` reads it back.
:func:`clip_to_stgcn` reshapes the pose stream into ST-GCN's ``(C, T, V, M)`` tensor.
See ``docs/research-dataset-design.md`` §3 and §5.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mesa.research.features import (
    HAND_N_CHANNELS,
    HAND_N_LANDMARKS,
    N_HANDS,
    FrameFeature,
)


def write_clip(
    path: str | Path,
    frames: list[FrameFeature],
    anchor_ts: float | None = None,
    meta: dict | None = None,
) -> Path:
    """Stack ``frames`` and save one ``.npz`` clip; returns the written path.

    ``t_rel`` is each frame's time relative to ``anchor_ts`` (the ``taken`` event), so it is
    ``0`` at contact and negative before. If ``anchor_ts`` is ``None`` (a negative clip with
    no event), ``t_rel`` is measured from the last frame. ``meta`` is stored as JSON so the
    file is self-describing when packaged for release.
    """
    if not frames:
        raise ValueError("cannot write an empty clip")

    pose = np.stack([f.pose for f in frames])              # (T, 33, 4)
    objects = np.stack([f.objects for f in frames])        # (T, K, 6)
    frame_ts = np.array([f.ts for f in frames], dtype=np.float64)  # (T,)
    anchor = frame_ts[-1] if anchor_ts is None else anchor_ts
    t_rel = (frame_ts - anchor).astype(np.float32)

    arrays: dict[str, np.ndarray] = {
        "pose": pose,
        "objects": objects,
        "frame_ts": frame_ts,
        "t_rel": t_rel,
    }
    # Hands are all-or-nothing per clip: if any frame has them, NaN-fill the rest.
    if any(f.hands is not None for f in frames):
        nan_hand = np.full((N_HANDS, HAND_N_LANDMARKS, HAND_N_CHANNELS), np.nan, np.float32)
        arrays["hands"] = np.stack([f.hands if f.hands is not None else nan_hand for f in frames])

    arrays["meta"] = np.array(json.dumps(meta or {}))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    # numpy appends .npz if the path has no suffix; normalize the returned path to match.
    return path if path.suffix == ".npz" else path.with_suffix(".npz")


def load_clip(path: str | Path) -> dict:
    """Load a clip ``.npz`` into a dict of arrays, with ``meta`` parsed back to a dict."""
    with np.load(path, allow_pickle=False) as npz:
        out = {k: npz[k] for k in npz.files}
    if "meta" in out:
        out["meta"] = json.loads(str(out["meta"]))
    return out


def clip_to_stgcn(clip: dict | np.ndarray, target_frames: int | None = None) -> np.ndarray:
    """Reshape a clip's pose stream into ST-GCN input ``(C=3, T, V=33, M=1)``.

    Channels are ``(x, y, visibility)`` — the ``z`` channel is dropped, matching ST-GCN's
    use of a per-joint confidence as the third channel. Accepts either a loaded clip dict or
    a raw ``(T, 33, 4)`` pose array. If ``target_frames`` is given, ``T`` is padded
    (zero) or truncated (keep the most recent frames — the moments closest to contact).
    """
    pose = clip["pose"] if isinstance(clip, dict) else clip   # (T, 33, 4)
    pose = np.asarray(pose, dtype=np.float32)
    xy_vis = pose[:, :, [0, 1, 3]]                            # (T, 33, 3)

    if target_frames is not None:
        xy_vis = _fit_frames(xy_vis, target_frames)

    tensor = np.transpose(xy_vis, (2, 0, 1))                  # (3, T, 33)
    return tensor[:, :, :, np.newaxis]                        # (3, T, 33, 1)


def _fit_frames(xy_vis: np.ndarray, target: int) -> np.ndarray:
    """Pad with zero-frames at the front, or keep the last ``target`` frames."""
    t = xy_vis.shape[0]
    if t == target:
        return xy_vis
    if t > target:
        return xy_vis[-target:]
    pad = np.zeros((target - t, *xy_vis.shape[1:]), dtype=xy_vis.dtype)
    return np.concatenate([pad, xy_vis], axis=0)
