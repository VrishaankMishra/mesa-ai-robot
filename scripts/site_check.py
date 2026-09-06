#!/usr/bin/env python3
"""On-site readiness check for an unmeasured room (VIS-011 / demo prep).

    .venv/bin/python scripts/site_check.py --label "library room 208"

The Sept 13 demo is in a room the model has never seen. Every number this project has
describes one home office, and the domain-shift study is precisely the finding that a
detector interpolates inside its covered envelope and collapses outside it. This script
turns an unmeasured room into a measured one in the time it takes to set up a table.

Place the medications at the marks, then run it. It reports, in order:

1. **The scene** — median grey level and the fraction of blown highlights. Direct sun was
   the worst cell in the grid (0-41%), and blown highlights are its signature, so this is
   the number that says whether the room is safe before any detection runs.
2. **Detection with the camera on auto** — per medication, how often it is seen and at what
   confidence. This is the honest answer to "does MeSA work in this room".
3. **Detection with the camera locked** — the same measurement after freezing exposure,
   white balance and focus. Locking is only worth doing if it does not cost detection HERE;
   that is a question about the room, not about the code.
4. **The config block to paste**, and the frozen values.

Nothing is written to config.yaml automatically: the operator decides, with both numbers in
front of them.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TRAY = "tray"


def scene_stats(gray) -> dict:
    """Median grey level and blown-highlight fraction. Pure, so it is unit-testable."""
    import numpy as np
    g = np.asarray(gray)
    return {
        "median": float(np.median(g)),
        "mean": float(g.mean()),
        "blown_pct": 100.0 * float((g > 250).mean()),
        "dark_pct": 100.0 * float((g < 20).mean()),
    }


def verdict(median: float, blown_pct: float) -> str:
    """Map scene statistics onto the conditions the grid actually measured."""
    if blown_pct > 5.0:
        return "BLOWN HIGHLIGHTS — resembles the direct-sun cell (worst in the grid, 0-41%). Close blinds."
    if median < 40:
        return "VERY DIM — resembles evening-dim (dark bottles 38-41%). Use the lamp."
    if median < 70:
        return "DIM — below any cell measured well without the lamp. Use the lamp."
    return "OK — comparable to the midday / evening-lights cells, where detection was 95-98%."


def _measure(cap, model, seconds: float, every: int = 3) -> dict:
    import cv2
    seen: dict[str, list[float]] = defaultdict(list)
    frames = 0
    t0 = time.time()
    while time.time() - t0 < seconds:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1
        if frames % every:
            continue
        res = model.predict(frame, conf=0.10, verbose=False)[0]
        best: dict[str, float] = {}
        for b in res.boxes:
            label = model.names[int(b.cls[0])]
            if label == TRAY:
                continue
            c = float(b.conf[0])
            best[label] = max(best.get(label, 0.0), c)
        for label, c in best.items():
            seen[label].append(c)
    return {"frames": frames, "seen": seen}


def _report(title: str, result: dict, known: list[str], samples: int) -> None:
    print(f"\n--- {title} ---")
    print(f"{'medication':16s} {'seen':>7s}  {'median conf':>11s}")
    for med in known:
        confs = result["seen"].get(med, [])
        rate = 100.0 * len(confs) / max(samples, 1)
        med_conf = statistics.median(confs) if confs else 0.0
        flag = "" if rate >= 90 else ("  <-- WEAK" if rate >= 40 else "  <-- FAILING")
        print(f"{med:16s} {rate:6.0f}% {med_conf:11.2f}{flag}")


def main() -> int:
    p = argparse.ArgumentParser(description="On-site readiness check")
    p.add_argument("--label", default="site", help="room name, for the saved reference frame")
    p.add_argument("--seconds", type=float, default=15.0, help="per measurement pass")
    p.add_argument("--model", default="models/best.pt")
    p.add_argument("--camera", type=int, default=0)
    args = p.parse_args()

    import cv2
    from ultralytics import YOLO
    from mesa.vision.camera import configure_capture

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    time.sleep(2.5)   # let auto-exposure settle before judging the room
    for _ in range(10):
        cap.read()

    ok, frame = cap.read()
    if not ok:
        print("camera not readable")
        return 1
    stats = scene_stats(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    ref = Path(f"/tmp/site_{args.label.replace(' ', '_')}.jpg")
    cv2.imwrite(str(ref), frame)

    print(f"=== SITE CHECK — {args.label} — {time.strftime('%Y-%m-%d %H:%M')} ===")
    print(f"\nscene: median {stats['median']:.0f}  mean {stats['mean']:.0f}  "
          f"blown {stats['blown_pct']:.1f}%  dark {stats['dark_pct']:.1f}%")
    print(f"VERDICT: {verdict(stats['median'], stats['blown_pct'])}")
    print(f"reference frame: {ref}")

    model = YOLO(args.model)
    known = sorted(n for n in model.names.values() if n != TRAY)

    auto = _measure(cap, model, args.seconds)
    samples = max(1, auto["frames"] // 3)
    _report("camera on AUTO", auto, known, samples)

    cfg = {"vision": {"camera": {"enabled": True, "lock_exposure": True,
                                 "lock_white_balance": True, "lock_focus": True,
                                 "exposure": None, "white_balance": None, "focus": 0}}}
    frozen = configure_capture(cap, cfg, cv2_module=cv2)
    locked = _measure(cap, model, args.seconds)
    samples_l = max(1, locked["frames"] // 3)
    _report("camera LOCKED", locked, known, samples_l)

    print("\nfrozen values:", ", ".join(f"{k}={v}" for k, v in sorted(frozen.items())))
    print("\nIf LOCKED is no worse than AUTO, put this in config.yaml under vision:")
    print("  camera:\n    enabled: true\n    lock_exposure: true\n    lock_white_balance: true\n"
          "    lock_focus: true\n    exposure: null\n    white_balance: null\n    focus: 0")
    print("\n(null freezes whatever auto chose at startup — which is what was just measured.)")
    cap.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
