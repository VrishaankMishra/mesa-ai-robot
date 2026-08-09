#!/usr/bin/env python3
"""Aggregate voice-grid session manifests into the paper-#2 results table (RES-004).

    .venv/bin/python scripts/eval_voice_analyze.py --eval-dir eval_voice \
        --out docs/eval/voice_grid_results.csv

Per condition cell: wake-word detection rate (wake-expected trials), false-wake rate
(no-wake controls), intent accuracy (given wake detected), and full-trial exact rate.
Scoring is computed from manifest columns written at capture time; this script only
aggregates (pure function, unit-tested).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def aggregate(rows: list[dict]) -> dict[str, dict[str, float]]:
    """manifest rows -> {condition: metrics}. Pure; unit-tested."""
    cells: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        c = r["condition"]
        wake_expected = bool(int(r["wake_expected"]))
        wake_detected = bool(int(r["wake_detected"]))
        if wake_expected:
            cells[c]["wake_hits"].append(int(wake_detected))
            if wake_detected:
                cells[c]["intent_hits"].append(
                    int(r["parsed_intent"] == r["expected_intent"]))
        else:
            cells[c]["false_wakes"].append(int(wake_detected))
        cells[c]["exact"].append(int(r["exact_wake_and_intent"]))

    def rate(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    return {
        c: {
            "wake_rate": rate(v["wake_hits"]),
            "false_wake_rate": rate(v["false_wakes"]),
            "intent_acc_given_wake": rate(v["intent_hits"]),
            "exact_rate": rate(v["exact"]),
            "n_trials": len(v["exact"]),
        }
        for c, v in cells.items()
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--eval-dir", default="eval_voice")
    p.add_argument("--out", default="docs/eval/voice_grid_results.csv")
    args = p.parse_args()

    rows: list[dict] = []
    for mpath in sorted(Path(args.eval_dir).glob("*/*/manifest.csv")):
        with open(mpath) as f:
            rows.extend(csv.DictReader(f))
    if not rows:
        print(f"no sessions under {args.eval_dir}")
        return 1

    table = aggregate(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "wake_rate", "false_wake_rate",
                    "intent_acc_given_wake", "exact_rate", "n_trials"])
        for c in sorted(table):
            m = table[c]
            w.writerow([c, f"{m['wake_rate']:.3f}", f"{m['false_wake_rate']:.3f}",
                        f"{m['intent_acc_given_wake']:.3f}", f"{m['exact_rate']:.3f}",
                        int(m["n_trials"])])
            print(f"{c}: wake {m['wake_rate']:.0%}  false-wake {m['false_wake_rate']:.0%}  "
                  f"intent|wake {m['intent_acc_given_wake']:.0%}  exact {m['exact_rate']:.0%}"
                  f"  (n={int(m['n_trials'])})")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
