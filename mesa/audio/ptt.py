"""Push-to-talk trigger behind one interface (VOX-006).

Why this exists: the wake word is the least reliable link in the voice chain, and it
fails worst exactly when a demo needs it. Every voice cell ever measured
(``docs/eval/voice_grid_results.csv``) is a *quiet* cell, and even there the wake rate
was 0.67-0.80; the ``noise`` half of the grid in ``docs/voice-grid-sessions.md`` has
never been run. At the library science center demo (2026-09-13) the room was loud and
the wake word failed repeatedly. No audio was captured, so we have no measured
mishearings for babble noise and cannot honestly widen ``WAKE_VARIANTS`` to cover it.

Push-to-talk removes the link instead of guessing at it: a button press *is* the wake
signal. This is not a workaround to be embarrassed about — assistive devices do it
routinely, and it converts an unmeasured probability into a deterministic one.

Same shape as the rest of the swappable subsystems (cf. :mod:`mesa.audio.stt` and
:func:`mesa.hardware.oled.get_display`): callers depend only on :class:`PushToTalk`, and
:func:`get_trigger` returns a real driver where one works and a Null otherwise, so laptop
dev and unit tests run with no button and no GPIO.
"""

from __future__ import annotations

import threading
from typing import Protocol


class PushToTalk(Protocol):
    """A source of 'the user wants to speak now' signals."""

    def wait_for_press(self, timeout: float | None = None) -> bool:
        """Block until the talk button is pressed. True if pressed, False on timeout."""
        ...

    def close(self) -> None:
        ...


class NullTrigger:
    """Never fires. Used on a laptop with no button and in tests."""

    name = "none"

    def wait_for_press(self, timeout: float | None = None) -> bool:
        return False

    def close(self) -> None:
        pass


class EventTrigger:
    """Programmatic trigger — fired by :meth:`press`. The dashboard/tests drive this."""

    name = "event"

    def __init__(self) -> None:
        self._event = threading.Event()
        self._closed = False

    def press(self) -> None:
        self._event.set()

    def wait_for_press(self, timeout: float | None = None) -> bool:
        if self._closed:
            return False
        if self._event.wait(timeout):
            self._event.clear()
            return True
        return False

    def close(self) -> None:
        self._closed = True
        self._event.set()  # release any waiter so the thread can exit


class KeyboardTrigger:
    """Enter key on the controlling terminal opens a talk window.

    The default trigger, because it needs no parts: it works on the laptop, on the Pi
    over SSH, and on a keyboard plugged into the Pi. ``stdin.readline`` blocks, so this
    only ever runs on the worker's daemon trigger thread; :meth:`close` marks it closed
    and the process exit reclaims the blocked read.
    """

    name = "keyboard"

    def __init__(self, stream=None):
        import sys

        self._stream = stream if stream is not None else sys.stdin
        self._closed = False

    def wait_for_press(self, timeout: float | None = None) -> bool:
        """Return True on Enter. Honours ``timeout`` so the caller can poll other state.

        ``select`` rather than a bare blocking ``readline``: AudioWorker._trigger_loop
        uses the timeout to retire talk windows that expired unused, so a trigger that
        blocked forever would silently disable that prompt.
        """
        import select

        if self._closed:
            return False
        try:
            ready, _, _ = select.select([self._stream], [], [], timeout)
        except (OSError, ValueError):  # stream has no fileno (not a real tty)
            self._closed = True
            return False
        if not ready:
            return False
        line = self._stream.readline()
        if line == "":  # EOF — stdin closed (systemd, piped input)
            self._closed = True
            return False
        return not self._closed

    def close(self) -> None:
        self._closed = True


class GpioButtonTrigger:  # pragma: no cover - requires Pi GPIO
    """A momentary push button on a Pi GPIO pin (HW). Imports gpiozero lazily."""

    name = "gpio"

    def __init__(self, pin: int = 17, bounce_seconds: float = 0.05):
        from gpiozero import Button  # imported here so laptops never need gpiozero

        self._button = Button(pin, bounce_time=bounce_seconds)
        self._closed = False

    def wait_for_press(self, timeout: float | None = None) -> bool:
        if self._closed:
            return False
        return bool(self._button.wait_for_press(timeout=timeout)) and not self._closed

    def close(self) -> None:
        self._closed = True
        try:
            self._button.close()
        except Exception:
            pass


def get_trigger(source: str = "auto", pin: int = 17) -> PushToTalk:
    """Return the best available trigger.

    ``auto`` prefers a wired GPIO button and falls back to the keyboard, so the same
    config runs on the Pi with a button and on a laptop without one. Ask for ``keyboard``
    explicitly to ignore a button that is wired but flaky — worth knowing on demo day.
    """
    source = (source or "auto").lower()
    if source in ("gpio", "button", "auto"):
        try:
            return GpioButtonTrigger(pin=pin)
        except Exception:
            if source != "auto":
                raise
    if source in ("keyboard", "auto", "enter"):
        try:
            return KeyboardTrigger()
        except Exception:
            pass
    if source == "event":
        return EventTrigger()
    if source in ("none", "off"):
        return NullTrigger()
    return NullTrigger()


class TalkWindow:
    """The span after a press during which speech counts. Pure, so it is unit-testable.

    Gating on a window is deliberately cheaper than stopping and restarting the audio
    stream: Vosk keeps transcribing the room, but nothing it hears outside an open window
    reaches the intent parser. Crowd speech can therefore neither trigger a command nor
    bury one, which is the whole failure we saw at the library.
    """

    def __init__(self, window_seconds: float = 6.0):
        self.window_seconds = window_seconds
        self._open_until: float | None = None

    def open(self, now: float, seconds: float | None = None) -> None:
        """Open for ``seconds`` (default :attr:`window_seconds`)."""
        self._open_until = now + (self.window_seconds if seconds is None else seconds)

    def extend_to(self, until: float) -> None:
        """Hold the window open until an absolute time. Used to retry a check-in answer."""
        self._open_until = until

    def is_open(self, now: float) -> bool:
        return self._open_until is not None and now < self._open_until

    def is_armed(self) -> bool:
        """True if a window has been opened and not yet closed (open or just expired)."""
        return self._open_until is not None

    def deadline(self) -> float | None:
        """Absolute time the current window runs out, or None if none is armed."""
        return self._open_until

    def close(self) -> None:
        self._open_until = None

    def expired(self, now: float) -> bool:
        """True if a window was opened and has run out without being closed by speech."""
        return self._open_until is not None and now >= self._open_until
