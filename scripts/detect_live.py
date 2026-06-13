#!/usr/bin/env python3
"""Live medication detection (VIS-006).

Opens the webcam, runs the fine-tuned YOLOv8 model, draws boxes + confidence, and prints
the running FPS. Low-confidence boxes are drawn in red as "unknown" (the wrong-medication
path for MED-DEMO).

Usage:
    python scripts/detect_live.py --model models/best.pt --conf 0.5

Run manually on the laptop (needs camera + ultralytics). Not part of the test suite.
"""

from __future__ import annotations

import argparse
import sys
import time

from mesa.config import get, load_config
from mesa.vision.detector import YOLODetector


def parse_args() -> argparse.Namespace:
    cfg = load_config()
    p = argparse.ArgumentParser(description="MeSA live detection")
    p.add_argument("--model", default=get(cfg, "detection.model_path", "models/best.pt"))
    p.add_argument("--conf", type=float, default=get(cfg, "detection.confidence_threshold", 0.5))
    p.add_argument("--camera", type=int, default=get(cfg, "vision.camera_index", 0))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    try:
        import cv2
    except ImportError:
        print("opencv-python required: pip install -r requirements.txt", file=sys.stderr)
        return 1

    detector = YOLODetector(args.model, conf_threshold=args.conf)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Could not open camera {args.camera}", file=sys.stderr)
        return 1

    print("Running detection. q to quit.")
    last = time.time()
    fps = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            detections = detector.detect(frame)
            for d in detections:
                x1, y1, x2, y2 = d.box
                color = (0, 0, 255) if d.is_unknown else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x1, max(0, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last, 1e-6))
            last = now
            cv2.putText(frame, f"{fps:4.1f} FPS", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.imshow("MeSA detect (q=quit)", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
