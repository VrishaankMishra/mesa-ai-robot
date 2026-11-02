# MeSA 2.0 — Ticket Board

> **STATUS (November 2026):** working prototype. All five core demos (MED, LOG, FALL,
> VOICE, ESCALATE) ran live on the Pi in one continuous run on 2026-10-24
> (`docs/eval/events_archive_2026-10-24.csv`). The research extension — a two-site
> domain-shift study with statistics — is complete (`docs/eval/`). Open: systemd
> auto-start (HW-003), on-Pi servo/OLED verification (HW-004–006), the tray-class
> retraining experiment (VIS-007), and open-vocabulary STT on the Pi (VOX-008).

Derived from the 10-week project plan. Tickets follow `AREA-###` with labels `vision`
`voice` `engine` `hw` `infra` `docs` `research`. A ticket closes only when its
acceptance criteria (AC) are met, with the evidence named. Work lands via feature branch
and PR.

- **Plan:** 10 weeks from Jun 15, 2026 (~12 h/week), laptop first, Pi from Week 7.
- **Evidence convention:** each closed ticket names the file, figure or notebook entry that
  proves it. "Live-verified" means it ran on the Pi with real camera, mic and speaker.

---

## Phase 0 — Repo foundation ✅

- [x] Project layout (`mesa/{vision,audio,engine,data,hardware,research,dashboard}`, `tests/`,
      `docs/`, `config.yaml`, `main.py`, `requirements.txt`, `requirements-pi.txt`).
- [x] `scripts/setup_env.sh` creates the venv on Python 3.11/3.12 (not 3.13 — the pinned
      mediapipe has no wheel) and verifies imports.
- [x] `pytest` green from day one; 363 tests at the time of writing.
- [x] `config.yaml` holds every threshold (INFRA-003).

## Week 1 — Dataset & dev environment ✅ (M1)

- [x] **INFRA-001** Dev environment on laptop.
- [x] **INFRA-002** Issue board: tickets tracked in this file.
- [x] **VIS-001** Capture rig + protocol → `docs/capture-protocol.md`.
- [x] **VIS-002** Image capture: 924 (Jul 18, voice-guided) + 308 (Aug 7, daylight) source
      images across 8 medications → `datasets/README.md`.
- [x] **VIS-003** Roboflow annotation, all 1,232 images hand-labelled, 70/20/10 split →
      `docs/roboflow-setup.md`.

## Week 2 — Train & evaluate detector ✅ (M2)

- [x] **VIS-004** YOLOv8n on Colab; held-out **test mAP@50 0.953** (v1, Aug 6) →
      `docs/eval/eval-report-v1.md`; per-arm records in `docs/training/`.
- [x] **VIS-005** Evaluation report with confusion matrix and per-class P/R → `docs/eval/`.
- [x] **VIS-006** Live inference with the unknown-bottle path → `scripts/detect_live.py`,
      `mesa/vision/detector.py`.
- [ ] **VIS-007** Hard-negative / tray-class round — **open, deliberately deferred.** The
      `tray` class, learned from a handful of clutter shots, outcompetes individual bottles
      once four or more appear together (measured 2026-09-07: 1 bottle 0.75 · 2: 0.73/0.72 ·
      3: 0.73/0.69/0.61 · 4: 0.74/0.67/0.65/**0.44 fails**; 8 clustered → `tray 0.61`, zero
      medications). Group scenes scored 0/12 in every lighting condition of the study.
      **Prediction on record:** remove or rebalance `tray`, retrain, re-run the bottle-count
      ladder; without the tray prior, four or more bottles detect where they now collapse.
      Not run yet because every measured number in `docs/eval/` describes the current
      weights; a new model re-opens all of it.

## Week 3 — Compliance tracking & database ✅ (M3)

- [x] **ENG-001** SQLite schema + DAO (`events`, `medications`, `schedule`; plus `sessions`,
      `clips` for the research layer) → `mesa/data/database.py`.
- [x] **ENG-002** Per-bottle presence state machine, 3 s debounce → `mesa/engine/presence.py`.
- [x] **ENG-003** `taken` rule: absent ≥ 10 s then returned → `mesa/engine/compliance.py`.
      Live-verified Aug 7 (first real `taken`), Oct 24 (`taken advil` 17:16:22, absent 21 s).
- [x] **DASH-001** Streamlit dashboard: today's doses, event table → `mesa/dashboard/app.py`.

## Week 4 — Voice assistant ✅ (M4)

- [x] **VOX-001** Mic capture + Vosk STT loop → `mesa/audio/stt.py`, `worker.py`.
- [x] **VOX-002** Intent parser (`NEXT_MED`, `DID_I_TAKE`, `HELP`, `DATE_TIME`, `OKAY`),
      unit-tested → `mesa/audio/intents.py`.
- [x] **VOX-003** Intent → DB → spoken answer (pyttsx3) → `mesa/audio/assistant.py`.
- [x] **VOX-004** HELP → ntfy push → `mesa/alerts/ntfy.py`.
- [x] **VOX-005** Voice robustness. Measured wake-word rate was ~70 % in a quiet room
      (`docs/voice-grid-sessions.md`), failing by homophone substitution, so the wake word was
      replaced by **push-to-talk** (VOX-006, Sept 18) and a constrained Vosk grammar
      (VOX-007). Live-verified Oct 24: both scripted commands answered on the first press.
- [x] **VOX-006** Push-to-talk trigger (keyboard / GPIO / event) → `config.yaml`
      `voice.push_to_talk`. The check-in after "Are you okay?" opens its own 30 s window
      with no press.
- [x] **VOX-007** Vocabulary constraint + spoken aliases for names outside the Vosk lexicon
      (`scripts/check_vocabulary.py`, `voice.med_aliases`).
- [ ] **VOX-008** Open-vocabulary STT (faster-whisper, `voice.stt_engine: whisper-tiny`) —
      coded and tested on the laptop; **not yet tried on the Pi**. Keep Vosk until it is.

## Week 5 — Fall detection + Pi bring-up ✅ (M5)

- [x] **VIS-008** MediaPipe Pose live → `scripts/pose_live.py`.
- [x] **VIS-009** Posture classifier (torso angle, shoulder/hip height, inverted-torso rule,
      static fallback chain for lying) → `mesa/vision/posture.py`, `pose_estimator.py`.
- [x] **VIS-010** Lying > 30 s → `possible_fall` → spoken check-in; torso-visibility gate.
      Live-verified Sept 5 (208/208 frames `lying` on staged poses), Oct 24.
- [x] **HW-001** Pi 5 set up, camera, repo deployed, FPS benchmarked (`scripts/benchmark.py`).

## Week 6 — Decision engine integration ✅ (M6)

- [x] **ENG-004** Event bus + orchestrator: `main.py --demo` (synthetic) and `--live`.
- [x] **ENG-005** Escalation L1 → L2 (60 s) → L3 (120 s), simulated-time tests →
      `mesa/engine/escalation.py`. Live-verified with both pushes on a phone: Sept 5, Sept 21,
      Oct 24 (`possible_fall` 17:19:13 → L2 17:20:13 → L3 17:21:14).
- [x] **ENG-006** Inactivity monitor (1 h window) → `mesa/engine/inactivity.py`.
- [x] **INFRA-003** All thresholds in `config.yaml`.

## Week 7 — Full system on the Pi (M7, partial)

- [x] **HW-002** Full stack on the Pi: 640×480, detection every 3rd frame, pose every frame;
      `requirements-pi.txt`. Live since Aug 7.
- [ ] **HW-003** systemd auto-start — **open.** `deploy/mesa.service` + `install_pi.sh` exist,
      but the unit launches `main.py` without `--live`, and keyboard push-to-talk needs a
      TTY, which systemd does not provide. Needs a GPIO button (`push_to_talk.source: gpio`)
      or a dashboard "Talk" button driving the event trigger first. Until then MeSA is
      started by hand over SSH (`docs/test-plan.md` §0).
- [x] **ENG-007** Soak: decision engine ran 3.02 M synthetic events over a simulated week,
      peak memory 19.1 KiB (`docs/eval/soak_results.md`). An on-robot multi-hour home soak
      has not been run.
- [x] **DASH-002** Dashboard on the LAN at `:8501`, reached from a phone (Sept 6 over a
      hotspot, Oct 24 at home).

## Week 8 — Robotic personality (M8, stretch — not verified on hardware)

- [ ] **HW-004** PCA9685 + pan-tilt assembly — driver coded (`mesa/hardware/servos.py`),
      hardware not assembled.
- [ ] **HW-005** Person-tracking head — control law coded and unit-tested
      (`mesa/hardware/tracking.py`); not run on a servo.
- [ ] **HW-006** OLED emotion display — coded (`mesa/hardware/oled.py`, `emotions.py`); not
      run on a display. Null drivers keep everything runnable without hardware.
- [x] **INFRA-004** Demo video: setup tour (Aug 9, `docs/media/`) and the Oct 24 live run.

## Week 9 — Accuracy hardening ✅ (M9)

- [x] **VIS-011** Robustness at deployment lighting: threshold 0.50 → 0.45 (Aug 7), daylight
      retrain (v2), camera-control locking in `config.yaml` (`vision.camera`), the
      eight-condition study. **Measured, not fixed:** detection spans the lighting envelope
      (see `docs/eval/`); the mitigation that works is the LED lamp and a fixed geometry.
- [x] **STRETCH-001** Schedule generator from a CSV prescription list →
      `scripts/import_schedule.py`, `mesa/engine/schedule_gen.py`.

## Week 10 — Demo, docs & showcase ✅ (M10)

- [x] **DOC-001** README with architecture figure, results, setup.
- [x] **DOC-002** Final demo: full five-act run recorded 2026-10-24.
- [x] **DOC-003** Abstract and poster (from the study).
- [x] **ENG-008** Dress rehearsals: Sept 7 (home), Sept 21 (home), Oct 24 run 1 (rehearsal)
      then run 2 (clean).

## Research extension (added Jun 21) — measured, capture paused

- [x] **DATA-001 / RES-001** Pre-event feature capture: ring buffer, `.npz` clips, `sessions`
      and `clips` tables → `mesa/research/`, `docs/research-dataset-design.md`.
- [x] **RES-004 (vision)** The domain-shift study: self-administered evaluation
      (`scripts/eval_capture.py`), scoring (`eval_analyze.py`), statistics (`eval_stats.py`),
      figures (`eval_figures.py`, `eval_site_figures.py`); two sites.
- [x] **RES-004 (voice)** Voice-reliability grid: four cells → `docs/voice-grid-sessions.md`.
- [ ] **RES-002 / RES-003** Hands channel, intent baselines — **paused.** The top-down
      geometry MED needs starves MediaPipe, so clips carry almost no skeleton;
      `research.enabled` is `false` since Sept 5 (`config.yaml`).

---

## Milestone summary

| Week | Milestone | Evidence |
|------|-----------|----------|
| 1 | M1 Dataset v1 | `datasets/README.md`, Roboflow project |
| 2 | M2 Detector ≥ 0.90 mAP@50 | `docs/eval/eval-report-v1.md` (0.953) |
| 3 | M3 Compliance logging | live `taken` events, Aug 7 and Oct 24 |
| 4 | M4 Voice commands | live Oct 24 (push-to-talk) |
| 5 | M5 Fall detection + Pi alive | staged-pose runs Sept 5, Oct 24 |
| 6 | M6 Integrated system | `main.py --live` |
| 7 | M7 Full stack on Pi | live since Aug 7; systemd still open |
| 8 | M8 Servo head + OLED | coded; not verified on hardware |
| 9 | M9 Hardened | `docs/eval/` |
| 10 | M10 Showcase package | README, Oct 24 recording |

## Risks — how they played out

| Risk | What happened |
|------|---------------|
| Pi 5 too slow for YOLO + pose | Fine at 640×480 with detection every 3rd frame. |
| Vosk accuracy poor | True for the wake word (~70 %); solved by push-to-talk + grammar, not by swapping engines. Whisper remains an option (VOX-008). |
| Dataset overfits to home lighting | The central research finding: measured across 8 conditions and 2 rooms; mitigated by a lamp and fixed geometry rather than by data. |
| Servo/I2C wiring eats time | Deferred entirely; the demos never needed it. |
| One camera, two geometries | Found late: the top-down MED view cannot see the floor, so FALL needs the camera re-aimed at the fall zone, and the research clips carry no skeleton. A product needs a second camera or a wider field of view. |

## Weekly operating rhythm

- Commit to a feature branch; close tickets with the AC and the evidence.
- End every working day with an entry in the engineering notebook.
- After any change to a headline number, re-check every place it is quoted.
