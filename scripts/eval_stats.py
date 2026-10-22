#!/usr/bin/env python3
"""Statistics pass over the domain-shift results — any number of sites.

Reads one or more tidy CSVs from ``eval_analyze.py`` and writes a markdown report:

- Wilson 95% intervals on every reported rate (per cell, per condition, unknown probe,
  group scene), per site;
- a lighting-trend test per site: Cochran–Armitage linear trend of the pooled
  single-scene rate over measured scene luminance (``eval_luminance.py``);
- the paired lamp analysis per site: lamp on vs off at the same time of day, per
  medication, with Newcombe score intervals on the difference and an exact sign test
  across medications;
- for every site beyond the reference, a cell-for-cell replication table against the
  reference plus a summary: rank agreement of the condition profile, worst condition,
  lamp lift, open-set rejection at the dark and bright ends.

    .venv/bin/python scripts/eval_stats.py \
        --results docs/eval/domain_shift_results.csv \
        --luminance docs/eval/scene_luminance.csv \
        --model best --reference-site home_office --out docs/eval/site_stats.md

Rows without a ``site`` column (the CSV committed before sites existed) belong to the
reference site. The statistics are pure functions, unit-tested in
tests/test_eval_stats.py; stdlib only, so this runs on the Pi as well.

Caveat written into every report: frames within a cell share one placement, so the
per-frame N (22) overstates the independent evidence and cell intervals are optimistic.
Condition-level and lamp-pair statistics pool cells and are the ones to lean on.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

Z95 = 1.959963984540054
DEFAULT_SITE = "home_office"
NAN = float("nan")

CONDITION_ORDER = [
    "morning_lamps_off", "morning_lamps_on",
    "midday_lamps_off", "midday_lamp_added",
    "afternoon_blinds_dim", "afternoon_blinds_dim_lamp",   # family_room extra, Oct 19
    "evening_lights_on", "evening_lamp_added",
    "evening_dim", "evening_dim_lamp",
]
MEDS_ORDER = ["mylanta", "vitamin_d3", "bayer_aspirin", "cvs_allergy",
              "omeprazole", "melatonin", "ashwagandha", "advil"]
# (lamp off, lamp on, label): same time of day, only the lamp differs.
LAMP_PAIRS = [
    ("midday_lamps_off", "midday_lamp_added", "midday"),
    ("afternoon_blinds_dim", "afternoon_blinds_dim_lamp", "afternoon, blinds closed"),
    ("evening_lights_on", "evening_lamp_added", "evening, lights on"),
    ("evening_dim", "evening_dim_lamp", "evening dim"),
]


# ----------------------------------------------------------------------------- statistics

def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. (nan, nan) when n == 0."""
    if n <= 0:
        return (NAN, NAN)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int,
                     z: float = Z95) -> tuple[float, float, float]:
    """Difference p1 - p2 with Newcombe's hybrid-score interval -> (d, lo, hi)."""
    if n1 <= 0 or n2 <= 0:
        return (NAN, NAN, NAN)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1, z)
    l2, u2 = wilson_ci(k2, n2, z)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (d, max(-1.0, lo), min(1.0, hi))


def two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2)) if not math.isnan(z) else NAN


def cochran_armitage(groups: list[tuple[int, int, float]]) -> tuple[float, float]:
    """Linear trend of a proportion over ordered groups.

    groups: (hits, n, score) per condition; score is the illumination ordinate.
    Returns (z, two-sided p); z > 0 means the rate rises with the score. (nan, nan) when
    the trend is undefined (one group, constant score, or all-hit / all-miss overall).
    """
    groups = [g for g in groups if g[1] > 0]
    N = sum(n for _, n, _ in groups)
    if len(groups) < 2 or N == 0:
        return (NAN, NAN)
    p_bar = sum(k for k, _, _ in groups) / N
    if p_bar in (0.0, 1.0):
        return (NAN, NAN)
    t = sum(s * (k - n * p_bar) for k, n, s in groups)
    s_mean = sum(n * s for _, n, s in groups) / N
    var = p_bar * (1 - p_bar) * sum(n * (s - s_mean) ** 2 for _, n, s in groups)
    if var <= 0:
        return (NAN, NAN)
    z = t / math.sqrt(var)
    return (z, two_sided_p(z))


def sign_test(deltas: list[float], eps: float = 1e-12) -> tuple[int, int, int, float]:
    """Exact two-sided sign test -> (positive, negative, ties, p). p is nan with no non-ties."""
    pos = sum(1 for d in deltas if d > eps)
    neg = sum(1 for d in deltas if d < -eps)
    ties = len(deltas) - pos - neg
    n = pos + neg
    if n == 0:
        return (pos, neg, ties, NAN)
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return (pos, neg, ties, min(1.0, 2 * tail))


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for idx in order[i:j + 1]:
            ranks[idx] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation (average ranks for ties); nan below 3 pairs or no spread."""
    if len(xs) != len(ys) or len(xs) < 3:
        return NAN
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return NAN
    return cov / math.sqrt(vx * vy)


# ----------------------------------------------------------------------------- data

Cells = dict  # (site, condition, scene, ground_truth) -> [hits, n]


def load_results(paths: list[Path], model: str, default_site: str = DEFAULT_SITE) -> Cells:
    """Aggregate per-frame rows of one model arm into cells. Site-less rows -> default."""
    cells: Cells = defaultdict(lambda: [0, 0])
    for path in paths:
        with open(path) as f:
            for r in csv.DictReader(f):
                if r["model"] != model:
                    continue
                site = r.get("site") or default_site
                key = (site, r["condition"], r["scene"], r["ground_truth"])
                cells[key][0] += int(r["correct"])
                cells[key][1] += 1
    return cells


def load_luminance(path: Path | None, default_site: str = DEFAULT_SITE) -> dict:
    """(site, condition) -> {"gray": mean median grey, "blown": mean blown %} over sessions."""
    if path is None or not Path(path).exists():
        return {}
    acc: dict = defaultdict(lambda: {"gray": [], "blown": []})
    with open(path) as f:
        for r in csv.DictReader(f):
            if r.get("median_gray", "") == "":
                continue
            key = (r.get("site") or default_site, r["condition"])
            acc[key]["gray"].append(float(r["median_gray"]))
            acc[key]["blown"].append(float(r.get("blown_pct") or 0.0))
    return {k: {"gray": sum(v["gray"]) / len(v["gray"]),
                "blown": sum(v["blown"]) / len(v["blown"])} for k, v in acc.items()}


def sites_in(cells: Cells) -> list[str]:
    return sorted({s for s, _, _, _ in cells})


def ordered(found: set[str], canonical: list[str]) -> list[str]:
    return [c for c in canonical if c in found] + sorted(found - set(canonical))


def conditions_in(cells: Cells, site: str) -> list[str]:
    return ordered({c for s, c, _, _ in cells if s == site}, CONDITION_ORDER)


def meds_in(cells: Cells, site: str) -> list[str]:
    return ordered({g for s, _, sc, g in cells if s == site and sc == "single"}, MEDS_ORDER)


def cell(cells: Cells, site: str, cond: str, scene: str, gt: str) -> tuple[int, int]:
    k, n = cells.get((site, cond, scene, gt), (0, 0))
    return k, n


def pooled_single(cells: Cells, site: str, cond: str) -> tuple[int, int]:
    k = n = 0
    for (s, c, sc, _), (h, cnt) in cells.items():
        if s == site and c == cond and sc == "single":
            k, n = k + h, n + cnt
    return k, n


def probe(cells: Cells, site: str, cond: str) -> tuple[int, int]:
    k = n = 0
    for (s, c, sc, _), (h, cnt) in cells.items():
        if s == site and c == cond and sc == "unknown":
            k, n = k + h, n + cnt
    return k, n


def group(cells: Cells, site: str, cond: str) -> tuple[int, int]:
    k = n = 0
    for (s, c, sc, _), (h, cnt) in cells.items():
        if s == site and c == cond and sc == "group":
            k, n = k + h, n + cnt
    return k, n


# ----------------------------------------------------------------------------- report

def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "—"
    lo, hi = wilson_ci(k, n)
    return f"{100 * k / n:.0f} [{100 * lo:.0f}–{100 * hi:.0f}]"


def excludes_zero(lo: float, hi: float, tol: float = 0.005) -> bool:
    """Interval clear of zero by more than half a point — consistent with the integer display."""
    return lo > tol or hi < -tol


def fmt_delta(k1: int, n1: int, k2: int, n2: int) -> str:
    d, lo, hi = newcombe_diff_ci(k1, n1, k2, n2)
    if math.isnan(d):
        return "—"
    mark = " \\*" if excludes_zero(lo, hi) else ""
    return f"{100 * d:+.0f} [{100 * lo:+.0f}, {100 * hi:+.0f}]{mark}"


def fmt_p(p: float) -> str:
    if math.isnan(p):
        return "n/a"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


def site_section(cells: Cells, site: str, lum: dict) -> list[str]:
    conds, meds = conditions_in(cells, site), meds_in(cells, site)
    out = [f"## Site `{site}`", ""]
    frames = sum(n for (s, _, sc, _), (_, n) in cells.items() if s == site and sc == "single")
    out.append(f"{len(conds)} conditions × {len(meds)} medications, "
               f"{frames} scored single-scene frames. Rates in %, Wilson 95% interval in brackets.")
    out.append("")

    out.append(f"### Detection rate by condition × medication (`{site}`)")
    out.append("")
    rows = []
    for c in conds:
        row = [c] + [fmt_rate(*cell(cells, site, c, "single", m)) for m in meds]
        row.append(f"**{fmt_rate(*pooled_single(cells, site, c))}**")
        rows.append(row)
    out += table(["condition"] + meds + ["pooled"], rows)

    out.append(f"### Unknown probe and group scene (`{site}`)")
    out.append("")
    rows = []
    for c in conds:
        pk, pn = probe(cells, site, c)
        gk, gn = group(cells, site, c)
        scene = lum.get((site, c))
        rows.append([c, f"{scene['gray']:.0f}" if scene else "—",
                     f"{scene['blown']:.1f}" if scene else "—",
                     fmt_rate(pk, pn) + (f" (n={pn})" if pn else ""),
                     fmt_rate(gk, gn) + (f" (n={gn})" if gn else "")])
    out += table(["condition", "median gray", "blown %", "probe rejected", "group ≥75% recall"],
                 rows)

    # Lighting trend over measured luminance.
    out.append(f"### Lighting trend (`{site}`)")
    out.append("")
    groups = []
    for c in conds:
        scene = lum.get((site, c))
        if scene is None:
            continue
        k, n = pooled_single(cells, site, c)
        groups.append((k, n, scene["gray"]))
    if len(groups) >= 2:
        z, p = cochran_armitage(groups)
        out.append(f"Cochran–Armitage linear trend of the pooled single-scene rate over whole-frame "
                   f"median grey ({len(groups)} conditions, grey "
                   f"{min(g[2] for g in groups):.0f}–{max(g[2] for g in groups):.0f}): "
                   f"z = {z:+.2f}, p = {fmt_p(p)}.")
        out.append("")
        out.append("Read the sign with care. Median grey is a whole-frame statistic: a direct-sun "
                   "beam across the table in an otherwise dark room reads as *dark* here (its "
                   "signature is the blown-highlight fraction in the table above), so this ordinate "
                   "sorts the beam cells next to the dim cells, and a positive z says only that the "
                   "dark-reading cells are the failing ones — not that more light is always better. "
                   "A linear trend cannot describe a two-sided collapse; the test is reported for "
                   "completeness, the per-condition table is the finding.")
        by_rate = sorted(groups, key=lambda g: g[0] / g[1])
        worst, best = by_rate[0], by_rate[-1]
        out.append("")
        out.append(f"Lowest pooled rate {100 * worst[0] / worst[1]:.0f}% at grey {worst[2]:.0f}; "
                   f"highest {100 * best[0] / best[1]:.0f}% at grey {best[2]:.0f}.")
    else:
        out.append("No scene luminance for this site — run `scripts/eval_luminance.py` on the "
                   "machine that holds `eval_data/` and pass the CSV with `--luminance`.")
    out.append("")

    # Paired lamp analysis.
    out.append(f"### Paired lamp analysis (`{site}`)")
    out.append("")
    out.append("Lamp on minus lamp off at the same time of day, in percentage points, Newcombe 95% "
               "interval; \\* marks an interval excluding zero. Sign test counts medications whose "
               "rate moved up / down.")
    out.append("")
    for off, on, label in LAMP_PAIRS:
        if off not in conds or on not in conds:
            continue
        rows, deltas = [], []
        for m in meds:
            k0, n0 = cell(cells, site, off, "single", m)
            k1, n1 = cell(cells, site, on, "single", m)
            if n0 and n1:
                deltas.append(k1 / n1 - k0 / n0)
            rows.append([m, fmt_rate(k0, n0), fmt_rate(k1, n1), fmt_delta(k1, n1, k0, n0)])
        pk0, pn0 = pooled_single(cells, site, off)
        pk1, pn1 = pooled_single(cells, site, on)
        rows.append(["**pooled**", fmt_rate(pk0, pn0), fmt_rate(pk1, pn1),
                     f"**{fmt_delta(pk1, pn1, pk0, pn0)}**"])
        pos, neg, ties, p = sign_test(deltas)
        out.append(f"**{label}** — `{off}` → `{on}`; sign test {pos} up / {neg} down / "
                   f"{ties} unchanged, p = {fmt_p(p)}")
        out.append("")
        out += table(["medication", "lamp off", "lamp on", "Δ pp"], rows)
    return out


def replication_section(cells: Cells, ref: str, site: str, lum: dict) -> list[str]:
    conds = [c for c in conditions_in(cells, ref) if c in set(conditions_in(cells, site))]
    meds = [m for m in meds_in(cells, ref) if m in set(meds_in(cells, site))]
    out = [f"## Replication: `{site}` vs `{ref}`", ""]
    if not conds:
        out.append("No shared conditions yet.")
        return out + [""]
    out.append(f"Cell-for-cell difference (`{site}` minus `{ref}`) in percentage points with "
               f"Newcombe 95% interval; \\* marks an interval excluding zero.")
    out.append("")
    rows, flagged, compared = [], [], 0
    for c in conds:
        row = [c]
        for m in meds:
            k1, n1 = cell(cells, site, c, "single", m)
            k0, n0 = cell(cells, ref, c, "single", m)
            row.append(fmt_delta(k1, n1, k0, n0))
            if n0 and n1:
                compared += 1
                d, lo, hi = newcombe_diff_ci(k1, n1, k0, n0)
                if excludes_zero(lo, hi):
                    flagged.append((c, m, d))
        pk1, pn1 = pooled_single(cells, site, c)
        pk0, pn0 = pooled_single(cells, ref, c)
        row.append(f"**{fmt_delta(pk1, pn1, pk0, pn0)}**")
        rows.append(row)
    out += table(["condition"] + meds + ["pooled"], rows)

    out.append("### Summary")
    out.append("")
    out.append(f"- Cells compared: {compared}; cells whose difference interval excludes zero: "
               f"{len(flagged)}" + (" — " + ", ".join(
                   f"{c}/{m} ({100 * d:+.0f})" for c, m, d in flagged) if flagged else "") + ".")
    ref_rates = [pooled_single(cells, ref, c) for c in conds]
    site_rates = [pooled_single(cells, site, c) for c in conds]
    rho = spearman([k / n if n else NAN for k, n in ref_rates],
                   [k / n if n else NAN for k, n in site_rates])
    out.append(f"- Condition profile agreement (Spearman ρ over {len(conds)} pooled condition "
               f"rates): {rho:.2f}." if not math.isnan(rho) else
               "- Condition profile agreement: not computable.")
    for s in (ref, site):
        rates = {c: pooled_single(cells, s, c) for c in conds}
        worst = min((c for c in conds if rates[c][1]), key=lambda c: rates[c][0] / rates[c][1])
        best = max((c for c in conds if rates[c][1]), key=lambda c: rates[c][0] / rates[c][1])
        out.append(f"- `{s}`: worst condition `{worst}` {fmt_rate(*rates[worst])}, "
                   f"best `{best}` {fmt_rate(*rates[best])}.")
    for off, on, label in LAMP_PAIRS:
        if off in conds and on in conds:
            parts = []
            for s in (ref, site):
                k0, n0 = pooled_single(cells, s, off)
                k1, n1 = pooled_single(cells, s, on)
                parts.append(f"`{s}` {fmt_delta(k1, n1, k0, n0)}")
            out.append(f"- Lamp lift, {label}: " + "; ".join(parts) + ".")
    # Open-set rejection at the dark and bright ends, by measured luminance when available.
    def _by_gray(s: str):
        with_gray = [(lum[(s, c)]["gray"], c) for c in conds
                     if (s, c) in lum and probe(cells, s, c)[1]]
        if len(with_gray) >= 2:
            with_gray.sort()
            return with_gray[0][1], with_gray[-1][1]
        return None
    for s in (ref, site):
        ends = _by_gray(s)
        if ends:
            dark, bright = ends
            out.append(f"- `{s}` probe rejection, darkest (`{dark}`) {fmt_rate(*probe(cells, s, dark))} "
                       f"vs brightest (`{bright}`) {fmt_rate(*probe(cells, s, bright))}.")
    return out + [""]


def build_report(cells: Cells, model: str, ref: str, lum: dict, sources: list[str],
                 notes: str = "") -> str:
    sites = sites_in(cells)
    out = ["# Domain-shift statistics pass", ""]
    if notes.strip():
        # Caveats the numbers cannot carry themselves (a confounded cell, a skipped
        # condition) live in a hand-written file so they survive every regeneration.
        out += ["## Notes on the data", "", notes.strip(), ""]
    out.append(f"Model arm `{model}`; sources: " + ", ".join(f"`{s}`" for s in sources) +
               f"; sites: " + ", ".join(f"`{s}`" for s in sites) + f" (reference `{ref}`).")
    out.append("")
    out.append("> Frames within a cell share one placement, so the per-frame N overstates the "
               "independent evidence and cell-level intervals are optimistic. Condition-level "
               "and lamp-pair statistics pool cells and are the ones to lean on. Generated by "
               "`scripts/eval_stats.py` — AI-assisted analysis tooling, disclosed.")
    out.append("")
    if ref in sites:
        out += site_section(cells, ref, lum)
    for s in sites:
        if s != ref:
            out += site_section(cells, s, lum)
            if ref in sites:
                out += replication_section(cells, ref, s, lum)
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Statistics pass over domain-shift results")
    p.add_argument("--results", nargs="+", default=["docs/eval/domain_shift_results.csv"],
                   help="one or more CSVs from eval_analyze.py")
    p.add_argument("--model", default="best", help="model arm (CSV `model` column)")
    p.add_argument("--reference-site", default=DEFAULT_SITE)
    p.add_argument("--luminance", default="docs/eval/scene_luminance.csv",
                   help="CSV from eval_luminance.py (optional; enables the trend test)")
    p.add_argument("--out", default="docs/eval/site_stats.md")
    p.add_argument("--notes", default="docs/eval/site_notes.md",
                   help="markdown caveats copied into the report verbatim (optional)")
    args = p.parse_args()

    paths = [Path(r) for r in args.results]
    cells = load_results(paths, args.model, args.reference_site)
    if not cells:
        print(f"no rows for model {args.model!r} in {args.results}")
        return 1
    lum = load_luminance(Path(args.luminance), args.reference_site)
    notes = Path(args.notes).read_text() if Path(args.notes).exists() else ""
    report = build_report(cells, args.model, args.reference_site, lum, args.results, notes)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    sites = sites_in(cells)
    for s in sites:
        conds = conditions_in(cells, s)
        pooled = [pooled_single(cells, s, c) for c in conds]
        k, n = sum(a for a, _ in pooled), sum(b for _, b in pooled)
        print(f"{s}: {len(conds)} conditions, overall single-scene {fmt_rate(k, n)}")
    print(f"report -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
