#!/usr/bin/env python3
"""Paper figures from the domain-shift results CSV (RES-002).

Reads docs/eval/domain_shift_results.csv (output of eval_analyze.py) and writes
publication PNGs to docs/eval/figures/. Model arms are auto-detected, so re-running
after adding v3 rows regenerates every figure with the new arm included.

    .venv/bin/python scripts/eval_figures.py

Design follows the repo's dataviz conventions: sequential single-hue ramp for
magnitude (heatmap), fixed-order categorical hues for model/series identity,
values labeled in ink (never series color), one axis per chart, recessive grid.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

CSV = Path("docs/eval/domain_shift_results.csv")
OUT = Path("docs/eval/figures")

# Validated reference palette (light mode).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e6e5e2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed order, never cycled
SEQ_CMAP = LinearSegmentedColormap.from_list("blue_seq", ["#eef4fc", "#1c5aa8"])

CONDITION_ORDER = [
    "morning_lamps_off", "morning_lamps_on",
    "midday_lamps_off", "midday_lamp_added",
    "evening_lights_on", "evening_lamp_added",
    "evening_dim", "evening_dim_lamp",
]
CONDITION_LABELS = {
    "morning_lamps_off": "morning\n(direct sun)",
    "morning_lamps_on": "morning\n+ lights",
    "midday_lamps_off": "midday",
    "midday_lamp_added": "midday\n+ lamp",
    "evening_lights_on": "evening\n(lights on)",
    "evening_lamp_added": "evening\n+ lamp",
    "evening_dim": "evening dim\n(screens only)",
    "evening_dim_lamp": "evening dim\n+ lamp",
}

MEDS = ["mylanta", "vitamin_d3", "bayer_aspirin", "cvs_allergy",
        "omeprazole", "melatonin", "ashwagandha", "advil"]


def load():
    """-> {(model, condition, med): (hits, n)} for single scenes."""
    cells = defaultdict(lambda: [0, 0])
    models = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if r["scene"] != "single":
                continue
            key = (r["model"], r["condition"], r["ground_truth"])
            cells[key][0] += int(r["correct"])
            cells[key][1] += 1
            if r["model"] not in models:
                models.append(r["model"])
    return cells, models


def rate(cells, model, cond, med):
    h, n = cells.get((model, cond, med), (0, 0))
    return h / n if n else float("nan")


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8, length=0)


def fig_heatmap(cells, model, tag):
    fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=180)
    fig.patch.set_facecolor(SURFACE)
    data = [[rate(cells, model, c, m) for m in MEDS] for c in CONDITION_ORDER]
    im = ax.imshow(data, cmap=SEQ_CMAP, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(MEDS)),
                  [m.replace("_", "\n") for m in MEDS], fontsize=8, color=INK)
    ax.set_yticks(range(len(CONDITION_ORDER)),
                  [CONDITION_LABELS[c] for c in CONDITION_ORDER],
                  fontsize=8, color=INK)
    for i, cond in enumerate(CONDITION_ORDER):
        for j, med in enumerate(MEDS):
            v = data[i][j]
            ax.text(j, i, f"{v * 100:.0f}", ha="center", va="center", fontsize=8,
                    color="#ffffff" if v > 0.55 else INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.ax.tick_params(colors=INK2, labelsize=7)
    cb.outline.set_visible(False)
    ax.set_title(f"Detection rate (%) by condition — {tag}",
                 color=INK, fontsize=11, pad=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / f"heatmap_{tag}.png", facecolor=SURFACE)
    plt.close(fig)


def fig_lamp_recovery(cells, model):
    """The money figure: evening-dim pair, per med, lamp off vs on."""
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=180)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    x = range(len(MEDS))
    off = [rate(cells, model, "evening_dim", m) * 100 for m in MEDS]
    on = [rate(cells, model, "evening_dim_lamp", m) * 100 for m in MEDS]
    w = 0.38
    ax.bar([i - w / 2 for i in x], off, w, color=SERIES[0], edgecolor=SURFACE,
           linewidth=1.5, label="screens only")
    ax.bar([i + w / 2 for i in x], on, w, color=SERIES[1], edgecolor=SURFACE,
           linewidth=1.5, label="+ LED lamp")
    for i in x:
        ax.text(i - w / 2, off[i] + 2, f"{off[i]:.0f}", ha="center", fontsize=7, color=INK2)
        ax.text(i + w / 2, on[i] + 2, f"{on[i]:.0f}", ha="center", fontsize=7, color=INK)
    ax.set_xticks(list(x), [m.replace("_", "\n") for m in MEDS], fontsize=8, color=INK)
    ax.set_ylim(0, 124)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("detection rate (%)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper center", ncols=2, labelcolor=INK)
    ax.set_title("Active illumination ablation — evening dim, per medication",
                 color=INK, fontsize=11, pad=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "lamp_recovery.png", facecolor=SURFACE)
    plt.close(fig)


def fig_model_arms(cells, models):
    """Overall single-scene accuracy per condition, one series per model arm."""
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=180)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    n = len(models)
    w = 0.8 / n
    for k, model in enumerate(models):
        vals = []
        for c in CONDITION_ORDER:
            hs = ns = 0
            for m in MEDS:
                h, cnt = cells.get((model, c, m), (0, 0))
                hs, ns = hs + h, ns + cnt
            vals.append(hs / ns * 100 if ns else float("nan"))
        xs = [i - 0.4 + w * (k + 0.5) for i in range(len(CONDITION_ORDER))]
        ax.bar(xs, vals, w, color=SERIES[k], edgecolor=SURFACE, linewidth=1.5,
               label={"best": "v2", "best_v1_backup": "v1", "best_v3syn": "v3 (+synthetic)"}.get(model, model))
    ax.set_xticks(range(len(CONDITION_ORDER)),
                  [CONDITION_LABELS[c] for c in CONDITION_ORDER],
                  fontsize=7.5, color=INK)
    ax.set_ylim(0, 105)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("mean detection rate (%)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK)
    ax.set_title("Model arms across the condition grid (single-bottle scenes)",
                 color=INK, fontsize=11, pad=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "model_arms.png", facecolor=SURFACE)
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cells, models = load()
    primary = "best" if "best" in models else models[0]
    fig_heatmap(cells, primary, primary)
    fig_lamp_recovery(cells, primary)
    fig_model_arms(cells, models)
    print(f"figures -> {OUT}/ (models: {models})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
