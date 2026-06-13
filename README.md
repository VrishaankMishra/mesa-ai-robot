# MeSA 2.0 — Medication & Safety Assistant Robot

A tabletop assistive robot (Raspberry Pi 5) that helps an at-risk person stay safe and on
schedule with medication: it recognizes medication bottles, logs when they're taken,
watches for falls, answers voice questions, and escalates to a caregiver if something's
wrong.

> ⚠️ **Assistive aid, not a medical device.** Fall detection is tested only with staged
> poses on cushions and must not be relied on for real emergencies.

## Features (the five demos)
1. **MED** — recognizes 5+ medication bottles, flags unknown ones as "wrong medication".
2. **LOG** — removing/returning a bottle logs a timestamped `taken` event, shown live on a dashboard.
3. **FALL** — classifies standing/sitting/lying; sustained lying triggers a spoken check-in.
4. **VOICE** — offline voice assistant: next med, did-I-take, call-for-help, date/time.
5. **ESCALATE** — no response → 3-level escalation (spoken check-in → push notification → caregiver alert).
6. *(Stretch)* servo head tracks the person; OLED shows emotion states; CSV → schedule generator.

## Architecture
One process, one event queue. Vision and audio workers publish events; the decision engine
consumes them and drives compliance, fall, and escalation logic.

```
USB cam ─▶ Vision (YOLOv8n detect + MediaPipe pose) ─┐
USB mic ─▶ Audio  (Vosk STT + pyttsx3 TTS)           ├─▶ EventBus ─▶ Decision engine ─┬─▶ SQLite (events.db)
                                                     │                                ├─▶ Streamlit dashboard (LAN)
                                                     │                                ├─▶ ntfy.sh / Twilio alerts
                                                     └────────────────────────────────┴─▶ Hardware: PCA9685 servos, SSD1306 OLED
```

## Layout
```
mesa/
├── vision/      detector.py (YOLO wrapper + unknown-bottle logic), posture.py (fall)
├── audio/       intents.py, assistant.py, stt.py (swappable), tts.py
├── engine/      database.py, presence.py, compliance.py, escalation.py,
│                inactivity.py, events.py, decision.py, schedule_gen.py
├── hardware/    tracking.py, servos.py, oled.py, emotions.py  (Pi-only behind plug modules)
└── dashboard/   app.py (Streamlit)
scripts/   capture, detect_live, pose_live, voice_loop, benchmark, soak_test, import_schedule, create_issues
deploy/    mesa.service, install_pi.sh
docs/      IMPLEMENTATION.md, capture-protocol.md, roboflow-setup.md, hardware-build.md, test-plan.md
```

## Quick start (laptop, no hardware)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .          # makes `mesa` importable + scripts runnable
.venv/bin/python -m pytest          # all tests green
.venv/bin/python main.py --demo     # runs a synthetic event sequence end-to-end
```

## Running for real
| What | Command | Needs |
|------|---------|-------|
| Live detection | `python scripts/detect_live.py` | camera + `models/best.pt` |
| Live posture/fall | `python scripts/pose_live.py --echo` | camera |
| Voice loop | `python scripts/voice_loop.py` | mic/speaker + Vosk model |
| Dashboard | `bash scripts/run_dashboard.sh` | — (LAN at `:8501`) |
| Import schedule | `python scripts/import_schedule.py examples/prescriptions.csv` | — |
| FPS benchmark | `python scripts/benchmark.py` | camera + models |

Config (thresholds, model paths, ntfy topic) lives in [`config.yaml`](config.yaml).
Models and datasets are gitignored — see [`models/README.md`](models/README.md) and
[`datasets/README.md`](datasets/README.md).

## Build it
- **Plan + tickets:** [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)
- **Hardware/robotics playbook:** [docs/hardware-build.md](docs/hardware-build.md)
- **Manual test plan:** [docs/test-plan.md](docs/test-plan.md)

## Tech
Python 3.11 · OpenCV · Ultralytics YOLOv8 · MediaPipe · Vosk · pyttsx3 · SQLite · Streamlit
· ntfy.sh · gpiozero / Adafruit CircuitPython (PCA9685, SSD1306).
