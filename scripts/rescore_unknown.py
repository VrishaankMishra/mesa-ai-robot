#!/usr/bin/env python3
"""Re-score the unknown probes for absorption confidence (open-set analysis).

    .venv/bin/python scripts/rescore_unknown.py --model models/best.pt

``eval_analyze.py`` records ``gt_confidence`` only for single scenes, because an unknown
probe has no true class among the trained set — so the column is empty for every
unknown-probe row and the open-set behaviour cannot be examined as a function of the
confidence threshold. It can only be read at the one threshold the study happened to use.

This records the missing number: for each unknown-probe frame, the **highest confidence
assigned to any known medication** — the confidence with which the detector absorbs a
stranger into a trained class. Sweeping a threshold over that column gives the rejection
rate at any operating point, which is what is needed to test whether known-class detection
and unknown-class rejection can ever be satisfied together.

Semantics mirror ``eval_analyze.py`` exactly: inference at a 0.10 floor, the same
``skip_first`` rule (frame 00 routinely catches the previous container mid-swap), and the
same definition of "known" (every trained class except ``tray``).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

TRAY = "tray"


def rejection_rate(absorption_confs: list[float], threshold: float) -> float:
    """Fraction of unknown probes rejected at ``threshold``.

    A probe is rejected iff no known class is asserted at or above the threshold, i.e. its
    absorption confidence falls below it. Pure, so the sweep is testable without a model.
    """
    if not absorption_confs:
        return float("nan")
    return sum(1 for c in absorption_confs if c < threshold) / len(absorption_confs)


def main() -> int:
    p = argparse.ArgumentParser(description="Re-score unknown probes for absorption confidence")
    p.add_argument("--model", default="models/best.pt")
    p.add_argument("--eval-dir", default="eval_data")
    p.add_argument("--skip-first", type=int, default=1)
    p.add_argument("--out", default="docs/eval/unknown_absorption.csv")
    args = p.parse_args()

    from ultralytics import YOLO

    manifests = sorted(Path(args.eval_dir).glob("*/*/manifest.csv"))
    if not manifests:
        print(f"no sessions under {args.eval_dir}")
        return 1

    model = YOLO(args.model)
    known = {n for n in model.names.values() if n != TRAY}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = open(out_path, "w", newline="")
    w = csv.writer(out)
    w.writerow(["model", "condition", "session", "frame", "absorbed_as",
                "absorption_confidence"])

    per_condition: dict[str, list[float]] = defaultdict(list)
    for mpath in manifests:
        sess_dir = mpath.parent
        for r in csv.DictReader(open(mpath)):
            if r["scene"] != "unknown":
                continue
            img = sess_dir / r["filename"]
            if not img.exists():
                continue
            if int(r["filename"].rsplit("__", 1)[1].split(".")[0]) < args.skip_first:
                continue
            res = model.predict(str(img), conf=0.10, verbose=False)[0]
            dets = [(model.names[int(b.cls[0])], float(b.conf[0])) for b in res.boxes]
            hits = [(lbl, c) for lbl, c in dets if lbl in known]
            if hits:
                label, conf = max(hits, key=lambda d: d[1])
            else:
                label, conf = "", 0.0
            w.writerow([Path(args.model).stem, r["condition"], r["session"],
                        r["filename"], label, f"{conf:.4f}"])
            per_condition[r["condition"]].append(conf)
    out.close()

    thresholds = [0.25, 0.35, 0.45, 0.55, 0.65, 0.75]
    print(f"\nunknown-probe absorption confidence -> {out_path}")
    print(f"{'condition':24s} " + "  ".join(f"tau={t:.2f}" for t in thresholds) + "    n   median")
    for cond in sorted(per_condition):
        cs = sorted(per_condition[cond])
        med = cs[len(cs) // 2]
        rates = "  ".join(f"{rejection_rate(cs, t)*100:6.0f}%" for t in thresholds)
        print(f"{cond:24s} {rates}  {len(cs):4d}   {med:.3f}")
    allc = [c for v in per_condition.values() for c in v]
    print(f"{'ALL':24s} " + "  ".join(f"{rejection_rate(allc,t)*100:6.0f}%" for t in thresholds)
          + f"  {len(allc):4d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
