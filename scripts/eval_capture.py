#!/usr/bin/env python3
"""Domain-shift evaluation capture (RES-002 / paper data collection).

Voice-guided, standardized placement session for ONE environmental condition.
Because placement is scripted, ground truth is free: no labeling ever. Frames and a
manifest land in ``eval_data/<condition>/<session>/``; scoring happens offline on the
laptop with ``scripts/eval_analyze.py`` against any set of model weights.

One session (~9 min): every bottle at two marks (12 frames each, slow rotation),
an optional unknown-medication probe (e.g. the untrained Benadryl box), and a final
all-bottles group scene.

    .venv/bin/python scripts/eval_capture.py \
        --condition evening_lamps_on \
        --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
        --unknown benadryl

Hardware-bound glue (camera + speaker); the manifest format is the contract with the
analyzer and is unit-tested there.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = REPO_ROOT / "eval_data"

MARKS = [("near mark", 0.6), ("far mark", 0.8)]  # 24" and 32" on the taped rig


def say(text: str) -> None:
    print(f"[say] {text}", flush=True)
    subprocess.run(["espeak-ng", "-s", "160", text], check=False)


def grab(cap, flush: int = 4):
    frame = None
    for _ in range(flush):
        ok, f = cap.read()
        if ok:
            frame = f
    return frame


def main() -> int:
    p = argparse.ArgumentParser(description="MeSA domain-shift evaluation session")
    p.add_argument("--condition", required=True,
                   help="condition label, e.g. morning_lamps_off, evening_lamps_on")
    p.add_argument("--bottles", required=True, help="comma-separated known med labels")
    p.add_argument("--unknown", default=None,
                   help="label for an untrained wrong-med probe item (e.g. benadryl)")
    p.add_argument("--frames", type=int, default=12, help="frames per placement cell")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--position-wait", type=float, default=8.0)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    args = p.parse_args()

    import cv2

    bottles = [b.strip() for b in args.bottles.split(",") if b.strip()]
    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = EVAL_DIR / args.condition / session
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print("Could not open camera", file=sys.stderr)
        return 1

    manifest_path = out_dir / "manifest.csv"
    mf = open(manifest_path, "w", newline="")
    writer = csv.writer(mf)
    writer.writerow(["filename", "ground_truth", "scene", "mark_m",
                     "condition", "session", "captured_at"])

    def burst(label: str, scene: str, mark_m: float, n: int) -> None:
        say("Capturing. Turn it slowly.")
        for i in range(n):
            frame = grab(cap)
            if frame is None:
                say("Camera error, skipping.")
                return
            fname = f"{label}__{scene}__d{int(mark_m*10):02d}__{i:02d}.jpg"
            cv2.imwrite(str(out_dir / fname), frame)
            writer.writerow([fname, label, scene, mark_m, args.condition,
                             session, datetime.now().isoformat(timespec="seconds")])
            time.sleep(args.interval)
        mf.flush()

    say(f"Evaluation session for condition {args.condition.replace('_', ' ')}. "
        "Table must be empty. Same routine as capture: one item at a time.")
    for bottle in bottles:
        say(f"Next: {bottle.replace('_', ' ')}.")
        for mark_name, meters in MARKS:
            say(f"Place it at the {mark_name}.")
            time.sleep(args.position_wait)
            burst(bottle, "single", meters, args.frames)

    if args.unknown:
        say(f"Now the unknown item: place the {args.unknown} at the near mark.")
        time.sleep(args.position_wait)
        burst(args.unknown, "unknown", MARKS[0][1], args.frames)
        say(f"Remove the {args.unknown} and put it away.")
        time.sleep(3)

    say("Last stage: place ALL bottles on the table, well spread out, "
        "at least a hand-width apart.")
    time.sleep(args.position_wait + 8)
    burst("ALL", "group", MARKS[0][1], args.frames)

    mf.close()
    cap.release()
    n = len(list(out_dir.glob("*.jpg")))
    say(f"Session done. {n} frames recorded.")
    print(f"SESSION COMPLETE: {n} frames -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
