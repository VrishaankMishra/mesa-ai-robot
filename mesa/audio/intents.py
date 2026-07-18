"""Voice intent parsing (VOX-002).

Pure keyword/regex intent classification — no audio, no model — so it can be exhaustively
unit-tested. The STT loop (VOX-001) feeds transcribed text here after the wake word.

Four command intents — NEXT_MED, DID_I_TAKE, HELP, DATE_TIME — plus OKAY, the answer to
an escalation check-in ("Are you okay?" → "MeSA, I'm okay"), which lets a voice reply
de-escalate. Everything else is UNKNOWN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

DEFAULT_WAKE_WORD = "mesa"


class Intent(Enum):
    NEXT_MED = "next_med"
    DID_I_TAKE = "did_i_take"
    HELP = "help"
    DATE_TIME = "date_time"
    OKAY = "okay"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ParsedIntent:
    intent: Intent
    med: str | None = None  # raw medication phrase for DID_I_TAKE, normalized (snake_case)


# Patterns are checked in priority order: HELP (safety) first, then most specific.
# Negated help ("I don't need help") is blanked out before the HELP check so it can't
# false-trigger an alert, while any other mention of help still wins over OKAY.
_HELP = re.compile(r"\b(help|emergency|fall(en)?|i'?ve fallen|call (for help|someone|911))\b")
_NEGATED_HELP = re.compile(r"\b(?:don'?t|do not|no) need (?:any )?(?:help|anything)\b")
_OKAY = re.compile(r"\b(i'?m (okay|ok|fine|alright|all right|good)|(yes\s+)?i'?m up|all good|no problem|never mind|i don'?t need (any\s*)?(help|anything))\b")
_DID_I_TAKE = re.compile(r"\b(did|have) i (already )?(take|taken|had)\b")
_NEXT_MED = re.compile(r"\b(next (med|medication|pill|dose)|what.*next|when.*next med)")
_DATE_TIME = re.compile(r"\b(what.*(time|date|day)|today'?s date|the date|the time)\b")

# Captures the medication phrase after "take/taken/had", trimming trailing fluff.
_MED_AFTER_TAKE = re.compile(
    r"\b(?:take|taken|had)\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:today|yet|already|this))?[?.!]*$"
)


def normalize_med(phrase: str) -> str:
    """'Vitamin D' -> 'vitamin_d'. Used to match against DB medication names."""
    return re.sub(r"\s+", "_", phrase.strip().lower())


def strip_wake_word(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> str:
    """Remove a leading wake word (and trailing comma) if present."""
    pattern = re.compile(rf"^\s*{re.escape(wake_word)}[,\s]+", re.IGNORECASE)
    return pattern.sub("", text, count=1)


def parse_intent(text: str) -> ParsedIntent:
    """Classify a transcribed utterance. Assumes the wake word is already stripped."""
    t = text.lower().strip()
    if _HELP.search(_NEGATED_HELP.sub("", t)):
        return ParsedIntent(Intent.HELP)
    if _OKAY.search(t):
        return ParsedIntent(Intent.OKAY)
    if _DID_I_TAKE.search(t):
        med = None
        m = _MED_AFTER_TAKE.search(t)
        if m and m.group(1).strip():
            med = normalize_med(m.group(1))
        return ParsedIntent(Intent.DID_I_TAKE, med=med)
    if _NEXT_MED.search(t):
        return ParsedIntent(Intent.NEXT_MED)
    if _DATE_TIME.search(t):
        return ParsedIntent(Intent.DATE_TIME)
    return ParsedIntent(Intent.UNKNOWN)
