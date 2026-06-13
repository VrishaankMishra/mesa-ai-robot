# Datasets (placeholder)

The image dataset of medication bottles lives here but is **not committed** (it's large and
gitignored). This README is the placeholder describing the expected structure.

## Capture (VIS-002)
Raw photos go under `datasets/raw/<bottle>/`, named by the capture helper:
```
datasets/raw/tylenol/tylenol__bright__a0__d05__0007.jpg
```
See `docs/capture-protocol.md` for the coverage matrix (3 lighting × 3 angles × 3 distances).

## Annotate + export (VIS-003)
Annotate in Roboflow, then export in **YOLOv8** format. The export produces:
```
datasets/
├── data.yaml            # class names + train/val/test paths (consumed by training)
├── train/{images,labels}
├── valid/{images,labels}
└── test/{images,labels}
```
A template `data.yaml` is provided as `data.yaml.template` — Roboflow's export will
overwrite it with the real paths.

## Classes
Keep class ids in sync everywhere (this README, `data.yaml`, `docs/capture-protocol.md`):

| id | label |
|----|-------|
| 0 | tylenol |
| 1 | vitamin_d |
| 2 | multivitamin |
| 3 | ibuprofen |
| 4 | aspirin |
| 5 | calcium |
