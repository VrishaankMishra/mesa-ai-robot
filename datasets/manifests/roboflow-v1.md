# Roboflow export — v1 (the export that survives locally)

The only Roboflow export kept on local disk. It trained `best_v1_backup.pt`, and its
92-image test split is that model's 0.953 held-out number (`docs/eval/eval-report-v1.md`).

## Identity

| Field | Value |
|---|---|
| Workspace / project | `vrishaank-mishra` / `medication-safety-object-detecti` |
| Version | 1 |
| URL | https://universe.roboflow.com/vrishaank-mishra/medication-safety-object-detecti/dataset/1 |
| License | CC BY 4.0 |
| Exported | 2026-08-06 |
| Format | YOLOv8 |
| Source captures | 924 images @1280×720, 2026-07-18 (evening round) |

## Preprocessing & augmentation (Roboflow-side)

- Auto-orient (EXIF stripped); resize 512×512 (stretch).
- ×3 versions per source image: brightness ±15%, exposure ±10%, Gaussian blur 0–1.1 px.
- Applied to the **train split only**; valid/test left pristine.

## Classes (nc = 9, alphabetical export order)

`advil` · `ashwagandha` · `bayer_aspirin` · `cvs_allergy` · `melatonin` · `mylanta` ·
`omeprazole` · `tray` · `vitamin_d3`

(Benadryl is deliberately untrained — the wrong-medication demo probe.)

## Splits

| Split | Images | Label files |
|---|---|---|
| train | 1,941 | 1,941 |
| valid | 185 | 185 |
| test | 92 | 92 |
| **total** | **2,218** | **2,218** |

## Fingerprint (detect drift without storing the images)

- `data.yaml` SHA-256: `9238bc993ab28b206d5994b911866df24ebc18adf69ea3eb35dea195086d8a62`
- Aggregate SHA-256 (all 4,440 files, sorted): `d8379012c505831f743bde1ba9c6c6d7a286a6db68516be159c27c3b5ca6f341`
- On-disk size: 60 MB

Recompute the aggregate:

```bash
cd "<export-dir>" && find . -type f ! -name '.DS_Store' -print0 \
  | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256
```

## Where it lives

- Extracted: iMac `~/Downloads/Medication Safety Object Detecti/` (not in git).
- Canonical source: the Roboflow project above (cloud; versioned).
- The **v2** export (both capture rounds) that trained `best.pt` / `best_v3syn.pt` is **not
  on disk** — Roboflow version 2 only. The original `.zip` downloads were not retained.
