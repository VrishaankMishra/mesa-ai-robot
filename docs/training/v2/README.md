# Training record — v2 (`best.pt`, deployed champion)

- **Dataset:** Roboflow **version 4** (both capture rounds: v1 evening 924 + daylight 308
  source). Checkpoint data path: `Medication-Safety-Object-Detecti-4`. **Export not on local
  disk** — Roboflow cloud only. ("v2" is the both-rounds *label*; the Roboflow *version* is 4.)
- **Notebook:** `notebooks/train_yolov8.ipynb`, Roboflow `version(4)`, no in-notebook transforms.
- **Config (checkpoint-verified):** yolov8n · **60 epochs** · imgsz 640 · batch 16
  (ultralytics 8.2.103); trained 2026-08-08. See `models/training-metadata/checkpoint-provenance.md`.
- **Result:** 0.95–0.98 validation band (Colab). **No held-out test run on record** — chosen as
  champion on deployed-condition results (`docs/eval/domain_shift_results.csv`), not validation.
- **Weights SHA-256:** `41f67c…92e0560`.
- **Status:** deployed — powers `main.py --live`.
- **Open:** re-score on a held-out split by re-pulling **version 4** from Roboflow
  (`scripts/recover_roboflow_export.py`); per-epoch logs re-exported from Colab.
