"""Inactivity monitor (ENG-006).

No person/motion seen for a configurable window (default 1 h) -> fire once so the engine
can start escalation at L1. Resets whenever a person is seen. Time is injected.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InactivityEvent:
    inactive_seconds: float
    ts: float


class InactivityMonitor:
    def __init__(self, window_seconds: float = 3600.0):
        self.window_seconds = window_seconds
        self._last_active: float | None = None
        self._fired = False

    def update(self, person_present: bool, now: float) -> InactivityEvent | None:
        if person_present:
            self._last_active = now
            self._fired = False
            return None
        if self._last_active is None:
            # First observation is absence — start the clock from now.
            self._last_active = now
            return None
        inactive = now - self._last_active
        if not self._fired and inactive >= self.window_seconds:
            self._fired = True
            return InactivityEvent(inactive_seconds=inactive, ts=now)
        return None
