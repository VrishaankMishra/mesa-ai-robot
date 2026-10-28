# Training record — v3syn (`best_v3syn.pt`, negative-result arm)

- **Dataset:** Roboflow v2 base + **in-notebook synthetic lighting ×3** on the train split
  (`synlight` cell: synwarm R×1.18 / G×1.02 / B×0.72, γ1.06; syncool R×0.82 / G×0.96 / B×1.20,
  γ0.96 — labels copied, geometry unchanged; valid/test pristine). v2 export not on local disk.
- **Notebook:** `notebooks/train_yolov8.ipynb`, Roboflow `version(2)` → run `synlight` cell → train.
  (The separate `droptray` ablation cell is independent; `models/README.md` attributes this arm
  to the synthetic-lighting transform only.)
- **Config:** yolov8n · 100 epochs · imgsz 640 · batch 16 · patience 20 (ultralytics 8.2.103).
- **Result:** 0.979 validation — yet loses every off-domain condition in deployment
  (`docs/eval/domain_shift_results.csv`). The pre-registered "synthetic beats more data"
  prediction that was wrong **at Site A**; the two-site data shows the effect is
  site-dependent (see `docs/paper/`).
- **Weights SHA-256:** `c41708…485fcad`.
- **Status:** **do NOT deploy** — research arm only.
- **Open:** per-epoch logs re-exported from Colab; test re-score needs the v2 export from Roboflow.
