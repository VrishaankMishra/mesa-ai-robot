# Training metadata

Factual provenance for the three trained detectors. The inventory table and the
deployment rule live in [`../README.md`](../README.md); this file records *how each arm
was trained* and *how to verify the exact binary*. Weights are not committed (global
`*.pt` ignore) — verify by hash and keep the binaries in the archive noted below.

The authoritative record is each checkpoint's own embedded `train_args`, captured in
[`checkpoint-provenance.md`](checkpoint-provenance.md) (verified 2026-10-28). Where this
file and prose elsewhere disagree, the checkpoint wins.

## Training configuration

From `notebooks/train_yolov8.ipynb`, Google Colab (T4 GPU), base `yolov8n.pt`,
ultralytics `8.2.103`, imgsz 640, batch 16. **Epochs differ by arm** (checkpoint-verified):

| Model | Roboflow version | Epochs | In-notebook transform |
|---|---|---|---|
| `best_v1_backup.pt` | **1** (evening round, 924 source) | 100 | none |
| `best.pt` (deployed) | **4** (both rounds) | 60 | none |
| `best_v3syn.pt` | **4** base | 60 | synthetic lighting ×3 on train (`synlight` cell) |

> "v2" elsewhere in the repo labels the *both-capture-rounds* dataset round; the Roboflow
> *version number* that actually trained `best.pt` / `best_v3syn.pt` is **4** (per the
> checkpoints). **Recover that export with `version(4)`, not `version(2)`** — confirm the
> mapping in the Roboflow UI.

Only the **v1** export survives locally; its 92-image test split is the 0.953 held-out
number for `best_v1_backup.pt` (`docs/eval/eval-report-v1.md`). The **version-4** export
behind the deployed champion and the synthetic arm is **not on disk** — Roboflow cloud only
(`vrishaank-mishra / medication-safety-object-detecti`). To re-score `best.pt` /
`best_v3syn.pt` on a held-out split, re-pull version 4 (`scripts/recover_roboflow_export.py`).

## Per-epoch training logs

`results.csv` / `results.png` from each Colab run are **not on local disk** (recycled Colab
VM). If an arm is re-run, download `mesa/yolov8n_med*/` into `docs/training/<arm>/`.

## Checksums

`checksums.sha256` holds SHA-256 for the three weights; all three verified `OK` on 2026-10-28.
Verify from the `models/` directory:

```bash
cd models && shasum -c training-metadata/checksums.sha256
```

## Binary archive

The three `.pt` (18 MB) and the v1 export (60 MB) are **not in git** (no git-lfs; large).
Durable copy location: **[ARCHIVE LOCATION — fill in, e.g. iCloud `MeSA/model-archive/` or an
external drive]**. As of 2026-10-28 they exist only in the iMac working tree — back them up.
