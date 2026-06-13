"""Text-to-speech wrapper (pyttsx3, offline).

A tiny indirection so callers just do ``speak(text)``. pyttsx3 is imported lazily and the
engine is cached. ``echo=True`` (for headless/dev) prints instead of speaking.
"""

from __future__ import annotations

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        import pyttsx3  # lazy

        _engine = pyttsx3.init()
    return _engine


def speak(text: str, echo: bool = False) -> None:
    if echo:
        print(f"[MeSA] {text}")
        return
    engine = _get_engine()  # pragma: no cover - audio hardware
    engine.say(text)
    engine.runAndWait()
