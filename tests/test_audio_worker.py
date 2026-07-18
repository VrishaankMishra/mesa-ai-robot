"""Tests for AudioWorker.handle_transcript (ENG-004) — no microphone required."""

from mesa.audio.assistant import VoiceAssistant
from mesa.audio.worker import AudioWorker
from mesa.data.database import Database
from mesa.engine.events import ACKNOWLEDGE, HELP_REQUEST, EventBus


def make_worker(spoken):
    db = Database(":memory:")
    bus = EventBus()
    worker = AudioWorker(
        bus,
        VoiceAssistant(db),
        recognizer=None,  # handle_transcript never touches the mic
        wake_word="mesa",
        speak=spoken.append,
    )
    return worker, bus


def drain(bus):
    events = []
    while not bus.empty():
        events.append(bus.get())
    return events


def test_ignores_speech_without_wake_word():
    spoken = []
    worker, bus = make_worker(spoken)
    assert worker.handle_transcript("what time is it", now=1.0) is False
    assert spoken == []
    assert drain(bus) == []


def test_help_publishes_help_request():
    spoken = []
    worker, bus = make_worker(spoken)
    assert worker.handle_transcript("mesa call for help", now=5.0) is True
    events = drain(bus)
    assert [e.type for e in events] == [HELP_REQUEST]
    assert events[0].ts == 5.0
    assert spoken  # spoke a confirmation


def test_recognized_command_publishes_acknowledge():
    spoken = []
    worker, bus = make_worker(spoken)
    worker.handle_transcript("mesa what time is it", now=7.0)
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]
    assert spoken


def test_im_okay_publishes_acknowledge():
    spoken = []
    worker, bus = make_worker(spoken)
    worker.handle_transcript("mesa i'm okay", now=9.0)
    assert [e.type for e in drain(bus)] == [ACKNOWLEDGE]


def test_unrecognized_command_does_not_acknowledge():
    spoken = []
    worker, bus = make_worker(spoken)
    worker.handle_transcript("mesa purple monkey dishwasher", now=3.0)
    assert drain(bus) == []  # gibberish is not proof of responsiveness
    assert spoken  # still answered "didn't catch that"
