"""Event bus + event types (ENG-004).

All subsystems communicate through one queue (no MQTT/network IPC at this scale). The
vision and audio worker threads *publish* events; the decision engine *consumes* them.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any

# Event type constants.
BOTTLE_OBSERVATION = "bottle_observation"  # payload: {med_name, present}
POSTURE = "posture"                        # payload: {posture: Posture}
PRESENCE_CHECK = "presence_check"          # payload: {person_present: bool}
ACKNOWLEDGE = "acknowledge"                # user responded to a check-in
HELP_REQUEST = "help_request"              # voice HELP intent
SHUTDOWN = "__shutdown__"                  # sentinel to stop the consumer loop


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0


class EventBus:
    """Thin wrapper over ``queue.Queue`` so the API reads as publish/consume."""

    def __init__(self, maxsize: int = 0):
        self._q: queue.Queue[Event] = queue.Queue(maxsize=maxsize)

    def publish(self, event: Event) -> None:
        self._q.put(event)

    def get(self, timeout: float | None = None) -> Event:
        return self._q.get(timeout=timeout)

    def shutdown(self) -> None:
        self._q.put(Event(SHUTDOWN))

    def empty(self) -> bool:
        return self._q.empty()
