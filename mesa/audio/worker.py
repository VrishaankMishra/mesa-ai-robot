"""Live audio worker thread (ENG-004).

Runs the STT loop and answers voice commands (same behaviour as ``scripts/voice_loop.py``),
and additionally publishes engine events onto the :class:`~mesa.engine.events.EventBus`:

- ``HELP_REQUEST`` on a HELP intent, so escalation starts immediately.
- ``ACKNOWLEDGE`` on any other recognized intent — a person answering MeSA is by
  definition responsive, which clears a pending check-in (fall or inactivity).

:meth:`AudioWorker.handle_transcript` holds all of that decision logic with speech in and
speech out injected, so it is unit-testable without a microphone; :meth:`run` is the thin
mic-bound loop.
"""

from __future__ import annotations

import threading
import time

from mesa.audio.assistant import VoiceAssistant
from mesa.audio.intents import Intent, parse_intent, strip_wake_word
from mesa.engine.events import ACKNOWLEDGE, HELP_REQUEST, Event, EventBus


class AudioWorker(threading.Thread):
    def __init__(
        self,
        bus: EventBus,
        assistant: VoiceAssistant,
        recognizer,
        wake_word: str,
        speak=None,
    ):
        super().__init__(name="audio-worker", daemon=True)
        self.bus = bus
        self.assistant = assistant
        self.recognizer = recognizer
        self.wake_word = wake_word.lower()
        self.speak = speak or (lambda _msg: None)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def handle_transcript(self, transcript: str, now: float | None = None) -> bool:
        """Process one finalized transcript. Returns True if it was a wake-word command."""
        if self.wake_word not in transcript.lower():
            return False
        now = now if now is not None else time.time()
        parsed = parse_intent(strip_wake_word(transcript, self.wake_word))

        if parsed.intent == Intent.HELP:
            self.bus.publish(Event(HELP_REQUEST, {}, ts=now))
        elif parsed.intent != Intent.UNKNOWN:
            # They answered MeSA coherently -> responsive -> clear any pending check-in.
            self.bus.publish(Event(ACKNOWLEDGE, {}, ts=now))

        self.speak(self.assistant.respond(parsed, now=now))
        return True

    def run(self) -> None:  # pragma: no cover - blocks on the microphone stream
        for transcript in self.recognizer.listen():
            if self._stop.is_set():
                break
            self.handle_transcript(transcript)
