"""Medication bottle detection (VIS-006).

The heavy YOLO model is loaded lazily so this module imports without ultralytics/torch
installed (keeps laptop tests light). The *decision* logic — turning raw model output into
labelled detections and flagging low-confidence boxes as "unknown / wrong medication" — is
kept as pure functions so it can be unit-tested without a model or camera.
"""

from __future__ import annotations

from dataclasses import dataclass

UNKNOWN_LABEL = "unknown"


@dataclass(frozen=True)
class Detection:
    """One detected bottle. ``label`` is ``"unknown"`` when below the confidence threshold."""

    label: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2

    @property
    def is_unknown(self) -> bool:
        return self.label == UNKNOWN_LABEL


def classify_detections(
    raw: list[tuple[int, float, tuple[int, int, int, int]]],
    names: dict[int, str] | list[str],
    conf_threshold: float,
) -> list[Detection]:
    """Convert raw ``(class_id, confidence, box)`` tuples into :class:`Detection` objects.

    Any detection with ``confidence < conf_threshold`` — or an out-of-range class id — is
    labelled ``"unknown"`` so the engine can announce "wrong medication" (MED-DEMO).
    """
    detections: list[Detection] = []
    for class_id, confidence, box in raw:
        if confidence < conf_threshold or not _has_index(names, class_id):
            label = UNKNOWN_LABEL
        else:
            label = names[class_id]
        detections.append(Detection(label=label, confidence=float(confidence), box=box))
    return detections


def _has_index(names: dict[int, str] | list[str], class_id: int) -> bool:
    if isinstance(names, dict):
        return class_id in names
    return 0 <= class_id < len(names)


class YOLODetector:
    """Thin wrapper around an Ultralytics YOLO model. Imports ultralytics lazily."""

    def __init__(self, model_path: str, conf_threshold: float = 0.5):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._model = None  # loaded on first use

    def _ensure_model(self):
        if self._model is None:
            from ultralytics import YOLO  # lazy import

            self._model = YOLO(self.model_path)
        return self._model

    @property
    def names(self) -> dict[int, str]:
        return self._ensure_model().names

    def detect(self, frame) -> list[Detection]:
        """Run inference on a single BGR frame and return classified detections."""
        model = self._ensure_model()
        # conf=0 so low-confidence boxes still surface and get flagged "unknown" by us.
        results = model.predict(frame, conf=0.01, verbose=False)
        raw: list[tuple[int, float, tuple[int, int, int, int]]] = []
        for r in results:
            for b in r.boxes:
                cls = int(b.cls[0])
                conf = float(b.conf[0])
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                raw.append((cls, conf, (x1, y1, x2, y2)))
        return classify_detections(raw, model.names, self.conf_threshold)
