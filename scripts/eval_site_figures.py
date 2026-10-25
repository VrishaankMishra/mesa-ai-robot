#!/usr/bin/env python3
"""Two-site figures for the domain-shift replication (home_office vs family_room).

Reads the per-frame results CSVs from ``eval_analyze.py`` for both sites and writes
report-ready PNGs to docs/eval/figures/two_site/:

- ``heatmaps_two_site.png`` — condition × medication detection rate for each site over
  the four shared conditions (deployed arm), with the cell-for-cell difference
  (family_room minus home_office) as a third, diverging panel; \\* marks a cell whose
  Newcombe 95% interval excludes zero.
- ``lamp_lift_two_site.png`` — pooled lamp-off vs lamp-on rate per site for the midday
  and evening-dim pairs (Wilson 95% bars), and the lift in percentage points with its
  Newcombe 95% interval.
- ``model_arms_family_room.png`` — pooled rate per model arm over the family room's four
  comparable cells (Wilson 95% bars).

    .venv/bin/python scripts/eval_site_figures.py
    .venv/bin/python scripts/eval_site_figures.py --numbers   # print the plotted values

Rows with no ``site`` column (the original grid) belong to the default site. The
family room's extra conditions (``afternoon_blinds_*``, the ``*_pilot_*`` geometry
pilot) are not part of the shared grid and are skipped. Intervals come from
``eval_stats.py`` (Wilson, Newcombe); the aggregation helpers here are pure and tested
in tests/test_eval_site_figures.py.

Design follows ``eval_figures.py``: sequential single-hue ramp for magnitude, a two-hue
diverging ramp with a neutral midpoint for the signed delta, fixed-order categorical hues
for site / arm identity, values labelled in ink, one axis per chart, recessive grid,
Agg backend, 180 dpi.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_stats import newcombe_diff_ci, wilson_ci  # noqa: E402

CSVS = [Path("docs/eval/domain_shift_results.csv"),
        Path("docs/eval/domain_shift_results_family_room.csv")]
OUT = Path("docs/eval/figures/two_site")
DEFAULT_SITE = "home_office"
SITES = ["home_office", "family_room"]          # fixed order = fixed hue
SITE_LABELS = {"home_office": "site A — home office", "family_room": "site B — family room"}
DEPLOYED = "best"
ARMS = ["best", "best_v1_backup", "best_v3syn"]  # fixed order = fixed hue
ARM_LABELS = {"best": "v2 (deployed)", "best_v1_backup": "v1", "best_v3syn": "v3 (+synthetic)"}
ARM_SHORT = {"best": "v2", "best_v1_backup": "v1", "best_v3syn": "v3syn"}

# Validated reference palette (light mode), as in eval_figures.py.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e6e5e2"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed order, never cycled
SEQ_CMAP = LinearSegmentedColormap.from_list("blue_seq", ["#eef4fc", "#1c5aa8"])
# Diverging: warm pole (family room worse) — neutral grey — cool pole (family room better).
DIV_CMAP = LinearSegmentedColormap.from_list("div", ["#c2410c", "#f0efec", "#1c5aa8"])

SHARED_CONDITIONS = ["midday_lamps_off", "midday_lamp_added", "evening_dim", "evening_dim_lamp"]
CONDITION_LABELS = {
    "midday_lamps_off": "midday",
    "midday_lamp_added": "midday\n+ lamp",
    "evening_dim": "evening dim",
    "evening_dim_lamp": "evening dim\n+ lamp",
}
LAMP_PAIRS = [("midday_lamps_off", "midday_lamp_added", "midday"),
              ("evening_dim", "evening_dim_lamp", "evening dim")]
MEDS = ["mylanta", "vitamin_d3", "bayer_aspirin", "cvs_allergy",
        "omeprazole", "melatonin", "ashwagandha", "advil"]
SKIP_PREFIXES = ("afternoon_blinds",)
SKIP_MARKERS = ("_pilot_",)

Cells = dict  # (site, model, condition, medication, mark_m) -> [hits, n]  (single scenes)


# ----------------------------------------------------------------------------- aggregation

def is_grid_condition(cond: str) -> bool:
    """Shared-grid condition? False for the family room's afternoon pair and any pilot."""
    if cond.startswith(SKIP_PREFIXES):
        return False
    return not any(m in cond for m in SKIP_MARKERS)


def load_cells(paths: list[Path], default_site: str = DEFAULT_SITE) -> Cells:
    """Single-scene hits/n per (site, model, condition, medication, mark). Site-less rows
    belong to ``default_site``; non-grid conditions are dropped."""
    cells: Cells = defaultdict(lambda: [0, 0])
    for path in paths:
        with open(path) as f:
            for r in csv.DictReader(f):
                if r["scene"] != "single" or not is_grid_condition(r["condition"]):
                    continue
                site = r.get("site") or default_site
                key = (site, r["model"], r["condition"], r["ground_truth"], r["mark_m"])
                cells[key][0] += int(r["correct"])
                cells[key][1] += 1
    return cells


def counts(cells: Cells, site: str, model: str, cond: str,
           med: str | None = None, mark: str | None = None) -> tuple[int, int]:
    """Pooled (hits, n); ``med``/``mark`` None pool over that axis."""
    k = n = 0
    for (s, mo, c, g, mk), (h, cnt) in cells.items():
        if s == site and mo == model and c == cond \
                and (med is None or g == med) and (mark is None or mk == mark):
            k, n = k + h, n + cnt
    return k, n


def rate(k: int, n: int) -> float:
    return k / n if n else float("nan")


def rate_matrix(cells: Cells, site: str, model: str = DEPLOYED,
                conds: list[str] = SHARED_CONDITIONS, meds: list[str] = MEDS) -> list[list[float]]:
    """Rows = conditions, columns = medications; nan where a cell is missing."""
    return [[rate(*counts(cells, site, model, c, m)) for m in meds] for c in conds]


def delta_matrix(cells: Cells, site: str, ref: str, model: str = DEPLOYED,
                 conds: list[str] = SHARED_CONDITIONS,
                 meds: list[str] = MEDS) -> list[list[tuple[float, bool]]]:
    """Cell-for-cell (site − ref) as (delta, excludes_zero) with Newcombe 95% intervals."""
    out = []
    for c in conds:
        row = []
        for m in meds:
            k1, n1 = counts(cells, site, model, c, m)
            k0, n0 = counts(cells, ref, model, c, m)
            d, lo, hi = newcombe_diff_ci(k1, n1, k0, n0)
            row.append((d, (not math.isnan(d)) and (lo > 0.005 or hi < -0.005)))
        out.append(row)
    return out


def pooled_ci(cells: Cells, site: str, model: str, cond: str,
              mark: str | None = None) -> tuple[float, float, float, int, int]:
    """(rate, lo, hi, hits, n) pooled over medications, Wilson 95%."""
    k, n = counts(cells, site, model, cond, mark=mark)
    lo, hi = wilson_ci(k, n)
    return rate(k, n), lo, hi, k, n


def lamp_lift(cells: Cells, site: str, off: str, on: str,
              model: str = DEPLOYED) -> tuple[float, float, float]:
    """Pooled lamp-on minus lamp-off (d, lo, hi), Newcombe 95%."""
    k1, n1 = counts(cells, site, model, on)
    k0, n0 = counts(cells, site, model, off)
    return newcombe_diff_ci(k1, n1, k0, n0)


def cross_site_delta(cells: Cells, site: str, ref: str, cond: str, mark: str | None = None,
                     model: str = DEPLOYED) -> tuple[float, float, float]:
    """Pooled (site − ref) at one condition, optionally one mark; Newcombe 95%."""
    k1, n1 = counts(cells, site, model, cond, mark=mark)
    k0, n0 = counts(cells, ref, model, cond, mark=mark)
    return newcombe_diff_ci(k1, n1, k0, n0)


def arms_in(cells: Cells, site: str) -> list[str]:
    found = {mo for s, mo, _, _, _ in cells if s == site}
    return [a for a in ARMS if a in found] + sorted(found - set(ARMS))


# ----------------------------------------------------------------------------- drawing

def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8, length=0)


def _heat_panel(ax, data, cmap, vmin, vmax, labels, title, conds=SHARED_CONDITIONS, meds=MEDS):
    im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(meds)), [m.replace("_", " ") for m in meds], fontsize=7, color=INK,
                  rotation=35, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(len(conds)), [CONDITION_LABELS[c] for c in conds], fontsize=7.5, color=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    for i in range(len(conds)):
        for j in range(len(meds)):
            txt, dark = labels[i][j]
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="#ffffff" if dark else INK)
    ax.set_title(title, color=INK, fontsize=9.5, pad=8, loc="left")
    return im


def fig_heatmaps(cells: Cells, site: str = "family_room", ref: str = DEFAULT_SITE,
                 model: str = DEPLOYED):
    fig, axes = plt.subplots(1, 3, figsize=(14.6, 3.9), dpi=180,
                             gridspec_kw={"width_ratios": [1, 1, 1.08]})
    fig.patch.set_facecolor(SURFACE)
    for ax, s in zip(axes[:2], (ref, site)):
        data = rate_matrix(cells, s, model)
        labels = [[("—" if math.isnan(v) else f"{v * 100:.0f}", (not math.isnan(v)) and v > 0.55)
                   for v in row] for row in data]
        im = _heat_panel(ax, data, SEQ_CMAP, 0, 1, labels,
                         f"Detection rate (%) — {SITE_LABELS.get(s, s)}")
    cb = fig.colorbar(im, ax=axes[1], fraction=0.04, pad=0.02, ticks=[0, 0.25, 0.5, 0.75, 1])
    cb.ax.set_yticklabels(["0", "25", "50", "75", "100"])
    cb.ax.tick_params(colors=INK2, labelsize=6.5)
    cb.outline.set_visible(False)

    deltas = delta_matrix(cells, site, ref, model)
    data = [[d for d, _ in row] for row in deltas]
    labels = [[("—" if math.isnan(d) else f"{d * 100:+.0f}" + ("*" if flag else ""),
                (not math.isnan(d)) and abs(d) > 0.55) for d, flag in row] for row in deltas]
    im2 = _heat_panel(axes[2], data, DIV_CMAP, -1, 1, labels,
                      "Difference, site B − site A (pp); * = 95% CI excludes 0")
    cb2 = fig.colorbar(im2, ax=axes[2], fraction=0.04, pad=0.02, ticks=[-1, -0.5, 0, 0.5, 1])
    cb2.ax.set_yticklabels(["−100", "−50", "0", "+50", "+100"])
    cb2.ax.tick_params(colors=INK2, labelsize=6.5)
    cb2.outline.set_visible(False)
    fig.suptitle(f"Deployed arm {ARM_SHORT.get(model, model)}, single-bottle scenes, "
                 "four shared lighting conditions, N = 22 frames per cell", color=INK2, fontsize=8.5, x=0.01,
                 ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "heatmaps_two_site.png", facecolor=SURFACE)
    plt.close(fig)


def fig_lamp_lift(cells: Cells, model: str = DEPLOYED, sites: list[str] = SITES):
    fig, (ax_r, ax_d) = plt.subplots(1, 2, figsize=(10.4, 3.6), dpi=180,
                                     gridspec_kw={"width_ratios": [1.45, 1]})
    fig.patch.set_facecolor(SURFACE)
    for ax in (ax_r, ax_d):
        style_axes(ax)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)

    # Left: pooled rates, lamp off (hollow) and lamp on (solid), hue = site.
    w = 0.19
    centres = list(range(len(LAMP_PAIRS)))
    for si, site in enumerate(sites):
        colour = SERIES[si]
        for pi, (off, on, _) in enumerate(LAMP_PAIRS):
            for li, (cond, solid) in enumerate(((off, False), (on, True))):
                r, lo, hi, _, n = pooled_ci(cells, site, model, cond)
                if not n:
                    continue
                x = centres[pi] - 0.4 + w * (si * 2 + li + 0.5)
                ax_r.bar(x, r * 100, w * 0.92, color=colour if solid else SURFACE,
                         edgecolor=colour, linewidth=1.4)
                ax_r.errorbar(x, r * 100, yerr=[[(r - lo) * 100], [(hi - r) * 100]],
                              fmt="none", ecolor=INK2, elinewidth=0.9, capsize=2)
                ax_r.text(x, hi * 100 + 2.5, f"{r * 100:.0f}", ha="center", fontsize=7, color=INK)
    ax_r.set_xticks(centres, [lab for _, _, lab in LAMP_PAIRS], fontsize=8.5, color=INK)
    ax_r.set_ylim(0, 134)
    ax_r.set_ylabel("pooled detection rate (%)", color=INK2, fontsize=9)
    ax_r.set_title("Lamp off (hollow) vs lamp on (solid), Wilson 95%",
                   color=INK, fontsize=9.5, pad=8, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[i]) for i in range(len(sites))]
    ax_r.legend(handles, [SITE_LABELS.get(s, s) for s in sites], frameon=False, fontsize=7.5,
                loc="upper center", ncols=2, labelcolor=INK)

    # Right: the lift in pp with its Newcombe interval.
    w2 = 0.3
    ax_d.axhline(0, color=INK2, linewidth=0.8)
    for si, site in enumerate(sites):
        for pi, (off, on, _) in enumerate(LAMP_PAIRS):
            d, lo, hi = lamp_lift(cells, site, off, on, model)
            if math.isnan(d):
                continue
            x = centres[pi] - w2 / 2 + w2 * si
            ax_d.bar(x, d * 100, w2 * 0.88, color=SERIES[si], edgecolor=SURFACE, linewidth=1.2)
            ax_d.errorbar(x, d * 100, yerr=[[(d - lo) * 100], [(hi - d) * 100]],
                          fmt="none", ecolor=INK, elinewidth=1.0, capsize=3)
            ytxt = hi * 100 + 2 if d >= 0 else lo * 100 - 2
            ax_d.text(x, ytxt, f"{d * 100:+.0f}", ha="center",
                      va="bottom" if d >= 0 else "top", fontsize=7.5, color=INK)
    ax_d.set_xticks(centres, [lab for _, _, lab in LAMP_PAIRS], fontsize=8.5, color=INK)
    ax_d.set_ylabel("lamp on − lamp off (pp)", color=INK2, fontsize=9)
    ax_d.set_title("Lift with Newcombe 95% interval", color=INK, fontsize=9.5, pad=8, loc="left")
    lo_all = min(ax_d.get_ylim()[0], -32)
    ax_d.set_ylim(lo_all, max(ax_d.get_ylim()[1], 40))
    fig.suptitle(f"Active illumination at two sites — deployed arm {ARM_SHORT.get(model, model)}, "
                 "single-bottle scenes pooled over 8 medications (N = 176 per bar)", color=INK2, fontsize=8.5,
                 x=0.01, ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "lamp_lift_two_site.png", facecolor=SURFACE)
    plt.close(fig)


def fig_model_arms(cells: Cells, site: str = "family_room", conds: list[str] = SHARED_CONDITIONS):
    arms = arms_in(cells, site)
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=180)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    w = 0.8 / max(len(arms), 1)
    for k, arm in enumerate(arms):
        for i, c in enumerate(conds):
            r, lo, hi, _, n = pooled_ci(cells, site, arm, c)
            if not n:
                continue
            x = i - 0.4 + w * (k + 0.5)
            ax.bar(x, r * 100, w * 0.9, color=SERIES[k % len(SERIES)], edgecolor=SURFACE,
                   linewidth=1.2, label=ARM_LABELS.get(arm, arm) if i == 0 else None)
            ax.errorbar(x, r * 100, yerr=[[(r - lo) * 100], [(hi - r) * 100]], fmt="none",
                        ecolor=INK2, elinewidth=0.9, capsize=2)
            ax.text(x, hi * 100 + 2, f"{r * 100:.0f}", ha="center", fontsize=7, color=INK)
    ax.set_xticks(range(len(conds)), [CONDITION_LABELS[c] for c in conds], fontsize=8, color=INK)
    ax.set_ylim(0, 105)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("pooled detection rate (%)", color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK)
    ax.set_title(f"Model arms — {SITE_LABELS.get(site, site)}, four comparable cells "
                 "(single-bottle scenes, Wilson 95%)", color=INK, fontsize=10, pad=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "model_arms_family_room.png", facecolor=SURFACE)
    plt.close(fig)


# ----------------------------------------------------------------------------- numbers

def _pct(d, lo, hi):
    return f"{100 * d:+.0f} pp [{100 * lo:+.0f}, {100 * hi:+.0f}]"


def print_numbers(cells: Cells, site: str = "family_room", ref: str = DEFAULT_SITE,
                  model: str = DEPLOYED) -> None:
    """The values behind the figures, for cross-checking against site_stats.md."""
    print(f"# plotted values — arm {model}; {ref} vs {site}; conditions {SHARED_CONDITIONS}")
    for s in (ref, site):
        print(f"\n## {s}: pooled rate per shared condition (Wilson 95%)")
        for c in SHARED_CONDITIONS:
            r, lo, hi, k, n = pooled_ci(cells, s, model, c)
            if n:
                print(f"  {c:<20} {100 * r:5.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]  ({k}/{n})")
        for mark in ("0.6", "0.8"):
            print(f"  -- mark {mark} m")
            for c in SHARED_CONDITIONS:
                r, lo, hi, k, n = pooled_ci(cells, s, model, c, mark=mark)
                if n:
                    print(f"  {c:<20} {100 * r:5.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]  ({k}/{n})")
    print(f"\n## cross-site delta {site} − {ref} (Newcombe 95%)")
    for c in SHARED_CONDITIONS:
        print(f"  {c:<20} pooled  {_pct(*cross_site_delta(cells, site, ref, c, model=model))}")
        for mark in ("0.6", "0.8"):
            d = cross_site_delta(cells, site, ref, c, mark=mark, model=model)
            if not math.isnan(d[0]):
                print(f"  {'':<20} mark {mark}  {_pct(*d)}")
    print("\n## lamp lift, pooled (Newcombe 95%)")
    for s in (ref, site):
        for off, on, lab in LAMP_PAIRS:
            d = lamp_lift(cells, s, off, on, model)
            if not math.isnan(d[0]):
                print(f"  {s:<12} {lab:<12} {_pct(*d)}")
    print(f"\n## model arms, {site}, pooled per shared condition (Wilson 95%)")
    for arm in arms_in(cells, site):
        for c in SHARED_CONDITIONS:
            r, lo, hi, k, n = pooled_ci(cells, site, arm, c)
            if n:
                print(f"  {arm:<15} {c:<20} {100 * r:5.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]  ({k}/{n})")
    flagged = sum(f for row in delta_matrix(cells, site, ref, model) for _, f in row)
    print(f"\n## delta cells with 95% interval excluding zero: {flagged} of "
          f"{len(SHARED_CONDITIONS) * len(MEDS)}")


def main() -> int:
    global OUT
    p = argparse.ArgumentParser(description="Two-site figures from the results CSVs")
    p.add_argument("--csv", nargs="+", default=[str(c) for c in CSVS])
    p.add_argument("--site", default="family_room", help="replication site")
    p.add_argument("--reference-site", default=DEFAULT_SITE)
    p.add_argument("--model", default=DEPLOYED, help="deployed arm for the heatmaps and lamp figure")
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--numbers", action="store_true", help="print the plotted values and exit")
    args = p.parse_args()
    OUT = Path(args.out)
    cells = load_cells([Path(c) for c in args.csv], args.reference_site)
    sites = {s for s, _, _, _, _ in cells}
    missing = {args.site, args.reference_site} - sites
    if missing:
        print(f"no single-scene rows for site(s) {sorted(missing)} in {args.csv}")
        return 1
    if args.numbers:
        print_numbers(cells, args.site, args.reference_site, args.model)
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    fig_heatmaps(cells, args.site, args.reference_site, args.model)
    fig_lamp_lift(cells, args.model, [args.reference_site, args.site])
    fig_model_arms(cells, args.site)
    print(f"figures -> {OUT}/ (sites: {args.reference_site}, {args.site}; arms: "
          f"{arms_in(cells, args.site)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
