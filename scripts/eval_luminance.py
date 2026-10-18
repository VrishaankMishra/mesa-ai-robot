#!/usr/bin/env python3
"""Scene luminance for every captured eval session, any site -> one CSV.

Sessions captured since ``--site`` existed carry ``scene.json`` from ``eval_capture.py``
(the empty table at session start). Older sessions get one computed here from frame 00
of each single-bottle cell — the mid-swap frame the analyzer skips, which is mostly
table — and are marked ``source=retro_frame00`` so the two are never confused. Every
``scene.json`` is then gathered into one CSV that ``eval_stats.py`` uses as the
illumination ordinate for the lighting-trend test.

    .venv/bin/python scripts/eval_luminance.py --eval-dir eval_data \
        --out docs/eval/scene_luminance.csv

Runs where the frames are (the Pi); the CSV is small and gets committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_analyze import DEFAULT_SITE, find_manifests, site_for  # noqa: E402

FIELDS = ["site", "condition", "session", "median_gray", "blown_pct", "dark_pct", "source"]


def gray_stats(grays) -> dict:
    """Median of per-frame median grey, pooled blown/dark fractions. Pure, unit-testable."""
    import numpy as np
    medians = [float(np.median(g)) for g in grays]
    blown = [100.0 * float((np.asarray(g) > 250).mean()) for g in grays]
    dark = [100.0 * float((np.asarray(g) < 20).mean()) for g in grays]
    return {"median_gray": statistics.median(medians),
            "blown_pct": statistics.fmean(blown), "dark_pct": statistics.fmean(dark)}


def retro_scene(sess_dir: Path, rows: list[dict]) -> dict | None:
    import cv2
    grays = []
    for r in rows:
        if r["scene"] != "single" or not r["filename"].endswith("__00.jpg"):
            continue
        img = cv2.imread(str(sess_dir / r["filename"]), cv2.IMREAD_GRAYSCALE)
        if img is not None:
            grays.append(img)
    if not grays:
        return None
    return {**gray_stats(grays), "source": "retro_frame00", "frames": len(grays)}


def main() -> int:
    p = argparse.ArgumentParser(description="Per-session scene luminance -> CSV")
    p.add_argument("--eval-dir", default="eval_data")
    p.add_argument("--out", default="docs/eval/scene_luminance.csv")
    p.add_argument("--default-site", default=DEFAULT_SITE)
    args = p.parse_args()

    eval_dir = Path(args.eval_dir)
    manifests = find_manifests(eval_dir)
    if not manifests:
        print(f"no sessions under {eval_dir}")
        return 1

    out_rows = []
    for mpath in manifests:
        sess_dir = mpath.parent
        with open(mpath) as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        site = site_for(mpath, rows[0], eval_dir, args.default_site)
        scene_path = sess_dir / "scene.json"
        if scene_path.exists():
            scene = json.loads(scene_path.read_text())
            scene.setdefault("source", "capture_start")
        else:
            scene = retro_scene(sess_dir, rows)
            if scene is None:
                print(f"skip {sess_dir}: no frame-00 images")
                continue
            scene.update(site=site if site != args.default_site else "",
                         condition=rows[0]["condition"], session=rows[0]["session"])
            scene_path.write_text(json.dumps(scene, indent=2) + "\n")
        out_rows.append({"site": site, "condition": rows[0]["condition"],
                         "session": rows[0]["session"],
                         "median_gray": f"{scene['median_gray']:.1f}",
                         "blown_pct": f"{scene['blown_pct']:.2f}",
                         "dark_pct": f"{scene['dark_pct']:.2f}",
                         "source": scene["source"]})
        print(f"{site:14s} {rows[0]['condition']:20s} gray {scene['median_gray']:5.1f}  "
              f"blown {scene['blown_pct']:5.2f}%  ({scene['source']})")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(out_rows)} sessions -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
