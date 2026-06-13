#!/usr/bin/env python3
"""Evaluate a trained detector (VIS-005).

Runs Ultralytics validation against the dataset's ``data.yaml`` and prints headline +
per-class metrics, then points to the confusion matrix Ultralytics writes to disk. Copy
the numbers into docs/eval-report-template.md.

Usage:
    python scripts/evaluate.py --model models/best.pt --data datasets/data.yaml

Run manually (needs ultralytics + a trained model). Not part of the test suite.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Evaluate MeSA detector")
    p.add_argument("--model", default="models/best.pt")
    p.add_argument("--data", default="datasets/data.yaml")
    p.add_argument("--imgsz", type=int, default=640)
    args = p.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics required: pip install -r requirements.txt", file=sys.stderr)
        return 1

    model = YOLO(args.model)
    metrics = model.val(data=args.data, imgsz=args.imgsz, verbose=False)

    print("\n=== Headline ===")
    print(f"mAP@50    : {metrics.box.map50:.4f}  (target >= 0.90)")
    print(f"mAP@50-95 : {metrics.box.map:.4f}")
    print(f"Precision : {metrics.box.mp:.4f}")
    print(f"Recall    : {metrics.box.mr:.4f}")

    print("\n=== Per-class mAP@50 ===")
    names = model.names
    for i, ap50 in enumerate(metrics.box.ap50):
        print(f"  {names.get(i, i):<14} {ap50:.4f}")

    print(f"\nConfusion matrix + plots saved under: {metrics.save_dir}")
    status = "PASS" if metrics.box.map50 >= 0.90 else "BELOW TARGET (run VIS-007)"
    print(f"\nM2 status: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
