# June 22 — Next Actions

Plan for tomorrow, written at the end of the June 21 session (research extension + capture
layer + hardware wiring + cross-platform setup, all merged via PR #4).

## Where we stand (the 3 facts that shape tomorrow)
- **No trained model yet** — `models/` is just a README, no `best.pt` → live *detection* can't run.
- **No live vision worker** — vision code is standalone; nothing publishes events to the bus,
  so `main.py` only runs `--demo` (synthetic). The robot doesn't run live yet.
- **Pose needs no model** — MediaPipe is pretrained → the posture/fall half *can* run live now.

The keystone is the missing middle piece: a **live vision worker** (camera → pose/detect →
event bus → engine). It turns `--demo` into a real running robot **and** is where the research
capture tap (DATA-001/RES-001) has to live. Build it once, serve both.

## Recommended order
1. **Live vision worker — pose first** (no model needed). Camera → MediaPipe pose → publish
   `POSTURE` events → engine. FALL now runs live on the M3 camera. *(~half a day; biggest unlock.)*
2. **Wire capture into that worker** (design-doc §10 steps 3–4): tap the raw 33-landmark pose
   behind `research.enabled`; on a `taken` event dump the ring-buffer clip. The instrument we
   built finally gets fed real frames.
3. **Quick M3 smoke test** (parallel, ~15 min): `bash scripts/setup_env.sh`, grant camera
   permission, run `python scripts/pose_live.py --echo` to see the skeleton track you. First
   real on-laptop confirmation.

## Parallel dependency to start early
MED / LOG demos and research **Task B** (which-bottle) both need a **trained detector**, i.e.
the dataset pipeline: capture ~600 bottle images (VIS-002) → Roboflow (VIS-003) → train
YOLOv8n on Colab (VIS-004) → `best.pt`. Long pole for the detection half — kick off image
capture early even while building the vision worker.

## TL;DR
**Start with the live pose worker** (immediate, no blockers, unlocks live FALL + feeds the
capture). **Begin bottle-image capture in parallel** to unblock detection + Task B.

## Reminders
- Python **3.11/3.12, never 3.13** (mediapipe wheel). `bash scripts/setup_env.sh` enforces it.
- macOS: grant camera/mic permission on first use; `brew install portaudio` if audio backend missing.
- New branch for tomorrow's work; PR into `main` (don't commit to `main`).
