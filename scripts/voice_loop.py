#!/usr/bin/env python3
"""Voice assistant runtime loop (VOX-001 + wiring).

Ties it together: Vosk STT -> wake-word gate -> intent parse -> assistant response ->
TTS. Run manually on the laptop/Pi with a microphone + a downloaded Vosk model.

    python scripts/voice_loop.py --echo      # print responses instead of speaking

Pure logic (parsing, responses) lives in mesa.audio.* and is unit-tested; this script is
the hardware-bound glue and is not part of the test suite.
"""

from __future__ import annotations

import argparse

from mesa.alerts.ntfy import send_alert
from mesa.audio.assistant import VoiceAssistant
from mesa.audio.intents import DEFAULT_WAKE_WORD, parse_intent, strip_wake_word
from mesa.audio.stt import VoskRecognizer
from mesa.audio.tts import speak
from mesa.config import get, load_config
from mesa.data.database import Database


def main() -> int:
    cfg = load_config()
    p = argparse.ArgumentParser(description="MeSA voice loop")
    p.add_argument("--model", default=get(cfg, "voice.vosk_model_path", "models/vosk-model-small-en-us"))
    p.add_argument("--echo", action="store_true", help="print responses instead of speaking")
    args = p.parse_args()

    wake = get(cfg, "voice.wake_word", DEFAULT_WAKE_WORD)
    topic = get(cfg, "alerts.ntfy_topic", "")

    db = Database()
    assistant = VoiceAssistant(db, alert_fn=lambda msg: send_alert(topic, msg, title="MeSA help"))
    recognizer = VoskRecognizer(args.model)

    print(f"Listening. Say '{wake}' then a command. Ctrl-C to stop.")
    for transcript in recognizer.listen():
        if wake not in transcript.lower():
            continue
        command = strip_wake_word(transcript, wake)
        parsed = parse_intent(command)
        reply = assistant.respond(parsed)
        speak(reply, echo=args.echo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
