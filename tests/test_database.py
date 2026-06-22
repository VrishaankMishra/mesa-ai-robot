"""Tests for the SQLite DAO (ENG-001)."""

import json
import sqlite3
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


# --- research extension: sessions + clips (DATA-001/002, RES-001) ---


def test_research_tables_exist(db):
    rows = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    tables = {r["name"] for r in rows}
    assert {"sessions", "clips"} <= tables


def test_create_session_roundtrip_serializes_conditions(db):
    sid = db.create_session(
        tier=1,
        participant="p01",
        conditions={"lighting": "dim", "distance_m": 1.0},
        fps=15.0,
        started_at=1000.0,
    )
    row = db.get_session(sid)
    assert row["tier"] == 1
    assert row["participant"] == "p01"
    assert row["consent_flag"] == 0
    assert json.loads(row["conditions"]) == {"lighting": "dim", "distance_m": 1.0}
    assert row["fps"] == 15.0


def test_tier2_requires_consent(db):
    with pytest.raises(ValueError, match="consent"):
        db.create_session(tier=2)  # no consent flag
    # with consent it succeeds
    sid = db.create_session(tier=2, consent_flag=True, consent_version="v1")
    assert db.get_session(sid)["consent_flag"] == 1


def test_invalid_tier_rejected(db):
    with pytest.raises(ValueError, match="tier"):
        db.create_session(tier=4)


def test_end_session_sets_ended_at(db):
    sid = db.create_session(tier=1, started_at=1000.0)
    assert db.get_session(sid)["ended_at"] is None
    db.end_session(sid, ended_at=1200.0)
    assert db.get_session(sid)["ended_at"] == 1200.0


def test_add_clip_links_to_session_and_event(db):
    sid = db.create_session(tier=1, started_at=1000.0)
    eid = db.log_event("taken", med_name="tylenol", ts=1010.0)
    cid = db.add_clip(
        session_id=sid,
        path=f"data/clips/{sid}/clip0.npz",
        window_seconds=6.0,
        n_frames=90,
        label_a="interact",
        label_b="tylenol",
        anchor_ts=1010.0,
        anchor_event_id=eid,
    )
    clips = db.get_clips(session_id=sid)
    assert len(clips) == 1
    c = clips[0]
    assert c["id"] == cid
    assert c["label_a"] == "interact" and c["label_b"] == "tylenol"
    assert c["anchor_event_id"] == eid
    assert c["label_source"] == "auto" and c["review_status"] == "auto"


def test_add_clip_validates_vocabularies(db):
    sid = db.create_session(tier=1)
    with pytest.raises(ValueError, match="label_a"):
        db.add_clip(sid, "p.npz", 6.0, 90, label_a="grabbing")
    with pytest.raises(ValueError, match="review_status"):
        db.add_clip(sid, "p.npz", 6.0, 90, label_a="interact", review_status="maybe")


def test_clip_requires_existing_session(db):
    # foreign_keys PRAGMA is ON; a dangling session_id must fail
    with pytest.raises(sqlite3.IntegrityError):
        db.add_clip("no-such-session", "p.npz", 6.0, 90, label_a="no_interaction")


def test_update_clip_review_relabel_marks_manual(db):
    sid = db.create_session(tier=1)
    cid = db.add_clip(sid, "p.npz", 6.0, 90, label_a="interact", label_b="tylenol")
    # relabel: supplying label_b flips source to manual and sets status
    db.update_clip_review(cid, "relabeled", label_b="vitamin_d")
    c = db.get_clips(session_id=sid)[0]
    assert c["review_status"] == "relabeled"
    assert c["label_b"] == "vitamin_d"
    assert c["label_source"] == "manual"


def test_update_clip_review_confirm_and_discard(db):
    sid = db.create_session(tier=1)
    cid = db.add_clip(sid, "p.npz", 6.0, 90, label_a="interact", label_b="tylenol")
    db.update_clip_review(cid, "confirmed")
    c = db.get_clips(session_id=sid)[0]
    assert c["review_status"] == "confirmed"
    assert c["label_source"] == "auto"  # unchanged when not relabeling
    db.update_clip_review(cid, "discarded")
    assert db.get_clips(session_id=sid)[0]["review_status"] == "discarded"


def test_get_clips_filters(db):
    sid = db.create_session(tier=1)
    db.add_clip(sid, "a.npz", 6.0, 90, label_a="interact", label_b="tylenol", created_at=1.0)
    db.add_clip(sid, "b.npz", 6.0, 90, label_a="no_interaction", created_at=2.0)
    assert len(db.get_clips()) == 2
    assert len(db.get_clips(label_a="interact")) == 1
    assert db.get_clips(label_a="no_interaction")[0]["path"] == "b.npz"
    # oldest-first ordering
    assert [c["path"] for c in db.get_clips()] == ["a.npz", "b.npz"]
