#!/usr/bin/env python3
"""Live posture detection (VIS-008 + VIS-010 wiring).

Runs MediaPipe Pose on the webcam, classifies posture each frame, overlays the label, and
fires a spoken "Are you okay?" check-in when lying exceeds the configured duration.

    python scripts/pose_live.py --echo

The classification + trigger logic lives in mesa.vision.posture (unit-tested); this script
is the MediaPipe/camera glue and is not part of the test suite.
"""

from __future__ import annotations

import argparse

from mesa.audio.tts import speak
from mesa.config import get, load_config
from mesa.vision.posture import Posture, PostureMonitor, classify_posture

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
    args = p.parse_args()
    trigger = get(cfg, "pose.lying_trigger_seconds", 30)

    import time

    import cv2
    import mediapipe as mp

    pose = mp.solutions.pose.Pose(model_complexity=0)
    cap = cv2.VideoCapture(args.camera)
    monitor = PostureMonitor(lying_trigger_seconds=trigger)

    try:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            posture = Posture.UNKNOWN
            if result.pose_landmarks:
                lm = result.pose_landmarks.landmark
                landmarks = {name: (lm[idx].x, lm[idx].y) for name, idx in _LANDMARK_IDS.items()}
                posture = classify_posture(landmarks)
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, result.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS
                )

            event = monitor.update(posture, time.time())
            if event is not None:
                speak("Are you okay? I noticed you've been lying down.", echo=args.echo)

            cv2.putText(frame, posture.value, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            cv2.imshow("MeSA posture (q=quit)", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
