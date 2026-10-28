#!/usr/bin/env python3
"""Recover a Roboflow export and run held-out tests on the trained weights.

The checkpoints' embedded train_args say the deployed champion (`best.pt`) and the
synthetic arm (`best_v3syn.pt`) trained on Roboflow **version 4** — so that is the default
here (NOT version 2; "v2" is the both-rounds *label*, not the Roboflow version number).
See models/training-metadata/checkpoint-provenance.md.

Credentials: the Roboflow API key is read from the ROBOFLOW_API_KEY environment variable and
is never printed or written anywhere. Run it yourself — do not paste the key into a chat.

    export ROBOFLOW_API_KEY=...            # your key, in your own shell
    .venv/bin/pip install roboflow         # not in the venv yet
    .venv/bin/python scripts/recover_roboflow_export.py            # version 4, both models
    .venv/bin/python scripts/recover_roboflow_export.py --version 1   # the v1 export

What it does:
  1. downloads version N (YOLOv8) into datasets/roboflow_v<N>/ (gitignored)
  2. prints split image counts + an aggregate SHA-256 fingerprint
  3. runs `.val(split="test")` for each model against the pulled data.yaml and prints test mAP

The held-out test is the self-check: if best.pt scores in its ~0.95-0.98 band on this
export's test split, the version is the right one; a poor score means the wrong version.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

WORKSPACE = "vrishaank-mishra"
PROJECT = "medication-safety-object-detecti"
REPO = Path(__file__).resolve().parents[1]


def fingerprint(root: Path) -> tuple[int, str]:
    """Count files and return an aggregate SHA-256 over their sorted per-file hashes."""
    files = sorted(
        p for p in root.rglob("*") if p.is_file() and p.name != ".DS_Store"
    )
    agg = hashlib.sha256()
    for p in files:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        agg.update(f"{h}  {p.relative_to(root)}\n".encode())
    return len(files), agg.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", type=int, default=4,
                    help="Roboflow dataset version to pull (default: 4, the champion's).")
    ap.add_argument("--models", nargs="*",
                    default=["best.pt", "best_v3syn.pt"],
                    help="weights under models/ to test on the pulled test split.")
    ap.add_argument("--no-test", action="store_true",
                    help="download and fingerprint only; skip the held-out tests.")
    args = ap.parse_args()

    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        print("ERROR: set ROBOFLOW_API_KEY in your environment first "
              "(export ROBOFLOW_API_KEY=...). The key is never printed or stored.",
              file=sys.stderr)
        return 2
    try:
        from roboflow import Roboflow
    except ModuleNotFoundError:
        print("ERROR: roboflow not installed. Run:  .venv/bin/pip install roboflow",
              file=sys.stderr)
        return 2

    out = REPO / "datasets" / f"roboflow_v{args.version}"
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {PROJECT} version {args.version} (YOLOv8) -> {out} ...")
    rf = Roboflow(api_key=key)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    dataset = project.version(args.version).download("yolov8", location=str(out))
    loc = Path(dataset.location)

    for split in ("train", "valid", "test"):
        imgs = loc / split / "images"
        n = len(list(imgs.glob("*"))) if imgs.is_dir() else 0
        print(f"  {split}: {n} images")
    nfiles, agg = fingerprint(loc)
    print(f"  fingerprint: {nfiles} files, aggregate SHA-256 {agg}")

    if args.no_test:
        return 0

    from ultralytics import YOLO
    data_yaml = loc / "data.yaml"
    print("\nHeld-out test (split=test):")
    for name in args.models:
        weights = REPO / "models" / name
        if not weights.exists():
            print(f"  {name}: MISSING at {weights}")
            continue
        metrics = YOLO(str(weights)).val(data=str(data_yaml), split="test", verbose=False)
        print(f"  {name}: test mAP@50 = {metrics.box.map50:.3f} | "
              f"mAP@50-95 = {metrics.box.map:.3f}")
    print("\nNote: record these numbers in docs/training/<arm>/ and "
          "models/training-metadata/. Fill eval-report-v<N>.md as needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
