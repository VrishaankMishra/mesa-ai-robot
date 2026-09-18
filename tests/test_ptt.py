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


# --- escalation check-in must stay answerable under push-to-talk (VOX-006) -----------

def test_check_in_window_opens_without_a_button_press():
    """MeSA asked "Are you okay?", so MeSA listens — a fallen person cannot press it."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_check_in(now=100.0)
    assert worker.handle_transcript("i'm okay", now=101.0) is True
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]


def test_check_in_window_is_longer_than_a_command_window():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger(), window_seconds=6.0)
    worker.check_in_window_seconds = 30.0
    worker.open_check_in(now=100.0)
    # Still listening well past the 6s command window — answering a fall takes longer.
    assert worker.handle_transcript("i'm okay", now=125.0) is True
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]


def test_garbled_reply_does_not_end_a_check_in():
    """One unclassifiable answer must not escalate someone who actually responded."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.check_in_window_seconds = 30.0
    worker.open_check_in(now=100.0)

    assert worker.handle_transcript("[unk]", now=102.0) is True     # garbled
    assert drain(bus) == []                                          # no ack yet
    assert worker.handle_transcript("mumble mumble", now=104.0) is True
    assert drain(bus) == []
    # The window survived both, so the eventual real answer still lands.
    assert worker.handle_transcript("i'm okay", now=106.0) is True
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]


def test_check_in_window_does_eventually_expire():
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.check_in_window_seconds = 30.0
    worker.open_check_in(now=100.0)
    assert worker.handle_transcript("i'm okay", now=131.0) is False   # past the window
    assert drain(bus) == []


def test_ordinary_command_window_is_not_sticky():
    """A button press gets one shot; only check-ins retry."""
    spoken = []
    worker, bus = make_worker(spoken, trigger=EventTrigger())
    worker.open_window(now=10.0)
    assert worker.handle_transcript("[unk]", now=10.5) is True
    assert worker.handle_transcript("i'm okay", now=11.0) is False    # window closed
    assert drain(bus) == []


# --- spoken aliases (VOX-007): what is said vs what the detector emits --------------

def test_alias_replaces_raw_name_in_grammar():
    from mesa.audio.vocabulary import spoken_form
    aliases = {"vitamin_d3": "vitamin d", "cvs_allergy": "allergy pill"}
    phrases = build_phrases({"vitamin_d3", "cvs_allergy", "advil"}, aliases)
    assert "vitamin d" in phrases and "vitamin d3" not in phrases   # "d3" is not speech
    assert "allergy pill" in phrases and "cvs allergy" not in phrases
    assert "advil" in phrases                                       # no alias -> raw name
    assert spoken_form("advil", aliases) == "advil"


def test_alias_resolves_to_canonical_db_name():
    """User says 'vitamin d'; the DB and detector know only 'vitamin_d3'."""
    from mesa.audio.intents import parse_intent
    db = Database(":memory:")
    db.add_medication("vitamin_d3")
    a = VoiceAssistant(db, med_aliases={"vitamin_d3": "vitamin d"})
    parsed = parse_intent("did i take my vitamin d today")
    assert parsed.med == "vitamin_d"                                # what parse_intent yields
    reply = a.respond(parsed, now=1_700_000_000.0)
    assert "Vitamin D3" in reply                                    # resolved to the canonical name
    assert "don't have" not in reply


def test_canonical_name_still_resolves_alongside_alias():
    from mesa.audio.intents import Intent, ParsedIntent
    db = Database(":memory:")
    db.add_medication("vitamin_d3")
    a = VoiceAssistant(db, med_aliases={"vitamin_d3": "vitamin d"})
    reply = a.respond(ParsedIntent(Intent.DID_I_TAKE, med="vitamin_d3"), now=1_700_000_000.0)
    assert "Vitamin D3" in reply


def test_alias_for_unknown_canonical_does_not_invent_a_medication():
    """An alias pointing at a med not in the DB must not make it 'known'."""
    from mesa.audio.intents import Intent, ParsedIntent
    db = Database(":memory:")
    db.add_medication("advil")
    a = VoiceAssistant(db, med_aliases={"omeprazole": "stomach pill"})   # omeprazole not in DB
    reply = a.respond(ParsedIntent(Intent.DID_I_TAKE, med="stomach_pill"), now=1_700_000_000.0)
    assert "don't have that medication" in reply
    assert "stomach" not in reply.lower()                           # still never echoed
