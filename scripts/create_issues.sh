#!/usr/bin/env bash
# INFRA-002 — Create the GitHub Issues board: labels, milestones, and all tickets.
#
# Prereqs: `gh` CLI authenticated (`gh auth status`) with write access to the repo.
# Run from the repo root:   bash scripts/create_issues.sh
# Idempotency: labels/milestones are created with `|| true` so re-running is safe,
# but issues are NOT de-duplicated — only run the issue section once.

set -euo pipefail

echo "==> Creating labels"
create_label() { gh label create "$1" --color "$2" --description "$3" 2>/dev/null || true; }
create_label vision "1d76db" "Computer vision: detection & pose"
create_label voice  "5319e7" "Voice: STT/TTS, intents"
create_label engine "0e8a16" "Decision engine, state machines, DB"
create_label hw     "b60205" "Hardware / Raspberry Pi"
create_label infra  "fbca04" "Tooling, environment, config"
create_label docs   "c5def5" "Docs, demos, write-ups"
create_label research "d4c5f9" "Dataset capture + intent-prediction research (DATA-/RES-)"

echo "==> Creating milestones (M1..M10)"
create_milestone() { # $1 title  $2 due (YYYY-MM-DD)
  gh api "repos/{owner}/{repo}/milestones" -f title="$1" -f due_on="${2}T23:59:59Z" >/dev/null 2>&1 || true
}
create_milestone "M1 Dataset v1"                  2026-06-21
create_milestone "M2 Detector >=90% mAP@50"       2026-06-28
create_milestone "M3 Compliance logging"          2026-07-05
create_milestone "M4 Voice commands x4"           2026-07-12
create_milestone "M5 Fall detection + Pi alive"   2026-07-19
create_milestone "M6 Integrated system (laptop)"  2026-07-26
create_milestone "M7 Full stack on Pi"            2026-08-02
create_milestone "M8 Servo head + OLED"           2026-08-09
create_milestone "M9 Hardened + 1 stretch"        2026-08-16
create_milestone "M10 Showcase package"           2026-08-23
create_milestone "M11 Research v1 (post-project)"  2026-09-30

echo "==> Creating issues"
mk() { # $1 title  $2 labels  $3 milestone  $4 body
  gh issue create --title "$1" --label "$2" --milestone "$3" --body "$4"
}

# Week 1 — M1
mk "INFRA-001 Set up dev environment on laptop" infra "M1 Dataset v1" \
  "Repo cloned; venv with pinned requirements.txt; existing unit tests pass. (est 2h)"
mk "INFRA-002 Create GitHub Issues board with all tickets" infra "M1 Dataset v1" \
  "All tickets entered with labels + milestones. (est 1h)"
mk "VIS-001 Build capture rig + photo protocol" vision "M1 Dataset v1" \
  "Fixed camera position documented; lighting/angle/distance checklist written. See docs/capture-protocol.md. (est 2h)"
mk "VIS-002 Capture 100 images x 6 bottles" vision "M1 Dataset v1" \
  ">=600 images, 3 lighting conditions, 3 angles, 3 distances; includes cluttered backgrounds. (est 5h)"
mk "VIS-003 Annotate dataset in Roboflow" vision "M1 Dataset v1" \
  "All images boxed + labeled; 70/20/10 split; augmentations configured. See docs/roboflow-setup.md. (est 3h)"

# Week 2 — M2
mk "VIS-004 Train YOLOv8n on Colab" vision "M2 Detector >=90% mAP@50" \
  "Training notebook in repo; best.pt exported; >=90% mAP@50. See notebooks/train_yolov8.ipynb. (est 4h)"
mk "VIS-005 Evaluation report" vision "M2 Detector >=90% mAP@50" \
  "Confusion matrix + per-class precision/recall committed to /docs; failure cases listed. (est 2h)"
mk "VIS-006 Live inference script" vision "M2 Detector >=90% mAP@50" \
  "detect_live.py shows boxes + confidence at >=5 FPS on laptop; 'unknown bottle' path when confidence < threshold. (est 4h)"
mk "VIS-007 Hard-negative round" vision "M2 Detector >=90% mAP@50" \
  "50+ images of failure cases added; retrained if mAP < 90%. (est 2h)"

# Week 3 — M3
mk "ENG-001 SQLite schema + data access module" engine "M3 Compliance logging" \
  "events, medications, schedule tables; CRUD functions; pytest coverage. (est 3h)"
mk "ENG-002 Presence state machine per bottle" engine "M3 Compliance logging" \
  "States present->absent->returned; debounced (3s) so hand occlusion doesn't false-trigger. (est 4h)"
mk "ENG-003 Medication taken event rule" engine "M3 Compliance logging" \
  "Absent >=10s then returned => taken event with timestamp + med name in DB. (est 2h)"
mk "DASH-001 Extend Streamlit dashboard" engine "M3 Compliance logging" \
  "Today's meds, taken/missed status, event history table reading live from SQLite. (est 3h)"

# Week 4 — M4
mk "VOX-001 Mic capture + Vosk STT loop" voice "M4 Voice commands x4" \
  "Continuous transcription; wake word 'MeSA' gates commands. (est 4h)"
mk "VOX-002 Intent parser" voice "M4 Voice commands x4" \
  "Keyword/regex intents: NEXT_MED, DID_I_TAKE, HELP, DATE_TIME; unit-tested on 20 phrasings each. (est 3h)"
mk "VOX-003 Intent -> DB -> spoken answer" voice "M4 Voice commands x4" \
  "'Did I take Vitamin D?' answers correctly from real events table via pyttsx3. (est 3h)"
mk "VOX-004 HELP intent -> alert stub" voice "M4 Voice commands x4" \
  "'Call for help' sends ntfy.sh push notification. (est 2h)"

# Week 5 — M5
mk "VIS-008 MediaPipe Pose integration" vision "M5 Fall detection + Pi alive" \
  "33 keypoints rendered live at >=10 FPS (laptop). (est 2h)"
mk "VIS-009 Posture classifier" vision "M5 Fall detection + Pi alive" \
  "Torso angle + hip/shoulder height rules classify standing/sitting/lying >=90% on a 50-clip test set. (est 5h)"
mk "VIS-010 Lying-duration trigger" vision "M5 Fall detection + Pi alive" \
  "Lying >30s fires possible_fall event; spoken 'Are you okay?' check-in. (est 2h)"
mk "HW-001 Pi 5 setup" hw "M5 Fall detection + Pi alive" \
  "Pi OS 64-bit, SSH, camera working, repo deployed, YOLO+pose FPS benchmarked. (est 3h)"

# Week 6 — M6
mk "ENG-004 Event bus + main orchestrator" engine "M6 Integrated system (laptop)" \
  "main.py launches vision, audio, engine threads; all events flow through one queue. (est 5h)"
mk "ENG-005 Escalation state machine" engine "M6 Integrated system (laptop)" \
  "L1 check-in -> 60s no response -> L2 ntfy -> no response -> L3 caregiver alert; unit-tested with simulated time. (est 4h)"
mk "ENG-006 Inactivity monitor" engine "M6 Integrated system (laptop)" \
  "No person/motion for configurable window (default 1h) triggers escalation L1. (est 2h)"
mk "INFRA-003 Config file" infra "M6 Integrated system (laptop)" \
  "All thresholds (timeouts, confidence, schedule) in config.yaml. (est 1h)"

# Week 7 — M7
mk "HW-002 Port full stack to Pi" hw "M7 Full stack on Pi" \
  "All Week-6 functionality on Pi; requirements-pi.txt; perf tuning to keep pose >=5 FPS. (est 5h)"
mk "HW-003 systemd service" hw "M7 Full stack on Pi" \
  "MeSA auto-starts on boot; logs to file; survives reboot. (est 2h)"
mk "ENG-007 Soak test + bug bash" engine "M7 Full stack on Pi" \
  "2-hour continuous run; no crashes; memory stable; issues filed and fixed. (est 4h)"
mk "DASH-002 Dashboard reachable on LAN" engine "M7 Full stack on Pi" \
  "Phone/laptop on same Wi-Fi can view dashboard served from Pi. (est 1h)"

# Week 8 — M8
mk "HW-004 PCA9685 + pan-tilt assembly" hw "M8 Servo head + OLED" \
  "Camera mounted on pan-tilt; servos sweep via script. (est 3h)"
mk "HW-005 Face/person tracking head" hw "M8 Servo head + OLED" \
  "Head keeps detected person centered (proportional control); no jitter. (est 4h)"
mk "HW-006 OLED emotion display" hw "M8 Servo head + OLED" \
  "idle/alert/greeting states driven by engine events. (est 3h)"
mk "INFRA-004 Demo video #1" docs "M8 Servo head + OLED" \
  "60-90s clip of med detection + fall check-in recorded for portfolio. (est 1h)"

# Week 9 — M9
mk "VIS-011 Detector robustness pass" vision "M9 Hardened + 1 stretch" \
  "Test at demo-location lighting; retrain/threshold-tune until MED-DEMO criteria met. (est 4h)"
mk "VOX-005 Voice robustness pass" voice "M9 Hardened + 1 stretch" \
  "90%+ command success at 1-2m in normal room noise; mis-recognition fallback. (est 3h)"
mk "STRETCH-001 Pick ONE stretch feature" engine "M9 Hardened + 1 stretch" \
  "Schedule generator OR family dashboard auth view OR face-recognition greeting. Demo-able. (est 5h)"

# Week 10 — M10
mk "DOC-001 README overhaul" docs "M10 Showcase package" \
  "Architecture diagram, setup guide, demo GIFs, results table (mAP, posture accuracy, FPS). (est 3h)"
mk "DOC-002 Final demo video" docs "M10 Showcase package" \
  "3-4 min: all 5 Definition-of-Done demos shown live, narrated. (est 3h)"
mk "DOC-003 Project abstract + poster draft" docs "M10 Showcase package" \
  "1-page abstract (problem, system, results, impact) for science fair / applications. (est 3h)"
mk "ENG-008 Dress rehearsal" engine "M10 Showcase package" \
  "Full scripted demo run twice without intervention; fallback recorded video ready. (est 2h)"

# --- Research extension (DATA-/RES-) — see docs/research-dataset-design.md and
#     MeSA-2_0-Research-Extension-Plan.pdf. Milestones follow Extension-Plan §6. ---

# Rides on Weeks 1-2 capture work (design features-not-video in from the start)
mk "DATA-001 Pose/landmark feature logging" research "M1 Dataset v1" \
  "Per-frame pose (33 x x,y,z,visibility) + detection features (bbox/class/conf) serialized to a documented schema; raw 33-landmark MediaPipe output tapped before posture classification; no raw video persisted by default; behind research.enabled flag. See docs/research-dataset-design.md §3.1. (est 3h)"

# Rides on Week 3 compliance & DB work
mk "RES-001 Rolling pre-event buffer" research "M3 Compliance logging" \
  "Ring buffer of last N s of features (buffer 6s; sweep 1-5s offline); on ENG-003 taken event, dump the pre-event window as one labeled .npz clip with metadata + anchor_event_id. (est 3h)"
mk "DATA-002 Consent + session metadata schema" research "M3 Compliance logging" \
  "sessions table: session id, pseudonymous participant id, consent flag/version, tier, conditions; every clip linked to a session; Tier>=2 requires consent_flag=1. (est 2h)"
mk "DATA-003 Label-review view (Streamlit)" research "M3 Compliance logging" \
  "Reviewer can scrub clips, see auto-label, confirm/relabel/discard (clips.review_status lifecycle); bolts onto the existing DASH-001 dashboard. (est 3h)"

# Rides on Week 5 MediaPipe Pose work
mk "RES-002 MediaPipe Hands integration (optional)" research "M5 Fall detection + Pi alive" \
  "Hand landmarks (21/hand) added to the feature stream alongside Pose; toggled via research.capture_hands in config.yaml; FPS impact recorded; gated so it can't jeopardize the fall-detection demo. (est 3h)"

# Stretch goal (Week 9) — replaces a generic STRETCH option
mk "RES-003 Baseline predictors" research "M9 Hardened + 1 stretch" \
  "Rule-based (wrist->nearest-bottle) + ST-GCN trained on collected clips; training notebook in repo; Task A (engagement) + Task B (object) metrics reported. See docs/research-dataset-design.md §5. (est 5h)"
mk "RES-004 Evaluation + lead-time analysis" research "M9 Hardened + 1 stretch" \
  "Lead-time curves (accuracy vs seconds-before-contact, swept over N), confusion matrix, failure cases committed to /docs; reproducible from a script; positioned against CAD-120 1/3/10s numbers. (est 3h)"

# Packaging (Week 10)
mk "DATA-004 Dataset packaging + datasheet" research "M10 Showcase package" \
  "Versioned features-only release, README + 'datasheet for datasets' doc (seeded by docs/research-dataset-design.md), license, train/val/test split assigned by session. (est 3h)"

# Post-project research milestone
mk "RES-005 Ethics/IRB scoping for Tier 2-3 collection" research "M11 Research v1 (post-project)" \
  "Determine ethics route (school/competition IRB vs lightweight consent); consent forms drafted; start inquiry early (~Week 3-4 lead time). Tier-1 self-data needs none but carries no authenticity claim. (est 3h)"
mk "RES-006 Tier-2 multi-participant collection" research "M11 Research v1 (post-project)" \
  "Run a consented, multi-participant session; clips accumulate automatically through the capture instrument; satisfies DATA-DONE in the Research Definition of Done. (est 5h)"

echo "==> Done. Issues board created."
