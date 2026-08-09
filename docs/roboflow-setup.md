# Roboflow Annotation & Export (VIS-003)

Manual step — needs your Roboflow account. This documents the exact settings so the
dataset is reproducible and matches what the training notebook (VIS-004) expects.

## 1. Create the project
- Type: **Object Detection**.
- Classes: the 8 medication labels + `tray` from `docs/capture-protocol.md`.
- Actual project: workspace `vrishaank-mishra`, project `medication-safety-object-detecti`.

## 2. Upload
- Upload everything from `datasets/raw/`.
- Roboflow can pre-assign the train/val/test split — set it to **70 / 20 / 10**.

## 3. Annotate
- Draw a tight bounding box around each bottle; one box per visible bottle.
- For cluttered shots with multiple bottles, label **every** bottle in frame.
- Be consistent: include the cap, exclude the hand.

## 4. Augmentations (generate version)
Keep augmentations realistic for a tabletop camera — don't over-augment:
- Brightness ±15%, exposure ±10% (covers lighting variation).
- Rotation ±10°, slight blur, slight noise.
- **No** vertical flip (bottles have a fixed up/down orientation).

## 5. Export
- Format: **YOLOv8**.
- This produces a `data.yaml` with `names:` and train/val/test paths — the training
  notebook consumes this directly. Either download the zip into `datasets/` or use the
  Roboflow download snippet inside the Colab notebook.

## Acceptance criteria
- [ ] All images boxed + labeled.
- [ ] 70/20/10 train/val/test split configured.
- [ ] Augmentations configured; YOLOv8-format version exported.
- [ ] Roboflow project link recorded in the M1 milestone / README.

## Lessons from the real runs (Aug 2026)
- **Label Assist:** rejected in practice — the v1 model mislabeled everything in its own
  blind spots (that's exactly where new rounds live). All 1,232 images were hand-labeled.
- **Modify Classes is paywalled** on the free plan — class surgery (e.g. dropping `tray`)
  is done in-notebook instead (see the drop-tray cell in notebooks/train_yolov8.ipynb).
- Filenames are NOT ground truth (capture-swap artifacts) — annotations are.
