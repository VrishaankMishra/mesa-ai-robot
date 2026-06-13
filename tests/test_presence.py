"""Tests for the presence state machine (ENG-002) and taken rule (ENG-003).

All time is simulated by passing explicit ``now`` values.
"""

from mesa.engine.presence import BottleTracker, PresenceState


def feed(tracker, present, start, count, step=1.0):
    """Feed `count` observations of `present` starting at `start`, one per `step` seconds."""
    last = None
    for i in range(count):
        last = tracker.update(present, start + i * step)
    return last


def test_starts_present():
    t = BottleTracker("tylenol")
    assert t.state == PresenceState.PRESENT


def test_brief_occlusion_does_not_flip_state():
    # Absent for only 2s (< 3s debounce), then present again -> no transition, no event.
    t = BottleTracker("tylenol", debounce_seconds=3.0)
    assert t.update(False, 0.0) is None
    assert t.update(False, 2.0) is None
    assert t.update(True, 2.5) is None
    assert t.state == PresenceState.PRESENT


def test_debounced_transition_to_absent():
    t = BottleTracker("tylenol", debounce_seconds=3.0)
    t.update(False, 0.0)
    t.update(False, 2.9)            # still within debounce
    assert t.state == PresenceState.PRESENT
    t.update(False, 3.0)            # debounce elapsed -> commit ABSENT
    assert t.state == PresenceState.ABSENT


def test_taken_event_fires_after_long_absence():
    t = BottleTracker("vitamin_d", debounce_seconds=3.0, taken_after_absent_seconds=10.0)
    # Absent from t=0; commit absent at t=3.
    feed(t, False, 0.0, count=5)    # 0..4s absent
    assert t.state == PresenceState.ABSENT
    # Keep absent well past the 10s threshold, then return.
    feed(t, False, 5.0, count=12)   # absent through ~16s
    event = None
    for i in range(4):              # returning, debounced over 3s
        event = t.update(True, 20.0 + i)
    assert event is not None
    assert event.med_name == "vitamin_d"
    assert event.absent_seconds >= 10.0
    assert t.state == PresenceState.PRESENT


def test_short_absence_returns_without_taken_event():
    t = BottleTracker("aspirin", debounce_seconds=1.0, taken_after_absent_seconds=10.0)
    # Absent 1s (commits absent), back present after total ~4s absence (< 10s) -> no event.
    t.update(False, 0.0)
    t.update(False, 1.0)            # commit ABSENT (absent_since = 0.0)
    assert t.state == PresenceState.ABSENT
    t.update(True, 3.0)
    event = t.update(True, 4.0)     # commit PRESENT; absence ~3s < 10s
    assert event is None
    assert t.state == PresenceState.PRESENT
