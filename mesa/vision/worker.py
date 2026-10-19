"""Live vision worker thread (ENG-004).

Owns the camera and publishes onto the :class:`~mesa.engine.events.EventBus`:

- ``POSTURE`` every frame — MediaPipe Pose → :func:`classify_posture` → smoothed label.
- ``BOTTLE_OBSERVATION`` every Nth frame (``vision.detection_every_n_frames``) — YOLO
  detections turned into a per-medication present/absent map. Only runs when a trained
  model file exists, so the posture/FALL path works before MED training is done.
- ``PRESENCE_CHECK`` at ~1 Hz — whether a person (any pose landmarks) is in frame,
  feeding the inactivity monitor.
- ``UNKNOWN_MEDICATION`` — an "unknown"-label box has sat in view, not overlapping any
  known bottle, for ``detection.unknown_debounce_seconds``; repeated at most once per
  ``detection.unknown_repeat_seconds`` while it stays (the "wrong medication" path).

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
    UNKNOWN_MEDICATION,
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


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)


def unknown_boxes(detections: list[Detection], iou_threshold: float = 0.5) -> list[Detection]:
    """Unknown-label boxes that are not just a second reading of a known bottle.

    YOLO's class-aware NMS can return two boxes for one bottle — the right class above
    threshold plus a weaker guess that gets labelled "unknown". An unknown box that
    overlaps a known detection (IoU >= ``iou_threshold``) is that case, not a foreign
    bottle, so it is dropped. What remains is evidence of a bottle MeSA does not know.
    """
    known = [d for d in detections if not d.is_unknown]
    return [
        d for d in detections
        if d.is_unknown and not any(_iou(d.box, k.box) >= iou_threshold for k in known)
    ]


class UnknownBottleGate:
    """Debounce + rate-limit for the "wrong medication" announcement.

    Pure with respect to time (the caller passes ``now``), like :class:`BottleTracker`.
    :meth:`update` returns True when an ``UNKNOWN_MEDICATION`` event should be published:
    an unknown box has been seen continuously for ``debounce_seconds`` (a hand passing
    over a bottle flickers for less than that and resets the clock), and nothing has been
    announced in the last ``repeat_seconds``.
    """

    def __init__(self, debounce_seconds: float = 3.0, repeat_seconds: float = 30.0):
        self.debounce_seconds = debounce_seconds
        self.repeat_seconds = repeat_seconds
        self._unknown_since: float | None = None
        self._last_fired: float | None = None

    def update(self, unknown_seen: bool, now: float) -> bool:
        if not unknown_seen:
            self._unknown_since = None
            return False
        if self._unknown_since is None:
            self._unknown_since = now
        if now - self._unknown_since < self.debounce_seconds:
            return False
        if self._last_fired is not None and now - self._last_fired < self.repeat_seconds:
            return False
        self._last_fired = now
        return True


class VisionWorker(threading.Thread):
    """Camera → pose + detection → events. Start with ``.start()``, stop with ``.stop()``."""

    def __init__(self, bus: EventBus, cfg: dict, known_meds: set[str] | None = None,
                 model_available: bool = True, capture=None, recorder=None):
        super().__init__(name="vision-worker", daemon=True)
        self.bus = bus
        self.cfg = cfg
        self.known_meds = set(known_meds or ())
        self.model_available = model_available
        # macOS can only show the camera-permission dialog from the main thread, so the
        # caller may open the capture there and pass it in; on Linux/Pi it's fine to let
        # the worker open its own.
        self.capture = capture
        # Optional ResearchRecorder (DATA-002): per-frame features -> ring buffer.
        self.recorder = recorder
        self._stop = threading.Event()

        self.camera_index = get(cfg, "vision.camera_index", 0)
        self.frame_width = get(cfg, "vision.frame_width", 640)
        self.frame_height = get(cfg, "vision.frame_height", 480)
        self.detect_every = max(1, get(cfg, "vision.detection_every_n_frames", 3))
        self.presence_interval = get(cfg, "vision.presence_check_seconds", 1.0)
        self.unknown_gate = UnknownBottleGate(
            debounce_seconds=get(cfg, "detection.unknown_debounce_seconds", 3.0),
            repeat_seconds=get(cfg, "detection.unknown_repeat_seconds", 30.0),
        )

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
            from mesa.vision.camera import configure_capture, disable_dynamic_framerate
            if configure_capture(cap, self.cfg, cv2_module=cv2):
                disable_dynamic_framerate(get(self.cfg, "vision.camera.device", "/dev/video0"))
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
                if self.recorder is not None:
                    lms = (reading.raw_result.pose_landmarks
                           if reading.raw_result is not None else None)
                    self.recorder.on_frame(lms, now)

                if now - last_presence_ts >= self.presence_interval:
                    last_presence_ts = now
                    self.bus.publish(
                        Event(PRESENCE_CHECK, {"person_present": person_present}, ts=now)
                    )

                if detector is not None and frame_no % self.detect_every == 0:
                    detections = detector.detect(frame)
                    if self.recorder is not None:
                        if not self.recorder._name_to_id:
                            self.recorder.set_class_names(detector.names)
                        self.recorder.on_detections(detections)
                    if not self.known_meds:
                        # No meds configured in the DB: fall back to the model's classes.
                        self.known_meds = set(detector.names.values())
                    for med, present in presence_map(detections, self.known_meds).items():
                        self.bus.publish(
                            Event(BOTTLE_OBSERVATION,
                                  {"med_name": med, "present": present}, ts=now)
                        )
                    unknowns = unknown_boxes(detections)
                    if self.unknown_gate.update(bool(unknowns), now):
                        self.bus.publish(
                            Event(UNKNOWN_MEDICATION,
                                  {"count": len(unknowns),
                                   "confidence": max(d.confidence for d in unknowns)},
                                  ts=now)
                        )
        finally:
            cap.release()
            estimator.close()
