#!/usr/bin/env python3
"""Check which grammar phrases the Vosk model can actually decode (VOX-007).

Vosk silently drops grammar words that are missing from the acoustic model's lexicon
(with only a warning on stderr). A medication name that gets dropped is a command that
can never be recognized — and you do not want to discover that with an audience in the
room. Run this after changing the medication list and before any demo.

    python scripts/check_vocabulary.py
    python scripts/check_vocabulary.py --db events.db

Exit code is non-zero if any phrase is undecodable, so it can gate a demo checklist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mesa.audio.vocabulary import UNK, build_phrases  # noqa: E402
from mesa.config import get, load_config  # noqa: E402
from mesa.data.database import Database  # noqa: E402


def load_lexicon(model_path: Path) -> set[str] | None:
    """Words the model knows, read from its graph vocabulary file if one is present."""
    # Vosk ships the decoding vocabulary as graph/words.txt; older//repacked layouts
    # sometimes put it under am/. Anything else is not a word list.
    for rel in ("graph/words.txt", "am/words.txt"):
        f = model_path / rel
        if not f.exists():
            continue
        words = set()
        for line in f.read_text(errors="ignore").splitlines():
            tok = line.split(" ", 1)[0].strip().lower()
            if tok and not tok.startswith("#"):
                words.add(tok)
        if words:
            return words
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="events.db", help="database to read medication names from")
    ap.add_argument("--model", default=None, help="override the Vosk model path")
    args = ap.parse_args()

    cfg = load_config()
    model_path = Path(args.model or get(cfg, "voice.vosk_model_path",
                                        "models/vosk-model-small-en-us"))

    med_names: set[str] = set()
    if Path(args.db).exists():
        db = Database(args.db)
        med_names = {m["name"] for m in db.list_medications(active_only=False)}
        med_names |= {s["med_name"] for s in db.get_schedule()}
        db.close()
        print(f"medications from {args.db}: {len(med_names)}")
    else:
        print(f"[warn] no database at {args.db} — checking command phrases only.")

    phrases = build_phrases(med_names)
    print(f"grammar: {len(phrases)} phrases\n")

    if not model_path.exists():
        print(f"[warn] no Vosk model at {model_path} — cannot verify against a lexicon.")
        print("       Phrases that would be sent:")
        for p in phrases:
            print(f"         {p}")
        return 0

    lexicon = load_lexicon(model_path)
    if lexicon is None:
        print(f"[warn] could not read a words.txt lexicon under {model_path};")
        print("       run the voice loop and watch stderr for Vosk's OOV warnings instead.")
        return 0

    print(f"model lexicon: {len(lexicon)} words ({model_path})\n")
    bad = []
    for phrase in phrases:
        if phrase == UNK:
            continue
        missing = [w for w in phrase.split() if w not in lexicon]
        if missing:
            bad.append((phrase, missing))

    if not bad:
        print(f"OK — all {len(phrases) - 1} phrases are decodable.")
        return 0

    # Split the report: a medication name that cannot be decoded is a command the user can
    # never issue, and is fixed in the database. A missing word in a built-in command phrase
    # is a different problem with a different fix — telling someone to "rename the
    # medication" because "what time is it" lost the word "it" sends them the wrong way.
    spoken_meds = {n.replace("_", " ").strip().lower() for n in med_names}
    bad_meds = [(p, m) for p, m in bad if p in spoken_meds]
    bad_cmds = [(p, m) for p, m in bad if p not in spoken_meds]

    print(f"UNDECODABLE — {len(bad)} phrase(s) contain words the model does not know:\n")
    if bad_meds:
        print("  MEDICATION NAMES (these commands can never be recognized):")
        for phrase, missing in bad_meds:
            print(f"    {phrase!r}  ->  missing: {', '.join(missing)}")
        print("\n  Fix: rename to a pronounceable in-vocabulary form in the schedule/")
        print("  medications table (e.g. 'omeprazole' -> 'stomach pill'). Say the new name")
        print("  aloud in the demo script too — the label the user speaks must match.\n")
    if bad_cmds:
        print("  COMMAND PHRASES (built-in wording this model cannot decode):")
        for phrase, missing in bad_cmds:
            print(f"    {phrase!r}  ->  missing: {', '.join(missing)}")
        print("\n  Fix: reword or drop the phrase in mesa/audio/vocabulary.py. Other")
        print("  phrasings of the same intent still cover it.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
