#!/usr/bin/env python3
"""Live posture detection (VIS-008 + VIS-010 wiring).

Runs MediaPipe Pose on the webcam, classifies posture each frame, overlays the label, and
fires a spoken "Are you okay?" check-in when lying exceeds the configured duration.

    python scripts/pose_live.py --echo                 # windowed (needs a display)
    python scripts/pose_live.py --headless --seconds 20 # no window; print labels (SSH/CI)

Posture labels are smoothed (majority vote over a window) before they drive the display and
the fall timer, so per-frame jitter doesn't reset the lying countdown. The classification,
smoothing, and trigger logic all live in mesa.vision.posture (unit-tested); this script is
the MediaPipe/camera glue and is not part of the test suite.
"""

from __future__ import annotations

import argparse

from mesa.audio.tts import speak
from mesa.config import get, load_config
from mesa.vision.posture import Posture, PostureMonitor, PostureSmoother, classify_posture

# MediaPipe Pose landmark indices -> our names.
_LANDMARK_IDS = {
    "left_shoulder": 11, "right_shoulder": 12,
    "left_hip": 23, "right_hip": 24,
    "left_knee": 25, "right_knee": 26,
    "left_ankle": 27, "right_ankle": 28,
}


def main() -> int:
    cfg = load_config()
    p = argparse.ArgumentParser(description="MeSA live posture detection")
    p.add_argument("--camera", type=int, default=get(cfg, "vision.camera_index", 0))
    p.add_argument("--echo", action="store_true", help="print check-in instead of speaking")
    p.add_argument("--headless", action="store_true",
                   help="no display window; print posture transitions (for SSH / CI)")
    p.add_argument("--seconds", type=float, default=None,
                   help="run for this many seconds then exit (default: until 'q')")
    p.add_argument("--lying-trigger", type=float, default=None,
                   help="override pose.lying_trigger_seconds (handy for demos)")
    args = p.parse_args()
    trigger = args.lying_trigger if args.lying_trigger is not None \
        else get(cfg, "pose.lying_trigger_seconds", 30)
    window = get(cfg, "pose.smoothing_window", 15)
    min_vis = get(cfg, "pose.min_landmark_visibility", 0.5)
    grace = get(cfg, "pose.lying_gap_grace_seconds", 5)
    complexity = get(cfg, "pose.model_complexity", 1)

    import time

    import cv2
    import mediapipe as mp

    pose = mp.solutions.pose.Pose(model_complexity=complexity)
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, get(cfg, "vision.frame_width", 640))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, get(cfg, "vision.frame_height", 480))
    monitor = PostureMonitor(lying_trigger_seconds=trigger, gap_grace_seconds=grace)
    smoother = PostureSmoother(window=window)

    start = time.time()
    frames = 0
    last_printed = None
    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            frames += 1
            result = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            raw = Posture.UNKNOWN
            if result.pose_landmarks:
                lm = result.pose_landmarks.landmark
                landmarks = {name: (lm[idx].x, lm[idx].y) for name, idx in _LANDMARK_IDS.items()}
                vis = {name: lm[idx].visibility for name, idx in _LANDMARK_IDS.items()}
                raw = classify_posture(landmarks, visibility=vis, min_visibility=min_vis)
                if not args.headless:
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS
                    )

            # Smooth the per-frame label before it drives display + the fall timer.
            posture = smoother.update(raw)

            now = time.time()
            event = monitor.update(posture, now)
            if event is not None:
                speak("Are you okay? I noticed you've been lying down.", echo=args.echo)

            if args.headless:
                if posture.value != last_printed:
                    print(f"[{now - start:5.1f}s] {posture.value}", flush=True)
                    last_printed = posture.value
            else:
                cv2.putText(frame, posture.value, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                cv2.imshow("MeSA posture (q=quit)", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

            if args.seconds is not None and (now - start) >= args.seconds:
                break
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()

    if args.headless:
        el = time.time() - start
        if el > 0:
            print(f"frames={frames}  fps={frames / el:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
