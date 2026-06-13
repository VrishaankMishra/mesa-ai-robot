"""MeSA 2.0 orchestrator entry point (ENG-004).

Builds the event bus + decision engine from config. In production, vision and audio worker
threads publish events onto the bus; those workers need a camera/mic, so they aren't
started here. ``--demo`` pushes a synthetic event sequence through the engine so the
integrated decision logic can be exercised on any laptop.

    python main.py --demo
"""

from __future__ import annotations

import argparse

from mesa import __version__
from mesa.config import get, load_config
from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker
from mesa.engine.decision import DecisionEngine
from mesa.engine.escalation import EscalationMachine
from mesa.engine.events import (
    ACKNOWLEDGE,
    BOTTLE_OBSERVATION,
    POSTURE,
    Event,
)
from mesa.engine.inactivity import InactivityMonitor
from mesa.vision.posture import Posture, PostureMonitor


def build_engine(db: Database, cfg: dict, speak=None) -> DecisionEngine:
    compliance = ComplianceTracker(
        db,
        debounce_seconds=get(cfg, "compliance.absence_debounce_seconds", 3),
        taken_after_absent_seconds=get(cfg, "compliance.taken_after_absent_seconds", 10),
    )
    escalation = EscalationMachine(
        l1_wait_seconds=get(cfg, "escalation.l1_wait_seconds", 60),
        on_check_in=lambda r: (speak or print)(f"Are you okay? ({r})"),
        on_notify=lambda r: print(f"[ntfy] {r}"),
        on_caregiver=lambda r: print(f"[caregiver alert] {r}"),
        db=db,
    )
    return DecisionEngine(
        db,
        compliance,
        escalation,
        posture_monitor=PostureMonitor(get(cfg, "pose.lying_trigger_seconds", 30)),
        inactivity_monitor=InactivityMonitor(get(cfg, "escalation.inactivity_window_seconds", 3600)),
        speak=speak,
    )


def _demo(engine: DecisionEngine) -> None:
    print("\n--- demo: synthetic event sequence ---")
    # Bottle removed then returned after 12s -> 'taken' event.
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=0))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=4))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=14))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=18))
    # Lying for >30s -> possible_fall -> escalation L1; no ack for 60s -> L2.
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=100))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=131))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=200))
    print(f"escalation level after no response: {engine.escalation.level.value}")
    # User responds.
    engine.process_event(Event(ACKNOWLEDGE, {}, ts=205))
    print(f"escalation level after acknowledge: {engine.escalation.level.value}")
    print("events logged:", [(e["type"], e["med_name"], e["detail"]) for e in engine.db.get_events()])


def main() -> None:
    p = argparse.ArgumentParser(description="MeSA orchestrator")
    p.add_argument("--demo", action="store_true", help="run a synthetic event sequence")
    args = p.parse_args()

    cfg = load_config()
    print(f"MeSA {__version__} — orchestrator ready.")
    db = Database(":memory:" if args.demo else "events.db")
    engine = build_engine(db, cfg)

    if args.demo:
        _demo(engine)
    else:
        print("Vision/audio workers need a camera + mic; start them to publish events.")
        print("See docs/IMPLEMENTATION.md (Week 6, ENG-004). Try: python main.py --demo")
    db.close()


if __name__ == "__main__":
    main()
