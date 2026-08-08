#!/usr/bin/env python3
"""Voice-guided, hands-free dataset capture (VIS-002, Pi edition).

`capture.py` needs a display and a keyboard; on the Pi rig there is neither. This script
instead uses the robot's own speaker to walk the operator through every capture cell:
it announces bottle / distance / position, waits while you place the bottle, then shoots
a short burst while you slowly rotate it. Files land in ``datasets/raw/<bottle>/`` with
the same condition-encoded names capture.py produces, so Roboflow upload is unchanged.

One run covers one lighting condition for a list of bottles, e.g.:

    .venv/bin/python -u scripts/capture_guided.py \
        --bottles tylenol,vitamin_d,multivitamin,ibuprofen,aspirin,calcium \
        --lighting bright

Change the room lighting, rerun with --lighting dim, then --lighting mixed.
Speech uses the espeak-ng CLI directly (more robust than pyttsx3 for long sessions).
Hardware-bound glue; not part of the test suite.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "datasets" / "raw"

LIGHTING_CHOICES = ("bright", "dim", "mixed", "daylight")

# (spoken name, angle-degrees for the filename slug). Left/right = move the bottle to
# the side of the table so the camera sees it ~30 degrees off-axis.
POSITIONS = [("straight ahead", 0), ("to the left side", -30), ("to the right side", 30)]


def say(text: str) -> None:
    print(f"[say] {text}", flush=True)
    subprocess.run(["espeak-ng", "-s", "150", text], check=False)


def slug(bottle: str, lighting: str, angle: int, meters: float) -> str:
    a = f"a{angle}".replace("-", "n")
    d = f"d{int(round(meters * 10)):02d}"
    return f"{bottle}__{lighting}__{a}__{d}"


def grab(cap, flush: int = 4):
    """Read past buffered frames so the shot reflects the scene *now*, post-sleep."""
    frame = None
    for _ in range(flush):
        ok, f = cap.read()
        if ok:
            frame = f
    return frame


def burst(cap, cv2, out_dir: Path, prefix: str, shots: int, interval: float) -> int:
    count = len(list(out_dir.glob(f"{prefix}__*.jpg")))
    saved = 0
    for _ in range(shots):
        frame = grab(cap)
        if frame is None:
            say("Camera error. Skipping.")
            return saved
        stamp = datetime.now().strftime("%H%M%S%f")[:-3]
        cv2.imwrite(str(out_dir / f"{prefix}__{count + saved:04d}_{stamp}.jpg"), frame)
        saved += 1
        time.sleep(interval)
    return saved


def main() -> int:
    p = argparse.ArgumentParser(description="MeSA voice-guided dataset capture")
    p.add_argument("--bottles", required=True,
                   help="comma-separated labels in capture order, e.g. tylenol,aspirin")
    p.add_argument("--lighting", required=True, choices=LIGHTING_CHOICES)
    p.add_argument("--distances", default="0.6,0.75,0.9",
                   help="comma-separated meters matching the tape marks (near,mid,far)")
    p.add_argument("--shots", type=int, default=4, help="shots per cell (rotate between)")
    p.add_argument("--interval", type=float, default=1.2, help="seconds between shots")
    p.add_argument("--position-wait", type=float, default=6.0,
                   help="seconds to place the bottle after the announcement")
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--skip-clutter", action="store_true",
                   help="skip the tray/clutter stage at the end")
    args = p.parse_args()

    import cv2  # lazy, like the other capture/vision scripts

    bottles = [b.strip() for b in args.bottles.split(",") if b.strip()]
    distances = [float(d) for d in args.distances.split(",")]
    dist_names = ["near mark", "middle mark", "far mark"][: len(distances)]

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print("Could not open camera", file=sys.stderr)
        return 1

    total = 0
    say(f"Starting {args.lighting} lighting capture for {len(bottles)} bottles.")
    try:
        for bottle in bottles:
            out_dir = RAW_DIR / bottle
            out_dir.mkdir(parents=True, exist_ok=True)
            say(f"Next bottle: {bottle.replace('_', ' ')}.")
            for dist_name, meters in zip(dist_names, distances):
                for pos_name, angle in POSITIONS:
                    say(f"Place it at the {dist_name}, {pos_name}.")
                    time.sleep(args.position_wait)
                    say("Capturing. Slowly turn the bottle.")
                    n = burst(cap, cv2, out_dir, slug(bottle, args.lighting, angle, meters),
                              args.shots, args.interval)
                    total += n
                    print(f"  {bottle} {dist_name} {angle:+d}deg: {n} shots "
                          f"(total {total})", flush=True)
        if not args.skip_clutter:
            say("Last stage. Place the full tray with several bottles in view.")
            time.sleep(args.position_wait + 4)
            out_dir = RAW_DIR / "_clutter"
            out_dir.mkdir(parents=True, exist_ok=True)
            say("Capturing the tray. Rearrange bottles, and pass your hand through "
                "the scene a few times.")
            total += burst(cap, cv2, out_dir, f"tray__{args.lighting}__a0__d08",
                           shots=20, interval=1.5)
    finally:
        cap.release()

    say(f"Done. {total} pictures saved for {args.lighting} lighting.")
    print(f"TOTAL {total} images -> {RAW_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
