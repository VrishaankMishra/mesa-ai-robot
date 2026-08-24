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

# The grid's independent variable is distance from the SP300U speakerphone, so the mic is
# part of the method, not a detail. sounddevice's default input resolves through ALSA
# "default" -> pulse -> whatever pulse picks, and the Pi has a second microphone in the
# C920. Card numbers also move across reboots (the SP300U was card 3 in July and card 2 on
# 2026-08-24). An unpinned default would silently make "3m from the speakerphone" mean
# "3m from the webcam", and the manifest would not say so.
DEFAULT_INPUT_DEVICE = "SP300U"


def pick_capture_rate(supported, device_default: float, wanted: int = 16000) -> int:
    """Choose the rate to actually record at.

    Vosk wants 16 kHz, but a pinned *hardware* device offers only what the hardware
    offers — the SP300U accepts 48000 and nothing else. sounddevice's "default" device
    hid this because pulse resamples silently; pinning the mic (which the method
    requires) means negotiating the rate ourselves. ``supported`` is a predicate taking
    a rate and returning whether the device accepts it.
    """
    if supported(wanted):
        return wanted
    return int(device_default)


def to_vosk_rate(audio, from_rate: int, to_rate: int = 16000):
    """Resample int16 mono audio to ``to_rate``. Identity when the rates already match.

    Prefers scipy's polyphase resampler (properly anti-aliased). Falls back to a box
    filter for integer ratios — averaging N samples both low-passes and decimates, which
    is crude but does not alias speech down into the band Vosk reads. A last-resort
    linear interpolation covers non-integer ratios.
    """
    import numpy as np

    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if int(from_rate) == int(to_rate):
        return np.clip(np.round(x), -32768, 32767).astype(np.int16)

    try:
        from math import gcd

        from scipy.signal import resample_poly
        g = gcd(int(from_rate), int(to_rate))
        y = resample_poly(x, int(to_rate) // g, int(from_rate) // g)
    except ImportError:
        if int(from_rate) % int(to_rate) == 0:
            n = int(from_rate) // int(to_rate)
            usable = (len(x) // n) * n
            y = x[:usable].reshape(-1, n).mean(axis=1)
        else:
            new_len = int(round(len(x) * to_rate / from_rate))
            y = np.interp(np.linspace(0, len(x) - 1, new_len), np.arange(len(x)), x)

    return np.clip(np.round(y), -32768, 32767).astype(np.int16)


def resolve_input_device(spec: str, devices: list[dict]) -> tuple[int, str]:
    """Resolve ``spec`` (an index, or a case-insensitive name substring) to (index, name).

    Only devices with input channels are eligible. Raises ValueError listing what IS
    available rather than falling back to a default — recording the wrong microphone
    invalidates a session silently, which is worse than not recording at all.
    """
    inputs = [(i, d) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]

    if spec.isdigit():
        idx = int(spec)
        for i, d in inputs:
            if i == idx:
                return i, d["name"]
        raise ValueError(f"device index {idx} is not an input device")

    matches = [(i, d["name"]) for i, d in inputs if spec.lower() in d["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(f"{i}:{d['name']}" for i, d in inputs) or "none"
    if not matches:
        raise ValueError(f"no input device matching {spec!r}. Available: {available}")
    raise ValueError(f"{spec!r} matches {len(matches)} devices: "
                     + ", ".join(f"{i}:{n}" for i, n in matches))


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
    p.add_argument("--device", default=DEFAULT_INPUT_DEVICE,
                   help="input device index or name substring (default: the SP300U)")
    args = p.parse_args()

    import numpy as np
    import sounddevice as sd
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)

    dev_index, dev_name = resolve_input_device(args.device, list(sd.query_devices()))

    def _supported(rate: int) -> bool:
        try:
            sd.check_input_settings(device=dev_index, samplerate=rate,
                                    channels=1, dtype="int16")
            return True
        except Exception:
            return False

    capture_rate = pick_capture_rate(
        _supported, sd.query_devices(dev_index)["default_samplerate"], SAMPLE_RATE)
    note = "" if capture_rate == SAMPLE_RATE else f" (resampled to {SAMPLE_RATE})"
    print(f"[voice] recording from device {dev_index}: {dev_name} "
          f"@ {capture_rate} Hz{note}", flush=True)

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
        audio = sd.rec(int(args.record_seconds * capture_rate), samplerate=capture_rate,
                       channels=1, dtype="int16", device=dev_index)
        sd.wait()
        pcm16k = to_vosk_rate(audio, capture_rate, SAMPLE_RATE)
        transcript = transcribe(pcm16k.tobytes(), model)

        wake_detected = DEFAULT_WAKE_WORD in transcript.lower()
        parsed = (parse_intent(strip_wake_word(transcript, DEFAULT_WAKE_WORD)).intent.value
                  if wake_detected else "")
        ok = (wake_detected == wake_expected) and (
            not wake_expected or parsed == expected_intent)
        correct += int(ok)
        print(f"  [{i+1:02d}/{len(SCRIPT)}] heard='{transcript}' wake={wake_detected} "
              f"intent={parsed or '-'} {'OK' if ok else 'MISS'}", flush=True)
        w.writerow([args.condition, session, i, utterance, expected_intent or "",
                    int(wake_expected), transcript, int(wake_detected), parsed, int(ok),
                    dev_name, capture_rate])
        mf.flush()

    mf.close()
    say(f"Session done. {correct} of {len(SCRIPT)} trials fully correct.")
    print(f"SESSION COMPLETE: {correct}/{len(SCRIPT)} -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
