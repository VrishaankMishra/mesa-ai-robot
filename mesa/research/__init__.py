"""Research extension: pre-event feature capture for intent prediction.

This package is the thin layer that turns a MeSA run into a dataset (DATA-001 / RES-001).
It is import-isolated from the build: nothing here is imported unless ``research.enabled``
is set, and it depends only on numpy (a declared dependency), never on a camera or model.

- :mod:`mesa.research.features` — the per-frame feature record + array shapes.
- :mod:`mesa.research.buffer` — a rolling pre-event ring buffer (RES-001).
- :mod:`mesa.research.clip_io` — ``.npz`` clip read/write + the ST-GCN adapter.

See ``docs/research-dataset-design.md`` for the authoritative schema.
"""

from mesa.research.features import (
    HAND_N_CHANNELS,
    HAND_N_LANDMARKS,
    N_HANDS,
    OBJECT_N_FIELDS,
    POSE_N_CHANNELS,
    POSE_N_LANDMARKS,
    FrameFeature,
    make_objects_array,
)

__all__ = [
    "FrameFeature",
    "make_objects_array",
    "POSE_N_LANDMARKS",
    "POSE_N_CHANNELS",
    "HAND_N_LANDMARKS",
    "HAND_N_CHANNELS",
    "N_HANDS",
    "OBJECT_N_FIELDS",
]
