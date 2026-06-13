"""Tests for the inactivity monitor (ENG-006)."""

from mesa.engine.inactivity import InactivityEvent, InactivityMonitor


def test_fires_after_window_of_absence():
    m = InactivityMonitor(window_seconds=3600.0)
    assert m.update(False, 0.0) is None            # start clock
    assert m.update(False, 3599.0) is None
    event = m.update(False, 3600.0)
    assert isinstance(event, InactivityEvent)
    assert event.inactive_seconds >= 3600.0


def test_presence_resets_clock():
    m = InactivityMonitor(window_seconds=100.0)
    m.update(False, 0.0)
    m.update(True, 50.0)                            # person last seen at t=50
    assert m.update(False, 60.0) is None            # inactive 10s
    assert m.update(False, 149.0) is None           # inactive 99s
    assert m.update(False, 150.0) is not None       # inactive 100s -> fires


def test_fires_only_once_until_reset():
    m = InactivityMonitor(window_seconds=10.0)
    m.update(False, 0.0)
    assert m.update(False, 10.0) is not None
    assert m.update(False, 20.0) is None            # already fired
    m.update(True, 21.0)                            # reset
    m.update(False, 22.0)
    assert m.update(False, 32.0) is not None        # fires again after reset
