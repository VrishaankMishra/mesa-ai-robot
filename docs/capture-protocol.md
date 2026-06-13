# Dataset Capture Protocol (VIS-001)

Fixed, repeatable photo protocol for the MeSA medication dataset. Following this gives a
dataset that generalizes instead of overfitting to one lighting setup (see risk:
"Dataset overfits to home lighting").

## Target

- **≥600 images** total across **6 bottles** (~100 each).
- Coverage matrix: **3 lighting × 3 angles × 3 distances**, plus cluttered backgrounds.
- Split later in Roboflow: **70 / 20 / 10** train / val / test.

## Bottles (classes)

Use 6 visually distinct, real bottles. Suggested set (edit to match what you have):

| Class id | Label        | Notes                          |
|----------|--------------|--------------------------------|
| 0        | tylenol      | red/white label                |
| 1        | vitamin_d    |                                |
| 2        | multivitamin |                                |
| 3        | ibuprofen    |                                |
| 4        | aspirin      |                                |
| 5        | calcium      |                                |

Keep this list in sync with `data.yaml` (`names:`) used for training.

## The capture rig

- Fixed camera position: **Logitech C920**, mounted at the medication-station height.
- Mark the bottle placement zone with tape so distances are repeatable.
- Record the setup with a photo so it can be reproduced at the demo location.

## Coverage matrix

**Lighting (3):**
1. Bright / daylight (window or room lights full).
2. Warm / dim (evening, lamp only).
3. Mixed / backlit (light source behind the bottle).

**Angle (3):** straight-on (0°), ~30° left, ~30° right (or slight high/low tilt).

**Distance (3):** 0.5 m, 1.0 m, 1.5 m (the MED-DEMO operating range).

**Backgrounds:** include cluttered scenes — other objects, a tray with multiple bottles,
hands partially occluding — not just a clean table. ~20% of shots should be "hard".

## Workflow

Use the helper script (VIS-002):

```bash
python scripts/capture.py --bottle tylenol --lighting bright --angle 0 --distance 0.5
```

It writes files to `datasets/raw/<bottle>/` with a structured name encoding the
conditions, e.g. `tylenol__bright__a0__d05__0007.jpg`. Press **SPACE** to capture,
**Q** to quit. Aim for ~12 shots per (lighting × angle × distance) cell.

## Acceptance criteria

- [ ] Fixed camera position documented (photo of rig committed to `docs/`).
- [ ] Lighting / angle / distance checklist written (this file).
- [ ] ≥600 images captured across the full matrix, including cluttered backgrounds.
