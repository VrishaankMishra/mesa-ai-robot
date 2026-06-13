#!/usr/bin/env python3
"""Dataset capture helper (VIS-002).

Opens the webcam, shows a live preview, and saves frames with structured filenames
encoding the capture conditions, so the coverage matrix in docs/capture-protocol.md is
easy to follow. Files land in ``datasets/raw/<bottle>/``.

Usage:
    python scripts/capture.py --bottle tylenol --lighting bright --angle 0 --distance 0.5

Keys (in the preview window):
    SPACE  capture a frame
    q      quit

This script is run manually on the laptop with the camera attached; it is not part of
the automated test suite (it needs hardware + opencv).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

LIGHTING_CHOICES = ("bright", "dim", "mixed")
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "datasets" / "raw"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MeSA dataset capture helper")
    p.add_argument("--bottle", required=True, help="bottle/class label, e.g. tylenol")
    p.add_argument("--lighting", required=True, choices=LIGHTING_CHOICES)
    p.add_argument("--angle", required=True, type=int, help="degrees, e.g. 0, 30, -30")
    p.add_argument("--distance", required=True, type=float, help="meters, e.g. 0.5")
    p.add_argument("--camera", type=int, default=0, help="cv2 camera index (default 0)")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    return p.parse_args()


def slug(args: argparse.Namespace) -> str:
    """Build the filename stem prefix: tylenol__bright__a0__d05."""
    angle = f"a{args.angle}".replace("-", "n")
    dist = f"d{int(round(args.distance * 10)):02d}"
    return f"{args.bottle}__{args.lighting}__{angle}__{dist}"


def main() -> int:
    args = parse_args()
    try:
        import cv2  # imported lazily so the rest of the repo doesn't require opencv
    except ImportError:
        print("opencv-python is required: pip install -r requirements.txt", file=sys.stderr)
        return 1

    out_dir = RAW_DIR / args.bottle
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = slug(args)

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(f"Could not open camera index {args.camera}", file=sys.stderr)
        return 1

    count = len(list(out_dir.glob(f"{prefix}__*.jpg")))
    print(f"Capturing to {out_dir} (prefix '{prefix}'). SPACE=capture, q=quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed", file=sys.stderr)
                break
            hud = frame.copy()
            cv2.putText(hud, f"{prefix}  n={count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("MeSA capture (SPACE=shoot, q=quit)", hud)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                stamp = datetime.now().strftime("%H%M%S%f")[:-3]
                fname = out_dir / f"{prefix}__{count:04d}_{stamp}.jpg"
                cv2.imwrite(str(fname), frame)
                count += 1
                print(f"  saved {fname.name}")
    finally:
        cap.release()
        cv2.destroyAllWindows()

    print(f"Done. {count} images in {out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
