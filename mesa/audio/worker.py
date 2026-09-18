"""Live audio worker thread (ENG-004, push-to-talk VOX-006).

Runs the STT loop and answers voice commands (same behaviour as ``scripts/voice_loop.py``),
and additionally publishes engine events onto the :class:`~mesa.engine.events.EventBus`:

- ``HELP_REQUEST`` on a HELP intent, so escalation starts immediately.
- ``ACKNOWLEDGE`` on any other recognized intent — a person answering MeSA is by
  definition responsive, which clears a pending check-in (fall or inactivity).

**Two listening modes.** Without a trigger the worker is wake-word driven: every
transcript is tested against the wake word and ignored unless it matches. With a
:class:`~mesa.audio.ptt.PushToTalk` trigger it is push-to-talk: a button press opens a
:class:`~mesa.audio.ptt.TalkWindow`, and only speech finalized inside that window is
acted on — the press *is* the wake signal, so no wake word is required (one is still
stripped if the user says it out of habit).

Push-to-talk exists because the wake word is unreliable in noise and we have no measured
data on how it fails there; see ``mesa/audio/ptt.py`` for the full reasoning. Note that
the stream is gated, not stopped: Vosk keeps transcribing, but anything it hears outside
an open window is discarded before it reaches the intent parser.

:meth:`AudioWorker.handle_transcript` holds all of that decision logic with speech in and
speech out injected, so it is unit-testable without a microphone; :meth:`run` is the thin
mic-bound loop.
"""

from __future__ import annotations

import threading
import time

from mesa.audio.assistant import VoiceAssistant
from mesa.audio.intents import Intent, matches_wake_word, parse_intent, strip_wake_word
from mesa.audio.ptt import TalkWindow
from mesa.engine.events import ACKNOWLEDGE, HELP_REQUEST, Event, EventBus

# Vosk's out-of-vocabulary token (see mesa.audio.vocabulary). A grammar-constrained
# recognizer emits this for anything it cannot match, so it must never be parsed as speech.
UNK_TOKEN = "[unk]"


class AudioWorker(threading.Thread):
    def __init__(
        self,
        bus: EventBus,
        assistant: VoiceAssistant,
        recognizer,
        wake_word: str,
        speak=None,
        trigger=None,
        window_seconds: float = 6.0,
        check_in_window_seconds: float = 30.0,
        on_listening=None,
    ):
        super().__init__(name="audio-worker", daemon=True)
        self.bus = bus
        self.assistant = assistant
        self.recognizer = recognizer
        self.wake_word = wake_word.lower()
        self.speak = speak or (lambda _msg: None)
        self.trigger = trigger
        self.window = TalkWindow(window_seconds)
        # Check-ins get a longer window than a command: a person answering "Are you okay?"
        # after a fall is slower than someone pressing a button to ask a question.
        self.check_in_window_seconds = check_in_window_seconds
        # Called with True when a talk window opens and False when it closes, so the OLED
        # face / any indicator can show that MeSA is actually listening. Silent by default.
        self.on_listening = on_listening or (lambda _listening: None)
        # Absolute time until which an open window is "sticky": an utterance we cannot
        # classify re-opens it instead of closing it. Set for escalation check-ins, where
        # giving up after one garbled reply would escalate a person who did answer.
        self._sticky_until: float | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    @property
    def push_to_talk(self) -> bool:
        return self.trigger is not None

    def stop(self) -> None:
        self._stop.set()
        if self.trigger is not None:
            self.trigger.close()

    def open_window(
        self,
        now: float | None = None,
        seconds: float | None = None,
        sticky: bool = False,
    ) -> None:
        """Open a talk window. Called by the trigger thread on a button press.

        ``sticky`` keeps the window alive across utterances MeSA cannot classify, for the
        full ``seconds``. :meth:`open_check_in` uses it; a button press does not.
        """
        now = now if now is not None else time.time()
        with self._lock:
            self.window.open(now, seconds)
            self._sticky_until = (
                now + (seconds if seconds is not None else self.window.window_seconds)
                if sticky else None
            )
        self.on_listening(True)

    def open_check_in(self, now: float | None = None) -> None:
        """Listen for an answer to a spoken check-in — no button press required.

        MeSA asked "Are you okay?", so MeSA listens. Without this, push-to-talk would make
        the check-in unanswerable: the reply arrives with no window open, is discarded, and
        the engine escalates L1 -> L2 -> L3 on someone who *did* answer. The person this
        matters most for is on the floor and cannot reach the button.
        """
        self.open_window(now, seconds=self.check_in_window_seconds, sticky=True)

    def _close_window(self) -> None:
        with self._lock:
            was_open = self.window.is_armed()
            self.window.close()
            self._sticky_until = None
        if was_open:
            self.on_listening(False)

    def handle_transcript(self, transcript: str, now: float | None = None) -> bool:
        """Process one finalized transcript. Returns True if it was acted on.

        In push-to-talk mode a transcript counts only inside an open talk window; in
        wake-word mode it counts only if it contains the wake word.
        """
        now = now if now is not None else time.time()

        if self.push_to_talk:
            with self._lock:
                if not self.window.is_open(now):
                    return False  # crowd noise outside a window: discarded, never parsed
            # The button was the wake signal. Strip a spoken wake word if there is one,
            # but do not require it.
            text = strip_wake_word(transcript, self.wake_word)
            # Read the sticky deadline before closing — _close_window clears it, and the
            # retry path below still needs to know whether this was a check-in window.
            sticky_until = self._sticky_until
            self._close_window()
        else:
            if not matches_wake_word(transcript, self.wake_word):
                return False
            text = strip_wake_word(transcript, self.wake_word)
            sticky_until = None

        if not text.strip() or text.strip().lower() == UNK_TOKEN:
            # Grammar-constrained recognizer heard something it has no words for.
            self._retry_if_sticky(now, sticky_until)
            self.speak("Sorry, I didn't catch that. Please say it again.")
            return True

        parsed = parse_intent(text)
        if parsed.intent == Intent.UNKNOWN:
            self._retry_if_sticky(now, sticky_until)

        if parsed.intent == Intent.HELP:
            self.bus.publish(Event(HELP_REQUEST, {}, ts=now))
        elif parsed.intent != Intent.UNKNOWN:
            # They answered MeSA coherently -> responsive -> clear any pending check-in.
            self.bus.publish(Event(ACKNOWLEDGE, {}, ts=now))

        self.speak(self.assistant.respond(parsed, now=now))
        return True

    def _retry_if_sticky(self, now: float, sticky_until: float | None) -> None:
        """Keep a sticky (check-in) window open after a reply we could not classify."""
        if sticky_until is None or now >= sticky_until:
            return
        with self._lock:
            self.window.extend_to(sticky_until)
            self._sticky_until = sticky_until
        self.on_listening(True)

    def _trigger_loop(self) -> None:  # pragma: no cover - thread + blocking trigger
        """Wait for presses and open talk windows; prompt if a window closes unused."""
        while not self._stop.is_set():
            if not self.trigger.wait_for_press(timeout=0.5):
                # No press. Retire a window that ran out without any speech in it.
                if self.window.expired(time.time()):
                    self._close_window()
                    self.speak("I didn't hear anything. Press the button and try again.")
                continue
            if self._stop.is_set():
                break
            self.open_window()

    def run(self) -> None:  # pragma: no cover - blocks on the microphone stream
        if self.push_to_talk:
            threading.Thread(target=self._trigger_loop, name="ptt-trigger",
                             daemon=True).start()
        for transcript in self.recognizer.listen():
            if self._stop.is_set():
                break
            self.handle_transcript(transcript)
