"""3-level escalation state machine (ENG-005).

L1: spoken check-in. If no response within ``l1_wait_seconds`` -> L2 (ntfy push). If still
no response within ``l2_wait_seconds`` -> L3 (caregiver alert: SMS or repeated push).

Side effects are injected callbacks (``on_check_in`` / ``on_notify`` / ``on_caregiver``) and
optional DB event logging, and time is passed in via ``now`` — so the whole machine is
unit-testable with simulated time (no real sleeping).
"""

from __future__ import annotations

from enum import Enum
from typing import Callable


class EscalationLevel(Enum):
    IDLE = "idle"
    L1 = "l1"
    L2 = "l2"
    L3 = "l3"


Callback = Callable[[str], None]


class EscalationMachine:
    def __init__(
        self,
        l1_wait_seconds: float = 60.0,
        l2_wait_seconds: float = 60.0,
        on_check_in: Callback | None = None,
        on_notify: Callback | None = None,
        on_caregiver: Callback | None = None,
        db=None,
    ):
        self.l1_wait_seconds = l1_wait_seconds
        self.l2_wait_seconds = l2_wait_seconds
        self.on_check_in = on_check_in
        self.on_notify = on_notify
        self.on_caregiver = on_caregiver
        self.db = db
        self.level = EscalationLevel.IDLE
        self.reason: str | None = None
        self._entered_at: float | None = None

    @property
    def active(self) -> bool:
        return self.level != EscalationLevel.IDLE

    def _log(self, type_: str) -> None:
        if self.db is not None:
            self.db.log_event(type_, detail=self.reason)

    def trigger(self, reason: str, now: float) -> EscalationLevel:
        """Begin escalation at L1. No-op if already escalating."""
        if self.active:
            return self.level
        self.level = EscalationLevel.L1
        self.reason = reason
        self._entered_at = now
        self._log("escalation_l1")
        if self.on_check_in:
            self.on_check_in(reason)
        return self.level

    def acknowledge(self, now: float) -> None:
        """User responded — resolve and return to idle."""
        if self.active:
            self._log("escalation_resolved")
            self.level = EscalationLevel.IDLE
            self.reason = None
            self._entered_at = None

    def tick(self, now: float) -> EscalationLevel | None:
        """Advance the machine if the current level's wait window has elapsed.

        Returns the new level if it changed this tick, else None.
        """
        if not self.active or self._entered_at is None:
            return None

        if self.level == EscalationLevel.L1 and now - self._entered_at >= self.l1_wait_seconds:
            self.level = EscalationLevel.L2
            self._entered_at = now
            self._log("escalation_l2")
            if self.on_notify:
                self.on_notify(self.reason or "")
            return self.level

        if self.level == EscalationLevel.L2 and now - self._entered_at >= self.l2_wait_seconds:
            self.level = EscalationLevel.L3
            self._entered_at = now
            self._log("escalation_l3")
            if self.on_caregiver:
                self.on_caregiver(self.reason or "")
            return self.level

        return None
