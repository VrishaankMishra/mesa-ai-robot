# Training record — v1 (`best_v1_backup.pt`)

- **Dataset:** Roboflow v1 (evening round, 924 source → 2,218 after ×3 train aug).
  Manifest: [`datasets/manifests/roboflow-v1.md`](../../../datasets/manifests/roboflow-v1.md).
  Export survives locally.
- **Notebook:** `notebooks/train_yolov8.ipynb`, Roboflow `version(1)`, no in-notebook transforms.
- **Config (checkpoint-verified):** yolov8n · 100 epochs · imgsz 640 · batch 16 (ultralytics 8.2.103);
  trained 2026-08-06, Roboflow data path `Medication-Safety-Object-Detecti-1` (version 1).
  See `models/training-metadata/checkpoint-provenance.md`.
- **Result:** 0.95 validation; **0.953 held-out test** (92 images, Aug 6) — `docs/eval/eval-report-v1.md`.
- **Weights SHA-256:** `67f758…f689010` (see `models/training-metadata/checksums.sha256`).
- **Status:** study baseline arm. Was the deployed `best.pt` on Aug 6, before the Aug 7 daylight retrain.
- **Open — per-epoch logs:** `results.csv` / `results.png` not on disk; re-export from Colab if re-run.
