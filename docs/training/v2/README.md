# Training record — v2 (`best.pt`, deployed champion)

- **Dataset:** Roboflow v2 (both rounds: v1 evening 924 + v2 daylight 308 source). **Export
  not on local disk** — Roboflow version 2 (cloud) only.
- **Notebook:** `notebooks/train_yolov8.ipynb`, Roboflow `version(2)`, no in-notebook transforms.
- **Config:** yolov8n · 100 epochs · imgsz 640 · batch 16 · patience 20 (ultralytics 8.2.103).
- **Result:** 0.95–0.98 validation band (Colab). **No held-out test run on record.** Chosen as
  champion on deployed-condition results (`docs/eval/domain_shift_results.csv`), not on validation.
- **Weights SHA-256:** `41f67c…92e0560`.
- **Status:** deployed — powers `main.py --live`.
- **Open:** re-scoring on a test split needs the v2 export re-pulled from Roboflow; per-epoch logs re-exported from Colab.
