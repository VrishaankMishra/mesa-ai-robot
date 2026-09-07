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

# Vosk splits "MAY-suh" into two words more often than it gets it whole. Measured across
# the 2026-09-05 quiet grid (45 wake-expected trials, 13 missed), the misses were:
#   "may so"  x6   "made so" x2   "mr" x3   "ms raisa" x1   "nice that" x1  "they saw" x1
# Accepting the two-token variants recovers 8 of 13 and lifts wake detection from 71% to
# 89% with no retraining.
#
# "mr" is deliberately EXCLUDED. It would recover three more (96%), but it is one short
# token that Vosk produces from all kinds of unclear audio — and on this system a false
# wake can reach the HELP intent, which alerts a caregiver. A missed wake costs a repeat;
# a false wake costs trust. That trade is not symmetric.
#
# Matching is token-based, not substring. The near-homophone control transcribed as
# "may son as bright today", which CONTAINS the substring "may so" — a naive substring
# match would false-wake on the very trial designed to catch that.
WAKE_VARIANTS: tuple[tuple[str, ...], ...] = (
    ("mesa",),
    ("may", "so"),
    ("made", "so"),
)

_TOKEN = re.compile(r"[a-z']+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def matches_wake_word(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> bool:
    """True if the transcript contains the wake word or a measured mishearing of it.

    Token-based so that "may son" does not match the ("may", "so") variant.
    """
    toks = _tokens(text)
    variants = tuple(WAKE_VARIANTS)
    if wake_word != DEFAULT_WAKE_WORD:
        variants = ((wake_word.lower(),),)
    for var in variants:
        n = len(var)
        for i in range(len(toks) - n + 1):
            if tuple(toks[i:i + n]) == var:
                return True
    return False


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
    """Remove a leading wake word — or a measured mishearing of it — and trailing comma."""
    pattern = re.compile(rf"^\s*{re.escape(wake_word)}[,\s]+", re.IGNORECASE)
    out = pattern.sub("", text, count=1)
    if out != text:
        return out
    for var in WAKE_VARIANTS:
        if var == (wake_word.lower(),):
            continue
        gap = r"[,\s]+"
        joined = gap.join(re.escape(w) for w in var)
        alt = re.compile(r"^\s*" + joined + r"[,\s]+", re.IGNORECASE)
        out = alt.sub("", text, count=1)
        if out != text:
            return out
    return text


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
