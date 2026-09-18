"""Tests for the open-vocabulary Whisper path (VOX-008) — no microphone, no model.

record_until_silence is pure over an iterable of int16 chunks; WhisperRecognizer takes an
injected model and chunk source; the worker's clip loop takes an injected clock.
"""

import numpy as np

from mesa.audio.assistant import VoiceAssistant
from mesa.audio.ptt import EventTrigger
from mesa.audio.stt import WhisperRecognizer, record_until_silence
from mesa.audio.worker import AudioWorker
from mesa.data.database import Database
from mesa.engine.events import ACKNOWLEDGE, HELP_REQUEST, EventBus

SR = 16000


def chunk(rms: float, seconds: float = 0.1, sr: int = SR):
    """A constant-amplitude int16 chunk with the given RMS."""
    n = int(sr * seconds)
    return np.full(n, int(rms), dtype=np.int16)


# --- endpointing -------------------------------------------------------------------

def test_silence_only_returns_none():
    audio = record_until_silence([chunk(50)] * 30, SR, max_seconds=3.0)
    assert audio is None


def test_speech_then_silence_stops_early_and_returns_float32():
    seq = [chunk(50)] * 5 + [chunk(3000)] * 8 + [chunk(50)] * 40   # 0.5s quiet, 0.8s speech, then quiet
    audio = record_until_silence(seq, SR, max_seconds=10.0, silence_seconds=1.2)
    assert audio is not None
    assert audio.dtype == np.float32 and np.abs(audio).max() <= 1.0
    # Stopped ~1.2 s after speech ended, well short of the 10 s max.
    assert 2.4 <= audio.size / SR <= 2.7


def test_speech_runs_to_max_when_it_never_stops():
    seq = [chunk(3000)] * 100
    audio = record_until_silence(seq, SR, max_seconds=2.0)
    assert audio is not None
    assert abs(audio.size / SR - 2.0) < 0.15


def test_threshold_adapts_to_a_loud_room():
    """The library case: a constant 900-RMS babble must not read as speech."""
    seq = [chunk(900)] * 40
    assert record_until_silence(seq, SR, max_seconds=4.0, energy_threshold=600.0) is None


def test_speech_over_a_loud_floor_is_still_caught():
    seq = [chunk(900)] * 5 + [chunk(6000)] * 6 + [chunk(900)] * 20
    audio = record_until_silence(seq, SR, max_seconds=4.0, energy_threshold=600.0)
    assert audio is not None


def test_talking_from_the_first_instant_does_not_inflate_the_floor():
    """Floor is the quietest calibration chunk, so speech with gaps still calibrates low."""
    seq = [chunk(4000), chunk(60), chunk(4000), chunk(60), chunk(4000)] + [chunk(60)] * 20
    audio = record_until_silence(seq, SR, max_seconds=4.0)
    assert audio is not None


# --- WhisperRecognizer with injected model + audio ----------------------------------

class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def transcribe(self, audio, **kw):
        self.calls.append(kw)
        return [FakeSegment(self.text)], None


def speech_source(max_seconds):
    return [chunk(50)] * 3 + [chunk(3000)] * 6 + [chunk(50)] * 30


def silent_source(max_seconds):
    return [chunk(50)] * 30


def test_transcribe_clip_returns_model_text():
    m = FakeModel(" Did I take my omeprazole today? ")
    r = WhisperRecognizer(model=m, chunk_source=speech_source)
    assert r.transcribe_clip(6.0) == "Did I take my omeprazole today?"


def test_transcribe_clip_skips_model_when_nobody_spoke():
    m = FakeModel("hallucination")
    r = WhisperRecognizer(model=m, chunk_source=silent_source)
    assert r.transcribe_clip(6.0) == ""
    assert m.calls == []          # no audio -> no decode -> nothing to hallucinate


def test_medication_names_become_the_initial_prompt():
    m = FakeModel("x")
    r = WhisperRecognizer(model=m, chunk_source=speech_source,
                          hint_words=["omeprazole", "ashwagandha", "vitamin d", ""])
    r.transcribe_clip(6.0)
    assert m.calls[0]["initial_prompt"] == "Medications: omeprazole, ashwagandha, vitamin d."
    assert m.calls[0]["language"] == "en"


def test_no_hints_means_no_prompt():
    m = FakeModel("x")
    r = WhisperRecognizer(model=m, chunk_source=speech_source)
    r.transcribe_clip(6.0)
    assert m.calls[0]["initial_prompt"] is None


# --- the whole chain: an OOV medication name, end to end ----------------------------

def test_omeprazole_is_recognized_end_to_end():
    """The exact command that failed at the library: a name no Vosk lexicon contains."""
    db = Database(":memory:")
    db.add_medication("omeprazole")
    spoken = []
    r = WhisperRecognizer(model=FakeModel("Did I take my omeprazole today?"),
                          chunk_source=speech_source)
    w = AudioWorker(EventBus(), VoiceAssistant(db), r, "mesa",
                    speak=spoken.append, trigger=EventTrigger())
    assert w.clip_mode
    w._auto_capture = False
    w.open_window(now=100.0)
    w._capture_loop(clock=lambda: 100.5)
    assert spoken == ["No, you haven't taken Omeprazole yet today."]


# --- clip-mode worker orchestration with a scripted recognizer ----------------------

class ScriptedClip:
    """Returns each scripted text in turn; records the max_seconds it was given."""
    def __init__(self, *texts):
        self.texts = list(texts)
        self.asked = []

    def transcribe_clip(self, max_seconds):
        self.asked.append(max_seconds)
        return self.texts.pop(0) if self.texts else ""


def make_clip_worker(rec, spoken):
    db = Database(":memory:")
    db.add_medication("tylenol")
    bus = EventBus()
    w = AudioWorker(bus, VoiceAssistant(db), rec, "mesa", speak=spoken.append,
                    trigger=EventTrigger(), window_seconds=6.0, check_in_window_seconds=30.0)
    w._auto_capture = False
    return w, bus


def drain(bus):
    out = []
    while not bus.empty():
        out.append(bus.get())
    return out


class FakeClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_press_records_once_and_closes():
    rec = ScriptedClip("call for help", "what time is it")
    spoken = []
    w, bus = make_clip_worker(rec, spoken)
    w.open_window(now=10.0)
    w._capture_loop(clock=FakeClock(10.2))
    assert [e.type for e in drain(bus)] == [HELP_REQUEST]
    assert len(rec.asked) == 1                          # one press, one recording
    assert not w.window.is_open(10.3)


def test_recording_asks_only_for_the_remaining_window():
    rec = ScriptedClip("what time is it")
    w, bus = make_clip_worker(rec, [])
    w.open_window(now=10.0)                             # deadline 16.0
    w._capture_loop(clock=FakeClock(12.5))
    assert abs(rec.asked[0] - 3.5) < 1e-6


def test_late_transcription_is_still_accepted():
    """Recording ran to the window's end and Whisper took 3 s more: still a valid command."""
    rec = ScriptedClip("what time is it")
    spoken = []
    w, bus = make_clip_worker(rec, spoken)
    w.open_window(now=10.0)                             # window shuts at 16.0
    clock = FakeClock(15.9)                             # recording started inside the window

    def slow_transcribe(max_seconds, _orig=rec.transcribe_clip):
        clock.t = 19.0                                  # ...and finished well after it
        return _orig(max_seconds)
    rec.transcribe_clip = slow_transcribe
    w._capture_loop(clock=clock)
    assert spoken and "time is" in spoken[0]


def test_silence_on_a_press_prompts_once_and_stops():
    rec = ScriptedClip("")
    spoken = []
    w, bus = make_clip_worker(rec, spoken)
    w.open_window(now=10.0)
    w._capture_loop(clock=FakeClock(10.1))
    assert spoken == ["I didn't hear anything. Press the button and try again."]
    assert len(rec.asked) == 1


def test_check_in_keeps_recording_through_garbage_until_answered():
    """Fall check-in: two unclassifiable replies, then 'I'm okay' — must ACKNOWLEDGE."""
    rec = ScriptedClip("", "mumble mumble", "I'm okay")
    spoken = []
    w, bus = make_clip_worker(rec, spoken)
    w.open_check_in(now=100.0)                          # sticky, 30 s
    clock = FakeClock(100.0)

    def ticking(max_seconds, _orig=rec.transcribe_clip):
        clock.t += 4.0
        return _orig(max_seconds)
    rec.transcribe_clip = ticking
    w._capture_loop(clock=clock)
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]
    assert len(rec.asked) == 3


def test_check_in_gives_up_at_its_deadline():
    rec = ScriptedClip(*([""] * 20))
    spoken = []
    w, bus = make_clip_worker(rec, spoken)
    w.open_check_in(now=100.0)
    clock = FakeClock(100.0)

    def ticking(max_seconds, _orig=rec.transcribe_clip):
        clock.t += 5.0
        return _orig(max_seconds)
    rec.transcribe_clip = ticking
    w._capture_loop(clock=clock)
    assert drain(bus) == []
    assert len(rec.asked) <= 7                          # ~30 s / 5 s, not 20


def test_second_capture_does_not_stack():
    rec = ScriptedClip("what time is it")
    w, bus = make_clip_worker(rec, [])
    w.open_window(now=10.0)
    assert w._capture_lock.acquire(blocking=False)      # simulate a capture in flight
    try:
        w._capture_loop(clock=FakeClock(10.1))          # must return immediately
    finally:
        w._capture_lock.release()
    assert rec.asked == []


def test_streaming_recognizer_is_not_clip_mode():
    w, _ = make_clip_worker(object(), [])
    assert w.clip_mode is False
