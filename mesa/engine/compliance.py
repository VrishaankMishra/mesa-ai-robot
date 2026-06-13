"""Medication compliance tracking (ENG-003) + dashboard status helper (DASH-001).

Wires per-bottle :class:`BottleTracker` instances to the database: when a tracker emits a
``TakenEvent``, a ``taken`` row is logged. Also provides :func:`compute_med_status`, the
pure function the Streamlit dashboard uses to show today's taken/missed status.
"""

from __future__ import annotations

from dataclasses import dataclass

from mesa.data.database import Database
from mesa.engine.presence import BottleTracker, PresenceState, TakenEvent


class ComplianceTracker:
    """Holds one BottleTracker per medication and logs ``taken`` events to the DB."""

    def __init__(
        self,
        db: Database,
        debounce_seconds: float = 3.0,
        taken_after_absent_seconds: float = 10.0,
    ):
        self.db = db
        self.debounce_seconds = debounce_seconds
        self.taken_after_absent_seconds = taken_after_absent_seconds
        self._trackers: dict[str, BottleTracker] = {}

    def register(self, med_name: str, initial: PresenceState = PresenceState.PRESENT) -> None:
        self._trackers[med_name] = BottleTracker(
            med_name,
            debounce_seconds=self.debounce_seconds,
            taken_after_absent_seconds=self.taken_after_absent_seconds,
            initial=initial,
        )

    def observe(self, med_name: str, present: bool, now: float) -> TakenEvent | None:
        """Feed one observation for a bottle; log + return a TakenEvent if one fires."""
        if med_name not in self._trackers:
            self.register(med_name)
        event = self._trackers[med_name].update(present, now)
        if event is not None:
            self.db.log_event(
                "taken",
                med_name=event.med_name,
                detail=f"absent {event.absent_seconds:.0f}s",
                ts=event.ts,
            )
        return event


@dataclass(frozen=True)
class MedStatus:
    med_name: str
    time_of_day: str
    dose: str | None
    taken: bool


def compute_med_status(
    schedule: list[dict],
    taken_today: set[str],
) -> list[MedStatus]:
    """Combine the schedule with today's taken set into per-dose status rows.

    ``schedule`` items are dicts with ``med_name``, ``time_of_day`` and optional ``dose``.
    """
    statuses = [
        MedStatus(
            med_name=item["med_name"],
            time_of_day=item["time_of_day"],
            dose=item.get("dose"),
            taken=item["med_name"] in taken_today,
        )
        for item in schedule
    ]
    return sorted(statuses, key=lambda s: s.time_of_day)
