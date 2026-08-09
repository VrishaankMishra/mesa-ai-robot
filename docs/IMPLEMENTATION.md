# MeSA 2.0 — Step-by-Step Implementation Plan

> **STATUS (2026-08-09):** Weeks 1–6 complete and live-verified (4 of 5 core demos:
> MED, LOG, FALL, VOICE; ESCALATE needs one live run — ntfy topic now set). A research
> extension (domain-shift study) completed Aug 8–9: docs/eval/ + docs/paper/. Remaining:
> ESCALATE live test, systemd + soak (HW-002/003, ENG-007), dashboard-on-LAN check
> (DASH-002), on-Pi servo/OLED verification (HW-004–006), demo video + rehearsal
> (Week 10). Day-by-day history: docs/engineering-notebook.md.

Derived from `mesa-2_0-project-plan*.pdf`. This is the working build guide: do the steps
in order, close each ticket only when its **acceptance criteria (AC)** are met, and commit
on a feature branch per ticket.

- **Target:** working tabletop prototype by ~Aug 23, 2026 (10 weeks from Jun 15).
- **Budget:** ~12 hrs/week (~120–150 hrs total).
- **Golden rule:** build on the laptop first; the Pi is only truly required from Week 7.
- **Labels:** `vision` `voice` `engine` `hw` `infra` `docs`.

---

## Phase 0 — Repo foundation (do this first, before Week 1 tickets)

This scaffolding is what the plan assumes already exists ("Layer 1 software scaffolded").
The repo currently has only `README.md` + `CLAUDE.md`, so stand it up now.

- [ ] **Create the project layout:**
  ```
  mesa-ai-robot/
  ├── mesa/                  # package source
  │   ├── __init__.py
  │   ├── vision/            # detection + pose
  │   ├── audio/             # STT/TTS
  │   ├── engine/            # state machine, escalation, compliance
  │   ├── data/              # SQLite schema + DAO
  │   ├── hardware/          # Pi-only: servos, OLED (import-isolated)
  │   └── dashboard/         # Streamlit app
  ├── tests/                 # pytest
  ├── docs/                  # this file, eval reports, journal.md
  ├── config.yaml            # all thresholds live here
  ├── requirements.txt       # laptop deps
  ├── requirements-pi.txt    # Pi-only deps
  └── main.py                # orchestrator entry point
  ```
- [ ] Create `venv`, add pinned `requirements.txt` (opencv-python, ultralytics, mediapipe, vosk, pyttsx3, sounddevice, streamlit, requests, pyyaml, pytest).
- [ ] Add a trivial unit test + `pytest` config so `pytest` runs green from day one.
- [ ] Stub `config.yaml` with placeholder thresholds (confidence, timeouts, schedule).
- [ ] First commit on a feature branch.

---

## Week 1 (Jun 15–21) — Dataset & Dev Environment
**Milestone M1: annotated dataset v1 uploaded to Roboflow.**

- [x] **INFRA-001** (2h) — Dev environment on laptop: repo cloned, venv with pinned `requirements.txt`, existing unit tests pass.
- [ ] **INFRA-002** (1h) — Create GitHub Issues board: all tickets entered with labels + milestones.
- [x] **VIS-001** (2h) — Capture rig + photo protocol: fixed camera position documented; lighting/angle/distance checklist written.
- [x] **VIS-002** (5h) — Capture ≥600 images across 6 bottles: 3 lighting conditions × 3 angles × 3 distances, incl. cluttered backgrounds.
- [x] **VIS-003** (3h) — Annotate in Roboflow: all images boxed + labeled; 70/20/10 train/val/test split; augmentations configured.

**Proof:** Roboflow project link.

---

## Week 2 (Jun 22–28) — Train & Evaluate Detector
**Milestone M2: fine-tuned YOLOv8n ≥90% mAP@50 on val set.**

- [x] **VIS-004** (4h) — Train YOLOv8n on Colab: training notebook in repo; `best.pt` exported; ≥90% mAP@50.
- [x] **VIS-005** (2h) — Evaluation report: confusion matrix + per-class precision/recall committed to `/docs`; failure cases listed.
- [x] **VIS-006** (4h) — Live inference: `detect_live.py` shows boxes + confidence ≥5 FPS on laptop; "unknown bottle" path when confidence < threshold.
- [ ] **VIS-007** (2h) — Hard-negative round: +50 failure-case images added; retrain if mAP < 90%.

**Proof:** eval report in repo.

---

## Week 3 (Jun 29–Jul 5) — Compliance Tracking & Database
**Milestone M3: bottle removed/returned → event logged in SQLite.**

- [x] **ENG-001** (3h) — SQLite schema + data access module: `events`, `medications`, `schedule` tables; CRUD functions; pytest coverage.
- [x] **ENG-002** (4h) — Per-bottle presence state machine: `present → absent → returned`; debounced 3 s so hand occlusion doesn't false-trigger.
- [x] **ENG-003** (2h) — "Medication taken" rule: absent ≥10 s then returned → `taken` event with timestamp + med name.
- [x] **DASH-001** (3h) — Extend Streamlit dashboard: today's meds, taken/missed status, event-history table reading live from SQLite.

> **⏰ Order the Pi 5 bundle (H1–H4) this week** so it arrives before Week 5/7.

**Proof:** dashboard shows a live "taken" event.

---

## Week 4 (Jul 6–12) — Voice Assistant
**Milestone M4: 4 voice commands working end-to-end on laptop.**

- [x] **VOX-001** (4h) — Mic capture + Vosk STT loop: continuous transcription; wake word "MeSA" gates commands.
- [x] **VOX-002** (3h) — Intent parser: keyword/regex intents `NEXT_MED`, `DID_I_TAKE`, `HELP`, `DATE_TIME`; unit-tested on 20 phrasings each.
- [x] **VOX-003** (3h) — Intent → DB → spoken answer: "Did I take Vitamin D?" answers correctly from real `events` via pyttsx3.
- [x] **VOX-004** (2h) — HELP intent → alert stub: "Call for help" sends an ntfy.sh push.

> Keep STT behind one module so Vosk can be swapped for whisper-tiny if accuracy is poor.

**Proof:** screen recording.

---

## Week 5 (Jul 13–19) — Fall Detection + Pi Bring-up
**Milestone M5: standing/sitting/lying classified live; Pi 5 running the detector.**

- [x] **VIS-008** (2h) — MediaPipe Pose integration: 33 keypoints rendered live ≥10 FPS (laptop).
- [x] **VIS-009** (5h) — Posture classifier: torso-angle + hip/shoulder-height rules classify standing/sitting/lying ≥90% accuracy on a 50-clip test set.
- [x] **VIS-010** (2h) — Lying-duration trigger: lying >30 s fires `possible_fall`; spoken "Are you okay?" check-in.
- [x] **HW-001** (3h) — Pi 5 setup: Pi OS 64-bit, SSH, camera working, repo deployed, YOLO+pose FPS benchmarked and recorded.

> **⚠️ Safety:** test falls with staged poses on cushions only. Document "assistive aid, not a medical device."

**Proof:** posture demo clip + Pi FPS benchmark.

---

## Week 6 (Jul 20–26) — Decision Engine Integration
**Milestone M6: all subsystems running together from one entry point (laptop).**

- [x] **ENG-004** (5h) — Event bus + orchestrator: `main.py` launches vision, audio, engine threads; all events flow through one queue.
- [x] **ENG-005** (4h) — Escalation state machine: L1 check-in → 60 s no response → L2 ntfy → no response → L3 caregiver alert; fully unit-tested with simulated time.
- [x] **ENG-006** (2h) — Inactivity monitor: no person/motion for configurable window (default 1 h) → escalation L1.
- [x] **INFRA-003** (1h) — Config file: all thresholds (timeouts, confidence, schedule) in `config.yaml`.

> **⏰ Order servos, PCA9685, pan-tilt kit, OLED (H8–H11)** this week.

**Proof:** one-command launch, all events flowing.

---

## Week 7 (Jul 27–Aug 2) — Full System on Raspberry Pi
**Milestone M7: end-to-end demo runs on the Pi unattended for 2+ hours.**

- [ ] **HW-002** (5h) — Port full stack to Pi: all Week-6 functionality; `requirements-pi.txt`; perf tuning (frame skipping, resolution) to keep pose ≥5 FPS.
- [ ] **HW-003** (2h) — systemd service: MeSA auto-starts on boot; logs to file; survives reboot.
- [ ] **ENG-007** (4h) — Soak test + bug bash: 2-hour continuous run; no crashes; memory stable; issues filed and fixed.
- [ ] **DASH-002** (1h) — Dashboard reachable on LAN: phone/laptop on same Wi-Fi can view it served from the Pi.

**Proof:** systemd logs.

---

## Week 8 (Aug 3–9) — Robotic Personality
**Milestone M8: servo head tracks person; OLED shows emotion states.**
*(If hardware is delayed, swap Week 8 ↔ Week 9.)*

- [ ] **HW-004** (3h) — PCA9685 + pan-tilt assembly: camera on pan-tilt; servos sweep via script.
- [ ] **HW-005** (4h) — Face/person tracking head: head keeps detected person centered (proportional control); no jitter/oscillation.
- [ ] **HW-006** (3h) — OLED emotion display: idle / alert / greeting states driven by engine events.
- [ ] **INFRA-004** (1h) — Demo video #1: 60–90 s clip of med detection + fall check-in for portfolio.

**Proof:** tracking demo clip.

---

## Week 9 (Aug 10–16) — Accuracy Hardening & Stretch Goals
**Milestone M9: demo-grade reliability; one stretch goal landed.**

- [x] **VIS-011** (4h) — Detector robustness pass: test at demo-location lighting; retrain/threshold-tune until MED-DEMO criteria met.
- [ ] **VOX-005** (3h) — Voice robustness pass: 90%+ command success at 1–2 m in normal room noise; mis-recognition fallback ("Sorry, say again?").
- [ ] **STRETCH-001** (5h) — Pick **ONE**: schedule generator (CSV prescription list → reminder schedule) **OR** family dashboard auth view **OR** face-recognition greeting. Chosen feature demo-able.

> Stretch goals **only** in Week 9, **only one**, and **only if M7 is done**.

**Proof:** robustness test results.

---

## Week 10 (Aug 17–23) — Demo, Docs & Showcase Package
**Milestone M10: working prototype + complete portfolio package.**

- [ ] **DOC-001** (3h) — README overhaul: architecture diagram, setup guide, demo GIFs, results table (mAP, posture accuracy, FPS).
- [ ] **DOC-002** (3h) — Final demo video: 3–4 min, all 5 Definition-of-Done demos shown live, narrated.
- [ ] **DOC-003** (3h) — Project abstract + poster draft: 1-page abstract (problem, system, results, impact) for science fair / applications.
- [ ] **ENG-008** (2h) — Dress rehearsal: full scripted demo run twice without intervention; fallback recorded video ready.

**Proof:** video, README, abstract.

---

## Milestone summary

| Week | Milestone | Proof |
|------|-----------|-------|
| 1 | M1 Dataset v1 | Roboflow project link |
| 2 | M2 Detector ≥90% mAP@50 | Eval report in repo |
| 3 | M3 Compliance logging | Dashboard shows live "taken" event |
| 4 | M4 Voice commands ×4 | Screen recording |
| 5 | M5 Fall detection + Pi alive | Posture demo clip; Pi FPS benchmark |
| 6 | M6 Integrated system (laptop) | One-command launch, all events flowing |
| 7 | M7 Full stack on Pi, 2 h soak | systemd logs |
| 8 | M8 Servo head + OLED | Tracking demo clip |
| 9 | M9 Hardened + 1 stretch goal | Robustness test results |
| 10 | M10 Showcase package | Video, README, abstract |

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Pi 5 too slow for YOLO + pose together | Medium | Frame skipping, 640×480, YOLOv8n only; fallback: detect on med-station ROI only |
| Pi shipping delay | Medium | Weeks 1–4 & 6 are laptop-only; Pi truly needed from Week 7 |
| Vosk accuracy poor | Medium | Swap to whisper-tiny (offline) — STT abstracted behind one module |
| Dataset overfits to home lighting | High | Hard-negative round (VIS-007) + Week 9 hardening at demo location |
| Scope creep (stretch goals) | High | Stretch only in Week 9, only one, only if M7 done |
| Servo/I2C wiring eats time | Medium | Personality features isolated to Week 8; demos fine without them |

## Weekly operating rhythm

- **Start of week (30 min):** review milestone, pick tickets, move to "In Progress."
- **Each session:** commit to a feature branch; close tickets with the AC checklist.
- **End of week (30 min):** record a 30-second progress clip (portfolio montage), write a 3-line log in `docs/journal.md`.
