"""Tests for VoiceAssistant responses (VOX-003) and ntfy request builder (VOX-004)."""

from datetime import datetime

import pytest

from mesa.alerts.ntfy import build_request
from mesa.audio.assistant import VoiceAssistant, next_scheduled, pretty_med
from mesa.audio.intents import Intent, ParsedIntent
from mesa.data.database import Database


@pytest.fixture
def db():
    d = Database(":memory:")
    d.add_medication("tylenol")
    d.add_medication("vitamin_d")
    d.add_schedule("tylenol", "08:00", "2 tablets")
    d.add_schedule("vitamin_d", "20:00", "1 tablet")
    yield d
    d.close()


# Noon on a fixed date for deterministic time-based responses.
NOON = datetime(2026, 6, 15, 12, 0, 0).timestamp()


def test_did_i_take_no_when_not_taken(db):
    a = VoiceAssistant(db)
    reply = a.respond(ParsedIntent(Intent.DID_I_TAKE, med="vitamin_d"), now=NOON)
    assert "haven't taken" in reply.lower()
    assert "Vitamin D" in reply


def test_did_i_take_yes_after_logging(db):
    db.log_event("taken", med_name="tylenol", ts=NOON - 3600)
    a = VoiceAssistant(db)
    reply = a.respond(ParsedIntent(Intent.DID_I_TAKE, med="tylenol"), now=NOON)
    assert "yes" in reply.lower() and "Tylenol" in reply


def test_did_i_take_unknown_med(db):
    a = VoiceAssistant(db)
    reply = a.respond(ParsedIntent(Intent.DID_I_TAKE, med="penicillin"), now=NOON)
    assert "don't have" in reply.lower()


def test_next_med_picks_upcoming(db):
    a = VoiceAssistant(db)
    # At noon, the next dose is vitamin_d at 20:00.
    reply = a.respond(ParsedIntent(Intent.NEXT_MED), now=NOON)
    assert "Vitamin D" in reply and "20:00" in reply


def test_next_med_none_left(db):
    a = VoiceAssistant(db)
    late = datetime(2026, 6, 15, 22, 0, 0).timestamp()
    reply = a.respond(ParsedIntent(Intent.NEXT_MED), now=late)
    assert "no more" in reply.lower()


def test_help_logs_and_alerts(db):
    sent = []
    a = VoiceAssistant(db, alert_fn=sent.append)
    reply = a.respond(ParsedIntent(Intent.HELP), now=NOON)
    assert "help" in reply.lower()
    assert sent == ["MeSA user requested help."]
    assert len(db.get_events(types=["help_request"])) == 1


def test_unknown_intent_response(db):
    a = VoiceAssistant(db)
    assert "say it again" in a.respond(ParsedIntent(Intent.UNKNOWN), now=NOON).lower()


def test_next_scheduled_helper():
    sched = [
        {"med_name": "a", "time_of_day": "08:00"},
        {"med_name": "b", "time_of_day": "20:00"},
    ]
    assert next_scheduled(sched, "12:00")["med_name"] == "b"
    assert next_scheduled(sched, "21:00") is None


def test_pretty_med():
    assert pretty_med("vitamin_d") == "Vitamin D"


def test_ntfy_build_request():
    url, headers, body = build_request(
        "mesa-alerts", "Help requested", title="MeSA", priority="urgent", tags=["rotating_light"]
    )
    assert url == "https://ntfy.sh/mesa-alerts"
    assert headers["Title"] == "MeSA"
    assert headers["Priority"] == "urgent"
    assert headers["Tags"] == "rotating_light"
    assert body == b"Help requested"


def test_ntfy_requires_topic():
    with pytest.raises(ValueError):
        build_request("", "msg")
