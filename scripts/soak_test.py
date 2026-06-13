#!/usr/bin/env python3
"""Soak test for the decision engine (ENG-007).

Drives the DecisionEngine with a stream of synthetic events at compressed time and reports
peak memory, so you can confirm there are no leaks / state bl-ups over a long run. Uses
simulated event timestamps, so a "2-hour" soak runs in seconds. No hardware needed.

    python scripts/soak_test.py --hours 2
"""

from __future__ import annotations

import argparse
import random
import tracemalloc

from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker
from mesa.engine.decision import DecisionEngine
from mesa.engine.escalation import EscalationMachine
from mesa.engine.events import (
    ACKNOWLEDGE,
    BOTTLE_OBSERVATION,
    POSTURE,
    PRESENCE_CHECK,
    Event,
)
from mesa.vision.posture import Posture


def main() -> int:
    p = argparse.ArgumentParser(description="MeSA decision-engine soak test")
    p.add_argument("--hours", type=float, default=2.0, help="simulated duration")
    p.add_argument("--hz", type=float, default=5.0, help="simulated events per second")
    args = p.parse_args()

    db = Database(":memory:")
    engine = DecisionEngine(db, ComplianceTracker(db), EscalationMachine(db=db))
    postures = [Posture.STANDING, Posture.SITTING, Posture.LYING]
    meds = ["tylenol", "vitamin_d", "ibuprofen"]

    total = int(args.hours * 3600 * args.hz)
    tracemalloc.start()
    for i in range(total):
        ts = i / args.hz
        r = random.random()
        if r < 0.5:
            engine.process_event(Event(POSTURE, {"posture": random.choice(postures)}, ts=ts))
        elif r < 0.8:
            engine.process_event(Event(
                BOTTLE_OBSERVATION,
                {"med_name": random.choice(meds), "present": random.random() < 0.7},
                ts=ts,
            ))
        elif r < 0.95:
            engine.process_event(Event(PRESENCE_CHECK, {"person_present": True}, ts=ts))
        else:
            engine.process_event(Event(ACKNOWLEDGE, {}, ts=ts))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    db.close()

    print(f"processed events : {total:,}")
    print(f"current memory   : {current/1024:8.1f} KiB")
    print(f"peak memory      : {peak/1024:8.1f} KiB")
    print("Inspect peak memory: it should be roughly flat regardless of --hours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
