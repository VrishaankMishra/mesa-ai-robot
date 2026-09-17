"""Tests for push-to-talk gating and vocabulary constraint (VOX-006 / VOX-007).

No microphone, no button, no sleeping — the talk window takes `now` explicitly so the
timing behaviour is exercised with simulated time (repo convention for timer logic).
"""

from mesa.audio.assistant import VoiceAssistant
from mesa.audio.ptt import EventTrigger, NullTrigger, TalkWindow, get_trigger
from mesa.audio.vocabulary import UNK, build_grammar, build_phrases
from mesa.audio.worker import AudioWorker
from mesa.data.database import Database
from mesa.engine.events import ACKNOWLEDGE, HELP_REQUEST, EventBus


def make_worker(spoken, trigger=None, window_seconds=6.0):
    db = Database(":memory:")
    db.add_medication("tylenol")
    bus = EventBus()
    worker = AudioWorker(
        bus,
        VoiceAssistant(db),
        recognizer=None,  # handle_transcript never touches the mic
        wake_word="mesa",
        speak=spoken.append,
        trigger=trigger,
        window_seconds=window_seconds,
    )
    return worker, bus


def drain(bus):
    events = []
    while not bus.empty():
        events.append(bus.get())
    return events


# --- TalkWindow (pure) ------------------------------------------------------------

def test_window_is_closed_until_opened():
    w = TalkWindow(6.0)
    assert w.is_open(100.0) is False
    assert w.is_armed() is False


def test_window_open_then_expires_on_schedule():
    w = TalkWindow(6.0)
    w.open(100.0)
    assert w.is_open(100.0) is True
    assert w.is_open(105.9) is True
    assert w.is_open(106.0) is False       # boundary is exclusive
    assert w.expired(106.0) is True


def test_window_close_disarms():
    w = TalkWindow(6.0)
    w.open(100.0)
    w.close()
    assert w.is_open(101.0) is False
    assert w.expired(200.0) is False       # closed, not expired-unused
    assert w.is_armed() is False


# --- push-to-talk gating ----------------------------------------------------------

def test_ptt_discards_speech_outside_a_window():
    """The library failure: a loud room talking at the robot must reach nothing."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    assert worker.handle_transcript("mesa call for help", now=10.0) is False
    assert spoken == []
    assert drain(bus) == []                # crucially: no HELP_REQUEST from crowd noise


def test_ptt_accepts_speech_inside_a_window_without_a_wake_word():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("what time is it", now=10.5) is True
    assert spoken and "time is" in spoken[0]


def test_ptt_still_strips_a_wake_word_said_from_habit():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("mesa did i take my tylenol today", now=10.5) is True
    assert "tylenol" in spoken[0].lower()


def test_ptt_window_closes_after_one_command():
    """One press, one command — a second utterance must not ride the same window."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("what time is it", now=10.5) is True
    assert worker.handle_transcript("mesa call for help", now=11.0) is False
    assert not [e for e in drain(bus) if e.type == HELP_REQUEST]


def test_ptt_window_expires_and_stops_accepting():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger(), window_seconds=6.0)
    worker.open_window(now=10.0)
    assert worker.handle_transcript("what time is it", now=16.1) is False
    assert spoken == []


def test_ptt_help_still_publishes_help_request():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("call for help", now=10.5) is True
    assert [e.type for e in drain(bus)] == [HELP_REQUEST]


def test_ptt_okay_acknowledges():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("i'm okay", now=10.5) is True
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]


def test_unk_token_is_never_parsed_as_speech():
    """A grammar-constrained recognizer emits [unk] for junk; it must not become a command."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript(UNK, now=10.5) is True
    assert "didn't catch that" in spoken[0]
    assert drain(bus) == []


def test_wake_word_mode_unchanged_when_no_trigger():
    """Without a trigger the worker must behave exactly as before (ENG-004 contract)."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=None)
    assert worker.push_to_talk is False
    assert worker.handle_transcript("what time is it", now=1.0) is False   # no wake word
    assert worker.handle_transcript("mesa what time is it", now=2.0) is True
    assert spoken and "time is" in spoken[0]


# --- triggers ---------------------------------------------------------------------

def test_event_trigger_fires_once_per_press():
    t = EventTrigger()
    assert t.wait_for_press(timeout=0.01) is False
    t.press()
    assert t.wait_for_press(timeout=0.01) is True
    assert t.wait_for_press(timeout=0.01) is False   # consumed


def test_closed_trigger_stops_firing():
    t = EventTrigger()
    t.close()
    assert t.wait_for_press(timeout=0.01) is False


def test_null_trigger_never_fires():
    assert NullTrigger().wait_for_press(timeout=0.01) is False


def test_get_trigger_falls_back_to_null_for_off():
    assert isinstance(get_trigger("none"), NullTrigger)


# --- vocabulary -------------------------------------------------------------------

def test_grammar_includes_commands_meds_and_unk():
    phrases = build_phrases({"tylenol", "vitamin_d3"})
    assert "call for help" in phrases
    assert "tylenol" in phrases
    assert "vitamin d3" in phrases          # snake_case -> spoken form
    assert UNK in phrases
    assert "mesa" in phrases


def test_grammar_is_valid_json_and_small():
    import json

    grammar = build_grammar({"tylenol"})
    parsed = json.loads(grammar)
    assert isinstance(parsed, list)
    # The whole point: a few dozen phrases, not ~100k words.
    assert len(parsed) < 100


def test_grammar_has_no_duplicates():
    phrases = build_phrases({"tylenol", "tylenol"})
    assert len(phrases) == len(set(phrases))
