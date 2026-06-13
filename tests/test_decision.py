"""Integration tests for the DecisionEngine event routing (ENG-004)."""

import pytest

from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker
from mesa.engine.decision import DecisionEngine
from mesa.engine.escalation import EscalationLevel, EscalationMachine
from mesa.engine.events import (
    ACKNOWLEDGE,
    BOTTLE_OBSERVATION,
    HELP_REQUEST,
    POSTURE,
    SHUTDOWN,
    Event,
    EventBus,
)
from mesa.engine.inactivity import InactivityMonitor
from mesa.vision.posture import Posture, PostureMonitor


@pytest.fixture
def engine():
    db = Database(":memory:")
    eng = DecisionEngine(
        db,
        ComplianceTracker(db, debounce_seconds=1.0, taken_after_absent_seconds=10.0),
        EscalationMachine(l1_wait_seconds=60.0, l2_wait_seconds=60.0, db=db),
        posture_monitor=PostureMonitor(lying_trigger_seconds=30.0),
        inactivity_monitor=InactivityMonitor(window_seconds=3600.0),
    )
    yield eng
    db.close()


def test_bottle_observation_logs_taken(engine):
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=0))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=1))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": False}, ts=15))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=15))
    engine.process_event(Event(BOTTLE_OBSERVATION, {"med_name": "tylenol", "present": True}, ts=16))
    assert len(engine.db.get_events(types=["taken"])) == 1


def test_sustained_lying_triggers_escalation(engine):
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=0))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=30))
    assert engine.escalation.level == EscalationLevel.L1
    assert len(engine.db.get_events(types=["possible_fall"])) == 1


def test_no_response_escalates_then_acknowledge_resolves(engine):
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=0))
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=30))   # -> L1
    engine.process_event(Event(POSTURE, {"posture": Posture.LYING}, ts=90))   # tick -> L2
    assert engine.escalation.level == EscalationLevel.L2
    engine.process_event(Event(ACKNOWLEDGE, {}, ts=95))
    assert engine.escalation.level == EscalationLevel.IDLE


def test_help_request_triggers_escalation(engine):
    engine.process_event(Event(HELP_REQUEST, {}, ts=0))
    assert engine.escalation.level == EscalationLevel.L1


def test_emotion_hook_fires_on_escalation_and_ack():
    from mesa.hardware.emotions import Emotion

    db = Database(":memory:")
    seen = []
    eng = DecisionEngine(
        db,
        ComplianceTracker(db),
        EscalationMachine(db=db),
        set_emotion=seen.append,
    )
    eng.process_event(Event(HELP_REQUEST, {}, ts=0))
    eng.process_event(Event(ACKNOWLEDGE, {}, ts=1))
    assert seen == [Emotion.ALERT, Emotion.IDLE]
    db.close()


def test_run_loop_drains_until_shutdown(engine):
    bus = EventBus()
    bus.publish(Event(HELP_REQUEST, {}, ts=0))
    bus.shutdown()
    engine.run(bus)  # should process the help request then stop at SHUTDOWN
    assert engine.escalation.level == EscalationLevel.L1
    assert bus.empty()
