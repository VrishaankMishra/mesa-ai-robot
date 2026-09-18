"""Speech-to-text behind one interface (VOX-001, VOX-008).

The whole point of this module is the *interface*: the rest of the system depends only on
the protocols below, so the engine can be swapped without touching callers. Vosk / Whisper
/ audio libs are imported lazily inside the concrete classes.

Two shapes of recognizer, because the two engines work differently:

- :class:`SpeechRecognizer` — **streaming**. ``listen()`` yields transcripts continuously
  from an always-open microphone. Vosk is this shape; it is what a wake word needs.
- :class:`ClipRecognizer` — **bounded**. ``transcribe_clip(max_seconds)`` records one
  utterance and transcribes it once. Whisper is this shape: it is not a streaming model,
  and it does not need to be, because push-to-talk (VOX-006) hands it a bounded window.

Why Whisper exists here at all (VOX-008): Vosk-small is a *closed-vocabulary* decoder. Its
lexicon is compiled into a static graph, and a word outside it — "omeprazole",
"ashwagandha" — is not misheard, it is *unrepresentable*; the decoder cannot emit it.
Medication names are exactly the words a general English lexicon lacks, and requiring
every drug on a schedule to be an English dictionary word is not a constraint a medication
assistant can live with. Whisper is open-vocabulary (subword tokens), so any name is
transcribable, and pharmaceutical names are dense in its training data.
"""

from __future__ import annotations

from typing import Callable, Iterable, Iterator, Protocol


class SpeechRecognizer(Protocol):
    def listen(self) -> Iterator[str]:
        """Yield finalized transcript strings as the user speaks."""
        ...


class ClipRecognizer(Protocol):
    def transcribe_clip(self, max_seconds: float) -> str:
        """Record until the person stops talking (or ``max_seconds``) and transcribe once.

        Returns ``""`` if nothing was said.
        """
        ...


def record_until_silence(
    chunks: Iterable,
    samplerate: int,
    max_seconds: float,
    silence_seconds: float = 1.2,
    energy_threshold: float = 600.0,
    calibrate_seconds: float = 0.5,
    noise_multiplier: float = 3.0,
    max_threshold_multiplier: float = 4.0,
):
    """Pull int16 chunks from ``chunks`` until speech has been followed by silence.

    Pure with respect to hardware — ``chunks`` is any iterable of 1-D int16 numpy arrays —
    so the endpointing logic is unit-tested with synthetic audio.

    The speech threshold is adaptive: the quietest chunk in the first ``calibrate_seconds``
    is taken as the room's noise floor, and speech must exceed ``noise_multiplier`` times
    that (never less than ``energy_threshold``). A fixed threshold tuned in a quiet room is
    exactly the kind of setting the 2026-09-13 library demo punished; calibrating against
    the room that is actually there is the point. The *minimum* chunk is used, not the
    mean, so a person who starts talking at the instant of the press does not usually
    inflate their own floor — speech has gaps, and the gaps are the floor. For the talker
    with *no* gaps, adaptation is capped at ``max_threshold_multiplier`` times
    ``energy_threshold``: a loud room can raise the bar, but never above a level that
    ordinary speech clears. Without the cap, unbroken speech calibrates the floor to
    itself and the person is filtered out as noise.

    Returns float32 audio in [-1, 1] (what Whisper wants), or ``None`` if no chunk ever
    crossed the threshold, i.e. nobody spoke.
    """
    import numpy as np

    collected: list = []
    elapsed = 0.0
    heard_speech = False
    trailing_silence = 0.0
    floor_samples: list[float] = []
    threshold = float(energy_threshold)
    ceiling = float(energy_threshold) * max_threshold_multiplier

    for chunk in chunks:
        chunk = np.asarray(chunk, dtype=np.int16)
        if chunk.size == 0:
            continue
        dur = chunk.size / float(samplerate)
        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        collected.append(chunk)
        elapsed += dur

        if elapsed <= calibrate_seconds:
            floor_samples.append(rms)
            threshold = max(float(energy_threshold),
                            min(min(floor_samples) * noise_multiplier, ceiling))
            # Loud speech during calibration still counts as speech.
            if rms > threshold:
                heard_speech = True
                trailing_silence = 0.0
        elif rms > threshold:
            heard_speech = True
            trailing_silence = 0.0
        elif heard_speech:
            trailing_silence += dur
            if trailing_silence >= silence_seconds:
                break

        if elapsed >= max_seconds:
            break

    if not heard_speech or not collected:
        return None
    audio = np.concatenate(collected).astype(np.float32) / 32768.0
    return audio


class VoskRecognizer:
    """Offline STT using Vosk. Needs a microphone + a downloaded Vosk model."""

    def __init__(
        self,
        model_path: str,
        samplerate: int = 16000,
        device: int | None = None,
        grammar: str | None = None,
    ):
        self.model_path = model_path
        self.samplerate = samplerate
        self.device = device
        # Optional JSON phrase list (see mesa.audio.vocabulary). When set, Vosk decodes
        # against these words only — which is what keeps a noisy room from producing
        # words nobody said. None = the model's full open vocabulary.
        self.grammar = grammar

    def listen(self) -> Iterator[str]:  # pragma: no cover - requires mic hardware
        import json
        import queue

        import sounddevice as sd
        from vosk import KaldiRecognizer, Model

        model = Model(self.model_path)
        rec = (
            KaldiRecognizer(model, self.samplerate, self.grammar)
            if self.grammar
            else KaldiRecognizer(model, self.samplerate)
        )
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


class WhisperRecognizer:
    """Offline open-vocabulary STT using faster-whisper (CTranslate2), CPU int8.

    Implements :class:`ClipRecognizer` — its natural shape — and also
    :class:`SpeechRecognizer` by looping clips, so the wake-word path still works if
    push-to-talk is off (each pause-delimited utterance becomes one transcript).

    ``hint_words`` (the station's medication names) go in as Whisper's ``initial_prompt``,
    which biases decoding toward those spellings. It is a hint, not a grammar: unlike Vosk
    there is no closed vocabulary here, which is the entire reason to use it.

    ``model`` and ``chunk_source`` are injectable so the class is unit-testable with no
    microphone and no model download.
    """

    name = "whisper"

    def __init__(
        self,
        model_size: str = "tiny",
        model_path: str | None = None,
        samplerate: int = 16000,
        device: int | None = None,
        compute_type: str = "int8",
        silence_seconds: float = 1.2,
        energy_threshold: float = 600.0,
        hint_words: Iterable[str] = (),
        language: str = "en",
        model=None,
        chunk_source: Callable[[float], Iterable] | None = None,
    ):
        self.model_size = model_size
        self.model_path = model_path
        self.samplerate = samplerate
        self.device = device
        self.compute_type = compute_type
        self.silence_seconds = silence_seconds
        self.energy_threshold = energy_threshold
        self.language = language
        hints = [h.strip() for h in hint_words if h and h.strip()]
        self.initial_prompt = ("Medications: " + ", ".join(hints) + ".") if hints else None
        self._model = model
        self._chunk_source = chunk_source

    # -- model ------------------------------------------------------------------------
    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # lazy: laptops without it still import this module

            self._model = WhisperModel(
                self.model_path or self.model_size, device="cpu", compute_type=self.compute_type,
            )
        return self._model

    def warm_up(self) -> None:
        """Load the model now (first load is the slow part) so the first press is not."""
        self._get_model()

    # -- audio ------------------------------------------------------------------------
    def _chunks(self, max_seconds: float):  # pragma: no cover - requires mic hardware
        """Yield ~100 ms int16 chunks from the microphone for up to ``max_seconds``."""
        import queue

        import numpy as np
        import sounddevice as sd

        q: queue.Queue = queue.Queue()
        blocksize = int(self.samplerate * 0.1)

        def _callback(indata, frames, t, status):
            q.put(np.frombuffer(bytes(indata), dtype=np.int16).copy())

        deadline_chunks = int(max_seconds / 0.1) + 2
        with sd.RawInputStream(
            samplerate=self.samplerate, blocksize=blocksize, dtype="int16",
            channels=1, device=self.device, callback=_callback,
        ):
            for _ in range(deadline_chunks):
                yield q.get()

    def transcribe_clip(self, max_seconds: float) -> str:
        source = self._chunk_source or self._chunks
        audio = record_until_silence(
            source(max_seconds), self.samplerate, max_seconds,
            silence_seconds=self.silence_seconds, energy_threshold=self.energy_threshold,
        )
        if audio is None:
            return ""
        segments, _info = self._get_model().transcribe(
            audio,
            language=self.language,
            beam_size=1,
            initial_prompt=self.initial_prompt,
            condition_on_previous_text=False,
            vad_filter=False,  # we already endpointed; Whisper's VAD would re-trim
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def listen(self) -> Iterator[str]:  # pragma: no cover - requires mic hardware
        """Streaming shape for the wake-word path: one transcript per pause-delimited utterance."""
        while True:
            text = self.transcribe_clip(max_seconds=15.0)
            if text:
                yield text
