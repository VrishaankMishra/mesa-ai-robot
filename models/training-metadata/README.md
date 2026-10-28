# Training metadata

Factual provenance for the three trained detectors. The inventory table and the
deployment rule live in [`../README.md`](../README.md); this file records *how each arm
was trained* and *how to verify the exact binary*. Weights are not committed (global
`*.pt` ignore) — verify by hash and keep the binaries in the archive noted below.

## Training configuration (all three arms)

From `notebooks/train_yolov8.ipynb`, Google Colab (T4 GPU):

| Setting | Value |
|---|---|
| Base weights | `yolov8n.pt` (Ultralytics) |
| Ultralytics | `8.2.103` |
| epochs | 100 (early stop `patience=20`) |
| imgsz | 640 |
| batch | 16 |
| run name | `mesa/yolov8n_med` |
| M2 gate | validation mAP@50 ≥ 0.90 |

## Which Roboflow export trained which model

| Model | Roboflow version | In-notebook transform | Export on local disk? |
|---|---|---|---|
| `best_v1_backup.pt` | **v1** (evening round, 924 source) | none | **yes** — [`../../datasets/manifests/roboflow-v1.md`](../../datasets/manifests/roboflow-v1.md) |
| `best.pt` (deployed) | **v2** (both rounds) | none | no — Roboflow cloud only |
| `best_v3syn.pt` | **v2** base | synthetic lighting ×3 on train (`synlight` cell) | no — Roboflow cloud only |

Only the **v1** export survives locally; its 92-image test split is the 0.953 held-out
number for `best_v1_backup.pt` (`docs/eval/eval-report-v1.md`). The **v2** export that
produced the deployed champion and the synthetic arm is **not on disk** — it lives in the
Roboflow project (`vrishaank-mishra / medication-safety-object-detecti`, version 2). To
re-score `best.pt` / `best_v3syn.pt` on a held-out split, re-pull v2 from Roboflow.

## Per-epoch training logs

`results.csv` / `results.png` from each Colab run are **not on local disk** (they stayed in
the recycled Colab VM). If an arm is re-run, download `mesa/yolov8n_med*/` and drop it under
`docs/training/<arm>/`. _(Open: back-fill the existing runs' logs if the VMs are recoverable.)_

## Checksums

`checksums.sha256` holds SHA-256 for the three weights. Verify from the `models/` directory:

```bash
cd models && shasum -c training-metadata/checksums.sha256
```

## Binary archive

The three `.pt` (18 MB total) and the v1 export (60 MB) are **not in git** (no git-lfs; large).
Durable copy location: **[ARCHIVE LOCATION — fill in, e.g. iCloud `MeSA/model-archive/` or an
external drive]**. As of 2026-10-27 they exist only in the iMac working tree — back them up.
