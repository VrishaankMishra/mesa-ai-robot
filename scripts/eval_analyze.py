#!/usr/bin/env python3
"""Domain-shift evaluation analyzer (paper data).

Scores one or more model weight files against every captured evaluation session
(``eval_data/<condition>/<session>/`` from ``eval_capture.py``) and writes a tidy CSV
plus a condition x class summary table per model.

    .venv/bin/python scripts/eval_analyze.py \
        --models models/best.pt,models/best_v1_backup.pt \
        --eval-dir eval_data --conf 0.45 --out docs/eval/domain_shift_results.csv

Scoring (pure functions, unit-tested in tests/test_eval_analyze.py):
- single scenes: correct iff the highest-confidence non-tray detection matches the
  manifest's ground truth at/above threshold.
- unknown scenes: correct iff NO known-med label is asserted at/above threshold
  (no detection at all, or the low-confidence "unknown" path — both mean MeSA
  would not misidentify the foreign item).
- group scenes: recall = fraction of expected meds detected at/above threshold.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

TRAY = "tray"


def score_single(dets: list[tuple[str, float]], truth: str, conf: float) -> bool:
    """dets: (label, confidence) pairs. Top non-tray det must match truth at >= conf."""
    real = [d for d in dets if d[0] != TRAY and d[1] >= conf]
    if not real:
        return False
    top = max(real, key=lambda d: d[1])
    return top[0] == truth


def score_unknown(dets: list[tuple[str, float]], known: set[str], conf: float) -> bool:
    """Unknown probe is handled correctly iff no known med is asserted at >= conf."""
    return not any(d[0] in known and d[1] >= conf for d in dets)


def score_group(dets: list[tuple[str, float]], expected: set[str], conf: float) -> float:
    """Fraction of expected meds present at >= conf (tray ignored)."""
    seen = {d[0] for d in dets if d[1] >= conf and d[0] != TRAY}
    return len(seen & expected) / len(expected) if expected else 0.0


def best_conf_for(dets: list[tuple[str, float]], truth: str) -> float:
    matches = [d[1] for d in dets if d[0] == truth]
    return max(matches, default=0.0)


def main() -> int:
    p = argparse.ArgumentParser(description="Score models against eval sessions")
    p.add_argument("--models", required=True, help="comma-separated .pt paths")
    p.add_argument("--eval-dir", default="eval_data")
    p.add_argument("--conf", type=float, default=0.45)
    p.add_argument("--out", default="docs/eval/domain_shift_results.csv")
    p.add_argument("--skip-first", type=int, default=1,
                   help="frames to skip at each cell start (placement transition; "
                        "frame 00 routinely shows the previous bottle mid-swap)")
    args = p.parse_args()

    from ultralytics import YOLO

    eval_dir = Path(args.eval_dir)
    manifests = sorted(eval_dir.glob("*/*/manifest.csv"))
    if not manifests:
        print(f"no sessions under {eval_dir}")
        return 1

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = open(out_path, "w", newline="")
    w = csv.writer(out)
    w.writerow(["model", "condition", "session", "scene", "ground_truth", "mark_m",
                "frame", "correct", "gt_confidence"])

    summaries = {}
    for model_path in [m.strip() for m in args.models.split(",")]:
        model = YOLO(model_path)
        known = {n for n in model.names.values() if n != TRAY}
        tag = Path(model_path).stem
        per_cell = defaultdict(lambda: [0, 0])  # (condition, gt, scene) -> [hits, n]

        for mpath in manifests:
            sess_dir = mpath.parent
            with open(mpath) as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                img = sess_dir / r["filename"]
                if not img.exists():
                    continue
                frame_idx = int(r["filename"].rsplit("__", 1)[1].split(".")[0])
                if frame_idx < args.skip_first:
                    continue
                res = model.predict(str(img), conf=0.10, verbose=False)[0]
                dets = [(model.names[int(b.cls[0])], float(b.conf[0])) for b in res.boxes]
                scene, truth = r["scene"], r["ground_truth"]
                if scene == "single":
                    ok = score_single(dets, truth, args.conf)
                elif scene == "unknown":
                    ok = score_unknown(dets, known, args.conf)
                else:  # group
                    ok = score_group(dets, known, args.conf) >= 0.75
                gt_conf = best_conf_for(dets, truth) if scene == "single" else ""
                w.writerow([tag, r["condition"], r["session"], scene, truth,
                            r["mark_m"], r["filename"], int(ok), gt_conf])
                cell = (r["condition"], truth if scene != "group" else "GROUP", scene)
                per_cell[cell][0] += int(ok)
                per_cell[cell][1] += 1
        summaries[tag] = per_cell

    out.close()
    for tag, per_cell in summaries.items():
        print(f"\n=== {tag} (threshold {args.conf}) ===")
        conditions = sorted({c for c, _, _ in per_cell})
        for cond in conditions:
            cells = {(g, s): v for (c, g, s), v in per_cell.items() if c == cond}
            parts = [f"{g}:{v[0]}/{v[1]}" for (g, s), v in sorted(cells.items())]
            print(f"  {cond}: " + "  ".join(parts))
    print(f"\nraw rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
