#!/usr/bin/env python3
"""Voice-reliability evaluation session (RES-004 / paper #2 data).

The audio sibling of eval_capture.py, using the same free-ground-truth trick: the robot
SPEAKS each prompt, the operator repeats it after the cue, and the expected utterance +
intent are known by construction — zero annotation. One session = one grid cell
(distance × background-noise × speaker), ~4 minutes, 18 scripted trials.

    .venv/bin/python scripts/eval_voice_capture.py --condition d1m_quiet_vrishaank

Cell naming: d{1m|2m|3m}_{quiet|tv}_{speaker}. Stand at the marked distance from the
speakerphone; for 'tv' cells, the TV/music plays at a fixed volume agreed in the
protocol doc. Results land in eval_voice/<condition>/<session>/manifest.csv with the
transcript, wake detection, and parsed intent per trial.

Hardware-bound glue; scoring lives in the manifest columns and eval_voice_analyze.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from mesa.audio.intents import DEFAULT_WAKE_WORD, parse_intent, strip_wake_word

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO_ROOT / "eval_voice"

# (utterance to repeat, expected_intent or None, wake word expected in it)
SCRIPT = [
    ("mesa what is my next medication",      "next_med",  True),
    ("mesa what's next",                     "next_med",  True),
    ("mesa when is my next pill",            "next_med",  True),
    ("mesa did I take my advil",             "did_i_take", True),
    ("mesa did I take my melatonin today",   "did_i_take", True),
    ("mesa have I taken my vitamin d",       "did_i_take", True),
    ("mesa what time is it",                 "date_time", True),
    ("mesa what day is it today",            "date_time", True),
    ("mesa what's the date",                 "date_time", True),
    ("mesa call for help",                   "help",      True),
    ("mesa help me",                         "help",      True),
    ("mesa I'm okay",                        "okay",      True),
    ("mesa im ok",                           "okay",      True),
    ("mesa I don't need help",               "okay",      True),  # negation guard trial
    ("mesa tell me a joke",                  "unknown",   True),
    ("what time is it",                      None,        False),  # control: no wake word
    ("did I take my advil",                  None,        False),  # control: no wake word
    ("may sun is bright today",              None,        False),  # near-homophone control
]

RECORD_SECONDS = 5.0
SAMPLE_RATE = 16000


def say(text: str) -> None:
    print(f"[say] {text}", flush=True)
    subprocess.run(["espeak-ng", "-s", "155", text], check=False)


def transcribe(audio_bytes: bytes, model) -> str:
    from vosk import KaldiRecognizer

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.AcceptWaveform(audio_bytes)
    return json.loads(rec.FinalResult()).get("text", "").strip()


def main() -> int:
    p = argparse.ArgumentParser(description="MeSA voice-grid evaluation session")
    p.add_argument("--condition", required=True,
                   help="cell label, e.g. d1m_quiet_vrishaank / d3m_tv_mom")
    p.add_argument("--model", default="models/vosk-model-small-en-us")
    p.add_argument("--record-seconds", type=float, default=RECORD_SECONDS)
    args = p.parse_args()

    import numpy as np
    import sounddevice as sd
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    model = Model(args.model)

    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / args.condition / session
    out_dir.mkdir(parents=True, exist_ok=True)
    mf = open(out_dir / "manifest.csv", "w", newline="")
    w = csv.writer(mf)
    w.writerow(["condition", "session", "trial", "prompt", "expected_intent",
                "wake_expected", "transcript", "wake_detected", "parsed_intent",
                "exact_wake_and_intent"])

    say(f"Voice evaluation, condition {args.condition.replace('_', ' ')}. "
        "After each beep, repeat the phrase exactly, at a normal speaking voice.")
    time.sleep(1.0)

    correct = 0
    for i, (utterance, expected_intent, wake_expected) in enumerate(SCRIPT):
        say(f'Repeat: "{utterance}"')
        time.sleep(0.6)
        subprocess.run(["espeak-ng", "-s", "300", "-p", "80", "go"], check=False)
        audio = sd.rec(int(args.record_seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                       channels=1, dtype="int16")
        sd.wait()
        transcript = transcribe(np.asarray(audio).tobytes(), model)

        wake_detected = DEFAULT_WAKE_WORD in transcript.lower()
        parsed = (parse_intent(strip_wake_word(transcript, DEFAULT_WAKE_WORD)).intent.value
                  if wake_detected else "")
        ok = (wake_detected == wake_expected) and (
            not wake_expected or parsed == expected_intent)
        correct += int(ok)
        print(f"  [{i+1:02d}/{len(SCRIPT)}] heard='{transcript}' wake={wake_detected} "
              f"intent={parsed or '-'} {'OK' if ok else 'MISS'}", flush=True)
        w.writerow([args.condition, session, i, utterance, expected_intent or "",
                    int(wake_expected), transcript, int(wake_detected), parsed, int(ok)])
        mf.flush()

    mf.close()
    say(f"Session done. {correct} of {len(SCRIPT)} trials fully correct.")
    print(f"SESSION COMPLETE: {correct}/{len(SCRIPT)} -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
