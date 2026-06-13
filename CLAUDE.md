# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## Project

**MeSA 2.0 — Medication & Safety Assistant Robot.** A tabletop assistive robot built
on a Raspberry Pi 5 that helps an elderly or at-risk person stay safe and on-schedule
with medication. Target: a working demo prototype in 10 weeks (~June 15 – Aug 23, 2026).

> **Not a medical device.** This is an assistive aid. Fall/posture detection must be
> tested only with staged poses on cushions, and everything user-facing should make the
> "assistive aid, not a medical device" framing clear.

See `mesa-2_0-project-plan*.pdf` for the full technical design, BOM, and ticket list.

## The five core demos (Definition of Done)

1. **MED** — detect 5+ medication bottles at ≥90% top-1 accuracy (0.5–1.5 m); flag unknown bottles as "wrong medication".
2. **LOG** — removing/returning a bottle writes a timestamped `taken` event to SQLite, visible on the Streamlit dashboard.
3. **FALL** — classify standing/sitting/lying in real time; lying >30 s triggers a spoken check-in.
4. **VOICE** — four commands end-to-end (next med, did-I-take, call for help, date/time) with spoken responses.
5. **ESCALATE** — no-movement timeout drives 3-level escalation: L1 ask → L2 notify → L3 caregiver alert.
6. *(Stretch)* servo head tracks the person; OLED shows emotion states.

## Architecture

One main process with worker threads/processes communicating over a
`multiprocessing.Queue` event bus (no MQTT/network IPC at this scale):

- **Vision service** — YOLOv8n (medication detection) + MediaPipe Pose (posture), sharing one camera feed via a frame router. Detection every 3rd frame; pose every frame at 640×480.
- **Audio loop** — Vosk (offline STT, wake word "MeSA") → intent parser → pyttsx3 (TTS).
- **Decision engine** — state machine: medication compliance tracker, fall/inactivity timers, escalation logic (L1→L2→L3).
- **Outputs** — SQLite (`events.db`), Streamlit dashboard (LAN), ntfy.sh push alerts (Twilio SMS optional), hardware I/O (PCA9685 servos + SSD1306 OLED, Pi only).

## Tech stack

- **Language:** Python 3.11 (same on laptop and Pi).
- **Vision:** OpenCV, Ultralytics YOLOv8, MediaPipe. Dataset via Roboflow; training on Colab.
- **Audio:** Vosk (STT), pyttsx3 (TTS), sounddevice/pyaudio — all offline.
- **Data:** SQLite via `sqlite3` stdlib. Tables: `events`, `medications`, `schedule`.
- **Dashboard:** Streamlit.
- **Alerts:** `requests` → ntfy.sh; optional Twilio.
- **Hardware I/O (Pi only):** gpiozero, `adafruit-circuitpython-pca9685`, `adafruit-circuitpython-ssd1306`.
- **Testing:** pytest (unit) + recorded-video fixtures (integration).
- **Config:** all thresholds (timeouts, confidence, schedule) live in one `config.yaml`.
- **Packaging:** `requirements.txt` (laptop) + `requirements-pi.txt` (Pi); systemd service for boot.

## Conventions

- **Develop on laptop first, deploy to Pi.** The Pi is only required from Week 7 on; keep
  hardware-only code (`gpiozero`, Adafruit libs) import-isolated so laptop dev/tests run without it.
- **Abstract swappable subsystems behind a single module** so they can be replaced without
  touching callers — e.g. STT (Vosk → whisper-tiny fallback) lives behind one interface.
- **Tickets** follow `AREA-###` IDs with labels `vision`, `voice`, `engine`, `hw`, `infra`, `docs`.
  Work happens on **feature branches**; close a ticket only when its acceptance criteria are met.
- **Tests:** keep the existing unit tests green; add pytest coverage for new engine/DB logic.
  Use simulated time for escalation-timer tests (don't sleep in tests).
- Keep evaluation artifacts (confusion matrix, precision/recall, FPS benchmarks) under `docs/`.

## Git / commits

- **All commits in this repo are authored as `VrishaankMishra <vrishaank.mishra@gmail.com>`**
  (set via local git config). Do **not** add a `Co-Authored-By` trailer or any other author.
- Commit to a feature branch, not `main`, and only commit/push when explicitly asked.
