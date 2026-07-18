"""Tests for voice intent parsing (VOX-002) — many phrasings per intent."""

import pytest

from mesa.audio.intents import (
    Intent,
    normalize_med,
    parse_intent,
    strip_wake_word,
)

HELP_PHRASES = [
    "help", "help me", "i need help", "call for help", "call someone",
    "emergency", "it's an emergency", "i've fallen", "i have fallen", "call 911",
]
NEXT_MED_PHRASES = [
    "what's my next medication", "next med", "next medication", "next pill",
    "next dose", "what do i take next", "when is my next med", "what's next",
]
DATE_TIME_PHRASES = [
    "what time is it", "what's the time", "tell me the time", "what day is it",
    "what's the date", "what's today's date", "what is the date today",
]
DID_I_TAKE_PHRASES = [
    ("did i take my vitamin d", "vitamin_d"),
    ("have i taken tylenol", "tylenol"),
    ("did i already take ibuprofen", "ibuprofen"),
    ("did i take the aspirin today", "aspirin"),
    ("have i had my multivitamin yet", "multivitamin"),
]


@pytest.mark.parametrize("phrase", HELP_PHRASES)
def test_help_intent(phrase):
    assert parse_intent(phrase).intent == Intent.HELP


@pytest.mark.parametrize("phrase", NEXT_MED_PHRASES)
def test_next_med_intent(phrase):
    assert parse_intent(phrase).intent == Intent.NEXT_MED


@pytest.mark.parametrize("phrase", DATE_TIME_PHRASES)
def test_date_time_intent(phrase):
    assert parse_intent(phrase).intent == Intent.DATE_TIME


@pytest.mark.parametrize("phrase,med", DID_I_TAKE_PHRASES)
def test_did_i_take_intent_and_med_slot(phrase, med):
    parsed = parse_intent(phrase)
    assert parsed.intent == Intent.DID_I_TAKE
    assert parsed.med == med


def test_unknown_intent():
    assert parse_intent("tell me a joke about robots").intent == Intent.UNKNOWN


def test_help_takes_priority_over_other_words():
    # "help" anywhere should win, since it's the safety-critical intent.
    assert parse_intent("i need help i think i've fallen").intent == Intent.HELP


def test_normalize_med():
    assert normalize_med("Vitamin D") == "vitamin_d"
    assert normalize_med("  ibuprofen ") == "ibuprofen"


def test_strip_wake_word():
    assert strip_wake_word("MeSA, what time is it", "mesa") == "what time is it"
    assert strip_wake_word("mesa next med", "mesa") == "next med"
    assert strip_wake_word("what time is it", "mesa") == "what time is it"


@pytest.mark.parametrize("phrase", ["i'm okay", "im ok", "i'm fine thanks", "all good",
                                    "no problem", "never mind", "i don't need help",
                                    "i don't need anything", "yes i'm up"])
def test_okay_intent(phrase):
    assert parse_intent(phrase).intent == Intent.OKAY


def test_negated_help_does_not_trigger_help():
    # "I don't need help" must never fire the safety alert path.
    assert parse_intent("i don't need help").intent is not Intent.HELP


def test_affirmative_help_still_wins_over_okay_words():
    # Safety first: an actual call for help beats an okay-sounding phrase around it.
    assert parse_intent("i'm fine but please call for help").intent == Intent.HELP
