"""Decision engine — consumes events and drives compliance, falls, and escalation (ENG-004).

This is the single consumer of the :class:`EventBus`. :meth:`process_event` is pure with
respect to time (events carry their own ``ts``) and side effects (alerts/speech are
injected), so it is unit-testable without threads, hardware, or sleeping. :meth:`run` is
the production loop that drains the bus until a SHUTDOWN sentinel.
"""

from __future__ import annotations

from typing import Callable

from mesa.data.database import Database
from mesa.engine.compliance import ComplianceTracker
from mesa.engine.escalation import EscalationMachine
from mesa.engine.events import (
    ACKNOWLEDGE,
    BOTTLE_OBSERVATION,
    HELP_REQUEST,
    POSTURE,
    PRESENCE_CHECK,
    SHUTDOWN,
    Event,
    EventBus,
)
from mesa.engine.inactivity import InactivityMonitor
from mesa.vision.posture import Posture, PostureMonitor


class DecisionEngine:
    def __init__(
        self,
        db: Database,
        compliance: ComplianceTracker,
        escalation: EscalationMachine,
        posture_monitor: PostureMonitor | None = None,
        inactivity_monitor: InactivityMonitor | None = None,
        speak: Callable[[str], None] | None = None,
    ):
        self.db = db
        self.compliance = compliance
        self.escalation = escalation
        self.posture_monitor = posture_monitor or PostureMonitor()
        self.inactivity_monitor = inactivity_monitor or InactivityMonitor()
        self.speak = speak or (lambda _msg: None)

    def process_event(self, event: Event) -> None:
        ts = event.ts
        p = event.payload

        if event.type == BOTTLE_OBSERVATION:
            self.compliance.observe(p["med_name"], p["present"], ts)

        elif event.type == POSTURE:
            fall = self.posture_monitor.update(p["posture"], ts)
            if fall is not None:
                self.db.log_event("possible_fall", detail=f"lying {fall.lying_seconds:.0f}s", ts=ts)
                self.escalation.trigger("possible fall detected", ts)

        elif event.type == PRESENCE_CHECK:
            inactive = self.inactivity_monitor.update(p["person_present"], ts)
            if inactive is not None:
                self.escalation.trigger("prolonged inactivity", ts)

        elif event.type == HELP_REQUEST:
            self.escalation.trigger("user requested help", ts)

        elif event.type == ACKNOWLEDGE:
            self.escalation.acknowledge(ts)

        # Always advance escalation timers using this event's clock.
        self.escalation.tick(ts)

    def run(self, bus: EventBus) -> None:  # pragma: no cover - blocking loop
        """Drain the bus until a SHUTDOWN event is received."""
        while True:
            event = bus.get()
            if event.type == SHUTDOWN:
                break
            self.process_event(event)
