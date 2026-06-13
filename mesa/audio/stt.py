"""Speech-to-text behind one interface (VOX-001).

The whole point of this module is the *interface*: the rest of the system depends only on
``SpeechRecognizer``, so Vosk can be swapped for whisper-tiny (risk mitigation) without
touching callers. Vosk/audio libs are imported lazily inside the concrete class.
"""

from __future__ import annotations

from typing import Iterator, Protocol


class SpeechRecognizer(Protocol):
    def listen(self) -> Iterator[str]:
        """Yield finalized transcript strings as the user speaks."""
        ...


class VoskRecognizer:
    """Offline STT using Vosk. Needs a microphone + a downloaded Vosk model."""

    def __init__(self, model_path: str, samplerate: int = 16000, device: int | None = None):
        self.model_path = model_path
        self.samplerate = samplerate
        self.device = device

    def listen(self) -> Iterator[str]:  # pragma: no cover - requires mic hardware
        import json
        import queue

        import sounddevice as sd
        from vosk import KaldiRecognizer, Model

        model = Model(self.model_path)
        rec = KaldiRecognizer(model, self.samplerate)
        q: queue.Queue = queue.Queue()

        def _callback(indata, frames, t, status):
            q.put(bytes(indata))

        with sd.RawInputStream(
            samplerate=self.samplerate, blocksize=8000, dtype="int16",
            channels=1, device=self.device, callback=_callback,
        ):
            while True:
                data = q.get()
                if rec.AcceptWaveform(data):
                    text = json.loads(rec.Result()).get("text", "").strip()
                    if text:
                        yield text
