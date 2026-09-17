"""Recognizer vocabulary / grammar construction (VOX-007).

MeSA understands exactly four commands plus an escalation answer. Letting Vosk decode
against its full ~100k-word open vocabulary therefore buys nothing and costs a great
deal: in a noisy room the decoder is free to emit any English word that happens to fit
the garbled audio. At the library science center demo (2026-09-13) that produced two
failures in front of an audience — commands transcribed into something
:func:`~mesa.audio.intents.parse_intent` could not classify, and *profanity that was
never spoken*, which pyttsx3 then read back aloud.

Vosk's ``KaldiRecognizer`` accepts a JSON phrase list that restricts decoding to those
words. Constraining it turns both failures into structural impossibilities rather than
things to filter after the fact: a word outside this list cannot be emitted at all.

Caveat worth knowing before demo day: words absent from the acoustic model's lexicon are
dropped from the grammar by Vosk (with a warning on stderr). Common brand names like
"tylenol" and "advil" are usually present; long generic names like "omeprazole" often are
not. :func:`build_grammar` is therefore best-effort — run ``scripts/check_vocabulary.py``
to see which of *your* medication names actually survive.
"""

from __future__ import annotations

import json

from mesa.audio.intents import WAKE_VARIANTS

# The spoken surface of each intent, written as the words people actually say. These are
# phrases, not regexes: the grammar constrains *acoustics*, while intents.py still does
# the classifying. Keep them loose enough to cover natural phrasings of the four commands.
COMMAND_PHRASES: tuple[str, ...] = (
    # NEXT_MED
    "what is my next medication",
    "what is next",
    "when is my next dose",
    "next medication",
    "next pill",
    "next dose",
    # DID_I_TAKE
    "did i take my",
    "did i already take my",
    "have i taken my",
    "did i take",
    "have i had my",
    # HELP
    "call for help",
    "i need help",
    "help me",
    "i have fallen",
    "call someone",
    "emergency",
    # DATE_TIME
    "what time is it",
    "what is the time",
    "what is the date",
    "what day is it",
    "what is today",
    # OKAY (answer to an escalation check-in)
    "i am okay",
    "i am fine",
    "i am all right",
    "i am good",
    "all good",
    "never mind",
    "i do not need help",
    "no problem",
)

# Filler words that glue the phrases above together in natural speech. Including them
# keeps a slightly-off phrasing decodable instead of forcing it to the nearest command.
FILLER_WORDS: tuple[str, ...] = (
    "today", "yet", "already", "my", "the", "a", "and", "please",
    "yes", "no", "okay", "medication", "pill", "dose", "time", "date",
)

# Vosk's out-of-vocabulary sink. Without it, unmatched audio is forced onto the nearest
# in-grammar phrase — which would turn every stray cough into a command. With it, junk
# decodes to "[unk]" and parse_intent falls through to UNKNOWN, which is correct.
UNK = "[unk]"


def _wake_phrases() -> list[str]:
    """The wake word and its measured mishearings, so habitual 'MeSA, ...' still decodes."""
    return [" ".join(var) for var in WAKE_VARIANTS]


def build_phrases(med_names: set[str] | None = None) -> list[str]:
    """Every phrase the recognizer is allowed to produce, lowercased and de-duplicated."""
    phrases: list[str] = []
    phrases.extend(_wake_phrases())
    phrases.extend(COMMAND_PHRASES)
    phrases.extend(FILLER_WORDS)
    for name in sorted(med_names or set()):
        # DB names are snake_case ('vitamin_d3'); spoken form is space-separated.
        spoken = name.replace("_", " ").strip().lower()
        if spoken:
            phrases.append(spoken)
    seen: set[str] = set()
    out: list[str] = []
    for p in phrases:
        p = p.strip().lower()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    out.append(UNK)
    return out


def build_grammar(med_names: set[str] | None = None) -> str:
    """The phrase list as the JSON string ``KaldiRecognizer`` expects."""
    return json.dumps(build_phrases(med_names))
