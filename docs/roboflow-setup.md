# Roboflow Annotation & Export (VIS-003)

Manual step — needs your Roboflow account. This documents the exact settings so the
dataset is reproducible and matches what the training notebook (VIS-004) expects.

## 1. Create the project
- Type: **Object Detection**.
- Classes: the 6 bottle labels from `docs/capture-protocol.md` (keep ids in the same order).

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
