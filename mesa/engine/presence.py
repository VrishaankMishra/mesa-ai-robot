"""Per-bottle presence state machine (ENG-002).

Tracks whether a bottle is present or absent, with **debouncing** so a hand briefly
occluding the bottle doesn't false-trigger a state change. When a bottle has been absent
for at least ``taken_after_absent_seconds`` and is then returned, :meth:`update` emits a
:class:`TakenEvent` (ENG-003).

The class takes no real time of its own — the caller passes ``now`` — so it is fully
unit-testable with simulated time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PresenceState(Enum):
    PRESENT = "present"
    ABSENT = "absent"


@dataclass(frozen=True)
class TakenEvent:
    med_name: str
    absent_seconds: float
    ts: float


class BottleTracker:
    def __init__(
        self,
        med_name: str,
        debounce_seconds: float = 3.0,
        taken_after_absent_seconds: float = 10.0,
        initial: PresenceState = PresenceState.PRESENT,
    ):
        self.med_name = med_name
        self.debounce_seconds = debounce_seconds
        self.taken_after_absent_seconds = taken_after_absent_seconds
        self.state = initial
        self._candidate = initial          # the raw reading we're currently debouncing
        self._candidate_since: float | None = None
        self._absent_since: float | None = None

    def update(self, present: bool, now: float) -> TakenEvent | None:
        """Feed one observation. Returns a TakenEvent if a return-after-absence committed."""
        raw = PresenceState.PRESENT if present else PresenceState.ABSENT

        if raw == self.state:
            # Reading agrees with committed state — cancel any pending flip.
            self._candidate = raw
            self._candidate_since = now
            return None

        # Reading disagrees — start or continue debouncing the candidate flip.
        if raw != self._candidate or self._candidate_since is None:
            self._candidate = raw
            self._candidate_since = now
            return None

        if now - self._candidate_since >= self.debounce_seconds:
            began = self._candidate_since
            return self._commit(raw, began)
        return None

    def _commit(self, new_state: PresenceState, began: float) -> TakenEvent | None:
        self.state = new_state
        self._candidate_since = began
        if new_state == PresenceState.ABSENT:
            self._absent_since = began
            return None

        # Returned to PRESENT — was it absent long enough to count as "taken"?
        event: TakenEvent | None = None
        if self._absent_since is not None:
            absent_seconds = began - self._absent_since
            if absent_seconds >= self.taken_after_absent_seconds:
                event = TakenEvent(self.med_name, absent_seconds, began)
        self._absent_since = None
        return event
