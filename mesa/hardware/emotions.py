"""Emotion state mapping for the OLED face (HW-006).

Pure logic: map decision-engine event types to an emotion the face should show. No display
I/O here (that's mesa.hardware.oled) — this is the testable mapping + a tiny controller
that remembers the current emotion.
"""

from __future__ import annotations

from enum import Enum


class Emotion(Enum):
    IDLE = "idle"
    GREETING = "greeting"
    LISTENING = "listening"
    SPEAKING = "speaking"
    ALERT = "alert"


# Engine event/type -> emotion. Anything unmapped leaves the emotion unchanged.
_EVENT_EMOTION = {
    "possible_fall": Emotion.ALERT,
    "help_request": Emotion.ALERT,
    "escalation_l1": Emotion.ALERT,
    "escalation_l2": Emotion.ALERT,
    "escalation_l3": Emotion.ALERT,
    "escalation_resolved": Emotion.IDLE,
    "person_greeting": Emotion.GREETING,
    "listening": Emotion.LISTENING,
    "speaking": Emotion.SPEAKING,
}


def emotion_for(event_type: str) -> Emotion | None:
    """Return the emotion an event should trigger, or None to leave it unchanged."""
    return _EVENT_EMOTION.get(event_type)


class EmotionController:
    """Tracks the current emotion and updates it from engine events."""

    def __init__(self, initial: Emotion = Emotion.IDLE):
        self.current = initial

    def on_event(self, event_type: str) -> Emotion:
        nxt = emotion_for(event_type)
        if nxt is not None:
            self.current = nxt
        return self.current

    def set(self, emotion: Emotion) -> Emotion:
        self.current = emotion
        return self.current
