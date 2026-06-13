"""Tests for the escalation state machine (ENG-005) with simulated time."""

import pytest

from mesa.data.database import Database
from mesa.engine.escalation import EscalationLevel, EscalationMachine


@pytest.fixture
def calls():
    return {"l1": [], "l2": [], "l3": []}


@pytest.fixture
def machine(calls):
    return EscalationMachine(
        l1_wait_seconds=60.0,
        l2_wait_seconds=60.0,
        on_check_in=lambda r: calls["l1"].append(r),
        on_notify=lambda r: calls["l2"].append(r),
        on_caregiver=lambda r: calls["l3"].append(r),
    )


def test_trigger_enters_l1_and_speaks(machine, calls):
    machine.trigger("possible fall", now=0.0)
    assert machine.level == EscalationLevel.L1
    assert calls["l1"] == ["possible fall"]


def test_no_response_escalates_l1_to_l2_to_l3(machine, calls):
    machine.trigger("possible fall", now=0.0)
    assert machine.tick(59.0) is None              # not yet
    assert machine.tick(60.0) == EscalationLevel.L2
    assert calls["l2"] == ["possible fall"]
    assert machine.tick(119.0) is None             # 59s into L2
    assert machine.tick(120.0) == EscalationLevel.L3
    assert calls["l3"] == ["possible fall"]


def test_acknowledge_stops_escalation(machine, calls):
    machine.trigger("possible fall", now=0.0)
    machine.acknowledge(30.0)
    assert machine.level == EscalationLevel.IDLE
    # No further escalation after acknowledgement.
    assert machine.tick(100.0) is None
    assert calls["l2"] == [] and calls["l3"] == []


def test_trigger_is_noop_while_active(machine, calls):
    machine.trigger("possible fall", now=0.0)
    machine.trigger("inactivity", now=5.0)         # ignored — already escalating
    assert machine.reason == "possible fall"
    assert calls["l1"] == ["possible fall"]


def test_events_logged_to_db():
    db = Database(":memory:")
    m = EscalationMachine(l1_wait_seconds=10, l2_wait_seconds=10, db=db)
    m.trigger("possible fall", now=0.0)
    m.tick(10.0)
    m.tick(20.0)
    m.acknowledge(25.0)
    types = [e["type"] for e in db.get_events()]
    assert "escalation_l1" in types
    assert "escalation_l2" in types
    assert "escalation_l3" in types
    assert "escalation_resolved" in types
    db.close()
