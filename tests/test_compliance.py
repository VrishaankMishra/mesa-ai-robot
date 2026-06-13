"""Tests for ComplianceTracker (ENG-003) and compute_med_status (DASH-001)."""

import pytest

from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker, compute_med_status


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


def test_taken_event_is_logged_to_db(db):
    ct = ComplianceTracker(db, debounce_seconds=1.0, taken_after_absent_seconds=10.0)
    ct.register("tylenol")
    # Absent long enough, then returned.
    ct.observe("tylenol", False, 0.0)
    ct.observe("tylenol", False, 1.0)      # commit absent (since 0.0)
    ct.observe("tylenol", False, 15.0)
    ct.observe("tylenol", True, 15.0)
    event = ct.observe("tylenol", True, 16.0)  # commit present; absence ~15s
    assert event is not None
    logged = db.get_events(types=["taken"])
    assert len(logged) == 1
    assert logged[0]["med_name"] == "tylenol"


def test_no_event_no_log(db):
    ct = ComplianceTracker(db, debounce_seconds=1.0, taken_after_absent_seconds=10.0)
    ct.observe("vitamin_d", True, 0.0)
    ct.observe("vitamin_d", True, 1.0)
    assert db.get_events(types=["taken"]) == []


def test_compute_med_status_marks_taken_and_sorts():
    schedule = [
        {"med_name": "vitamin_d", "time_of_day": "20:00", "dose": "1"},
        {"med_name": "tylenol", "time_of_day": "08:00", "dose": "2"},
    ]
    statuses = compute_med_status(schedule, taken_today={"tylenol"})
    # sorted by time_of_day
    assert [s.med_name for s in statuses] == ["tylenol", "vitamin_d"]
    assert statuses[0].taken is True
    assert statuses[1].taken is False
