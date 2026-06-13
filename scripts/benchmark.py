#!/usr/bin/env python3
"""FPS benchmark for detection + pose (HW-001 / HW-002).

Measures sustained FPS of YOLOv8 detection and MediaPipe pose on the current machine, so
you can record the Pi 5 numbers and tune frame-skipping to keep pose >=5 FPS.

    python scripts/benchmark.py --model models/best.pt --frames 200

Needs a camera + ultralytics + mediapipe. Not part of the test suite.
"""

from __future__ import annotations

import argparse
import time


def main() -> int:
    p = argparse.ArgumentParser(description="MeSA FPS benchmark")
    p.add_argument("--model", default="models/best.pt")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--frames", type=int, default=200)
    p.add_argument("--detect-every", type=int, default=3, help="run detection every Nth frame")
    args = p.parse_args()

    import cv2
    import mediapipe as mp
    from ultralytics import YOLO

    model = YOLO(args.model)
    pose = mp.solutions.pose.Pose(model_complexity=0)
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    det_time = pose_time = 0.0
    det_count = frames = 0
    start = time.time()
    while frames < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        if frames % args.detect_every == 0:
            t = time.time()
            model.predict(frame, verbose=False)
            det_time += time.time() - t
            det_count += 1
        t = time.time()
        pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        pose_time += time.time() - t
        frames += 1
    cap.release()

    wall = time.time() - start
    print(f"frames           : {frames}")
    print(f"overall FPS      : {frames / wall:5.1f}")
    print(f"detection FPS    : {det_count / det_time:5.1f}  (ran {det_count} times)")
    print(f"pose FPS         : {frames / pose_time:5.1f}")
    print(f"pose >=5 FPS     : {'PASS' if frames / pose_time >= 5 else 'TUNE frame-skip/res'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
