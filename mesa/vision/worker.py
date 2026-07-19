"""Live vision worker thread (ENG-004).

Owns the camera and publishes onto the :class:`~mesa.engine.events.EventBus`:

- ``POSTURE`` every frame — MediaPipe Pose → :func:`classify_posture` → smoothed label.
- ``BOTTLE_OBSERVATION`` every Nth frame (``vision.detection_every_n_frames``) — YOLO
  detections turned into a per-medication present/absent map. Only runs when a trained
  model file exists, so the posture/FALL path works before MED training is done.
- ``PRESENCE_CHECK`` at ~1 Hz — whether a person (any pose landmarks) is in frame,
  feeding the inactivity monitor.

The camera/MediaPipe loop is hardware-bound glue (not unit-tested, same convention as
``scripts/pose_live.py``); the detection→presence mapping is a pure function with tests.
"""

from __future__ import annotations

import threading
import time

from mesa.config import get
from mesa.engine.events import (
    BOTTLE_OBSERVATION,
    POSTURE,
    PRESENCE_CHECK,
    Event,
    EventBus,
)
from mesa.vision.detector import Detection, YOLODetector
from mesa.vision.posture import PostureSmoother


def presence_map(detections: list[Detection], known_meds: set[str]) -> dict[str, bool]:
    """Turn one detection pass into a present/absent reading for every known med.

    A med is present iff a confident (non-"unknown") detection carries its label; every
    known med missing from the frame reads absent, which is what lets the compliance
    tracker see a bottle being picked up. Unknown-label boxes are ignored here — they are
    the "wrong medication" path, not evidence about a known bottle.
    """
    seen = {d.label for d in detections if not d.is_unknown}
    return {med: (med in seen) for med in known_meds}


class VisionWorker(threading.Thread):
    """Camera → pose + detection → events. Start with ``.start()``, stop with ``.stop()``."""

    def __init__(self, bus: EventBus, cfg: dict, known_meds: set[str] | None = None,
                 model_available: bool = True, capture=None):
        super().__init__(name="vision-worker", daemon=True)
        self.bus = bus
        self.cfg = cfg
        self.known_meds = set(known_meds or ())
        self.model_available = model_available
        # macOS can only show the camera-permission dialog from the main thread, so the
        # caller may open the capture there and pass it in; on Linux/Pi it's fine to let
        # the worker open its own.
        self.capture = capture
        self._stop = threading.Event()

        self.camera_index = get(cfg, "vision.camera_index", 0)
        self.frame_width = get(cfg, "vision.frame_width", 640)
        self.frame_height = get(cfg, "vision.frame_height", 480)
        self.detect_every = max(1, get(cfg, "vision.detection_every_n_frames", 3))
        self.presence_interval = get(cfg, "vision.presence_check_seconds", 1.0)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # pragma: no cover - camera + MediaPipe hardware loop
        import cv2

        from mesa.vision.pose_estimator import PoseEstimator

        estimator = PoseEstimator(
            model_complexity=get(self.cfg, "pose.model_complexity", 1),
            min_visibility=get(self.cfg, "pose.min_landmark_visibility", 0.5),
        )
        smoother = PostureSmoother(window=get(self.cfg, "pose.smoothing_window", 15))

        detector: YOLODetector | None = None
        if self.model_available:
            detector = YOLODetector(
                get(self.cfg, "detection.model_path", "models/best.pt"),
                conf_threshold=get(self.cfg, "detection.confidence_threshold", 0.5),
            )

        cap = self.capture
        if cap is None:
            cap = cv2.VideoCapture(self.camera_index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
        if not cap.isOpened():
            raise RuntimeError(f"vision worker: could not open camera {self.camera_index}")

        frame_no = 0
        last_presence_ts = 0.0
        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue
                frame_no += 1
                now = time.time()

                reading = estimator.infer(frame)
                person_present = reading.person_present
                self.bus.publish(
                    Event(POSTURE, {"posture": smoother.update(reading.posture)}, ts=now)
                )

                if now - last_presence_ts >= self.presence_interval:
                    last_presence_ts = now
                    self.bus.publish(
                        Event(PRESENCE_CHECK, {"person_present": person_present}, ts=now)
                    )

                if detector is not None and frame_no % self.detect_every == 0:
                    detections = detector.detect(frame)
                    if not self.known_meds:
                        # No meds configured in the DB: fall back to the model's classes.
                        self.known_meds = set(detector.names.values())
                    for med, present in presence_map(detections, self.known_meds).items():
                        self.bus.publish(
                            Event(BOTTLE_OBSERVATION,
                                  {"med_name": med, "present": present}, ts=now)
                        )
        finally:
            cap.release()
            estimator.close()
