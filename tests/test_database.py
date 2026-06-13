"""Tests for the SQLite DAO (ENG-001)."""

import time

import pytest

from mesa.data.database import Database


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


def test_schema_tables_exist(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    tables = {r["name"] for r in rows}
    assert {"medications", "schedule", "events"} <= tables


def test_add_medication_is_idempotent(db):
    id1 = db.add_medication("tylenol", class_id=0)
    id2 = db.add_medication("tylenol", class_id=0)
    assert id1 == id2
    assert len(db.list_medications()) == 1


def test_schedule_roundtrip(db):
    db.add_medication("vitamin_d")
    db.add_schedule("vitamin_d", "08:00", dose="1 tablet")
    sched = db.get_schedule()
    assert len(sched) == 1
    assert sched[0]["med_name"] == "vitamin_d"
    assert sched[0]["time_of_day"] == "08:00"


def test_log_and_query_events(db):
    db.log_event("taken", med_name="tylenol", detail="absent 12s", ts=1000.0)
    db.log_event("possible_fall", detail="lying 31s", ts=2000.0)
    all_events = db.get_events()
    assert len(all_events) == 2
    # ordered newest first
    assert all_events[0]["type"] == "possible_fall"
    taken = db.get_events(types=["taken"])
    assert len(taken) == 1 and taken[0]["med_name"] == "tylenol"


def test_get_events_since_filter(db):
    db.log_event("taken", med_name="a", ts=100.0)
    db.log_event("taken", med_name="b", ts=200.0)
    recent = db.get_events(since=150.0)
    assert [e["med_name"] for e in recent] == ["b"]


def test_meds_taken_today(db):
    now = time.time()
    db.log_event("taken", med_name="tylenol", ts=now)
    db.log_event("taken", med_name="vitamin_d", ts=now - 10)
    # an event from "yesterday" shouldn't count
    db.log_event("taken", med_name="aspirin", ts=now - 48 * 3600)
    taken = db.meds_taken_today(now=now)
    assert taken == {"tylenol", "vitamin_d"}
