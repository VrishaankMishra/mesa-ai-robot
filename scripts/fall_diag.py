#!/usr/bin/env python3
"""Torso-visibility diagnostic for the fall zone (VIS-010 validation).

    .venv/bin/python scripts/fall_diag.py --seconds 25

Prints, per sampled frame, the four torso landmark visibilities the gate in
``classify_posture`` actually reads, and the posture returned at several candidate
thresholds. Run it after ANY camera move, because the gate's safety depends on a
property of the *view*, not of the code: a real body in frame reports ~0.99 torso
visibility, while a camera that can only see a forearm makes MediaPipe invent a torso
at low confidence. The gate separates those two cases, and this is how you confirm the
separation still holds where the camera is now pointing.

Measured 2026-09-05 on staged lying poses on cushions (the only falls this project
stages): side-on min-visibility 0.948, head-toward-camera 0.997 — against a 0.5 bar,
with 208/208 frames classified `lying`. Before the gate existed, three spurious
`possible_fall` check-ins fired in five minutes at the medication-station geometry.
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TORSO = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
THRESHOLDS = (0.5, 0.3, 0.2, 0.1, 0.05)


def summarize(per_frame_mins: list[float], thresholds=THRESHOLDS) -> dict:
    """Pure: min-torso-visibility per frame -> pass rate at each threshold."""
    if not per_frame_mins:
        return {"frames": 0}
    s = sorted(per_frame_mins)
    return {
        "frames": len(s),
        "median": s[len(s) // 2],
        "p10": s[max(0, len(s) // 10)],
        "worst": s[0],
        "best": s[-1],
        "pass_rate": {t: sum(1 for v in s if v >= t) / len(s) for t in thresholds},
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Fall-zone torso visibility diagnostic")
    p.add_argument("--seconds", type=float, default=25.0)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--every", type=int, default=5, help="sample every Nth frame")
    args = p.parse_args()

    import cv2
    import mediapipe as mp

    from mesa.vision.pose_estimator import extract_named_landmarks
    from mesa.vision.posture import classify_posture

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # complexity 2 + static: the config measured (Jul 18) to find lying bodies at all.
    pose = mp.solutions.pose.Pose(model_complexity=2, static_image_mode=True)

    mins: list[float] = []
    verdicts: collections.Counter = collections.Counter()
    t0, n = time.time(), 0
    while time.time() - t0 < args.seconds:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        if n % args.every:
            continue
        res = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if not res.pose_landmarks:
            verdicts["NO_LANDMARKS"] += 1
            continue
        pts, vis = extract_named_landmarks(res.pose_landmarks)
        tv = [vis.get(k, 0.0) for k in TORSO]
        mins.append(min(tv))
        at = {t: classify_posture(pts, visibility=vis, min_visibility=t).value
              for t in THRESHOLDS}
        verdicts[at[0.5]] += 1
        print(f"  min_torso_vis={min(tv):.2f}  [{' '.join(f'{v:.2f}' for v in tv)}]  "
              f"0.5->{at[0.5]:8s} 0.2->{at[0.2]:8s} 0.05->{at[0.05]}", flush=True)
    cap.release()
    pose.close()

    s = summarize(mins)
    print()
    if s["frames"]:
        print(f"frames sampled: {s['frames']}   min-torso-visibility: "
              f"median={s['median']:.3f} p10={s['p10']:.3f} "
              f"worst={s['worst']:.3f} best={s['best']:.3f}")
        for t, rate in s["pass_rate"].items():
            print(f"  threshold {t:>4}: {rate*100:5.0f}% of frames classified")
    print("verdicts at 0.5:", dict(verdicts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
