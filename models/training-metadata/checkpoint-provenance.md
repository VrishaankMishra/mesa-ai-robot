# Checkpoint-embedded provenance (verified 2026-10-28)

Read directly from each weights file's `train_args` and metadata — the model's own record of
how it was trained, and the authoritative source above any prose. Loaded with
`.venv/bin/python` (torch 2.2.2 / ultralytics 8.2.103); all three load cleanly, 9 classes,
SHA-256 matches `checksums.sha256`.

| Weights | Trained | Roboflow data path (in checkpoint) | epochs | imgsz | batch | base |
|---|---|---|---|---|---|---|
| `best_v1_backup.pt` | 2026-08-06 | `Medication-Safety-Object-Detecti-1` → **version 1** | 100 | 640 | 16 | yolov8n.pt |
| `best.pt` (deployed) | 2026-08-08 | `Medication-Safety-Object-Detecti-4` → **version 4** | 60 | 640 | 16 | yolov8n.pt |
| `best_v3syn.pt` | 2026-08-09 | `Medication-Safety-Object-Detecti-4` → **version 4** (+ in-notebook synthetic lighting) | 60 | 640 | 16 | yolov8n.pt |

Classes (all three): `advil`, `ashwagandha`, `bayer_aspirin`, `cvs_allergy`, `melatonin`,
`mylanta`, `omeprazole`, `tray`, `vitamin_d3`.

## Two corrections this surfaced

1. **The deployed champion trained on Roboflow dataset _version 4_, not "v2".** "v2" in
   `../README.md` and `datasets/README.md` is the label for the *both-capture-rounds* dataset
   round; the Roboflow *version number* behind `best.pt` and `best_v3syn.pt` is **4** (folder
   suffix `-4`). **To recover that export, pull `version(4)`, not `version(2)`.** Confirm in
   the Roboflow UI which generation is which before relying on it.
2. **Actual epochs were 60 for `best.pt` / `best_v3syn.pt`** (not the notebook cell's default
   of 100); `best_v1_backup.pt` used 100. The run overrode the notebook default.

The local surviving export is **version 1** (trained `best_v1_backup.pt`). Version 4 is **not
on disk** — Roboflow cloud only. Recover it with `scripts/recover_roboflow_export.py`.
