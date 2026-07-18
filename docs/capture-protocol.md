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

| Class id | Label         | Notes                                   |
|----------|---------------|-----------------------------------------|
| 0        | mylanta       | box (blue/red)                          |
| 1        | vitamin_d3    | dark amber bottle, black cap            |
| 2        | bayer_aspirin | small white bottle, orange label        |
| 3        | cvs_allergy   | small white bottle, green cap           |
| 4        | omeprazole    | small bottle, purple cap                |
| 5        | melatonin     | Nature's Bounty, green bottle           |
| 6        | ashwagandha   | Himalaya, amber bottle, green label     |
| 7        | advil         | white bottle, red label                 |

**Held-out "wrong medication" prop:** the Benadryl box is deliberately NOT captured or
trained, so it triggers the unknown-bottle path in the MED demo.

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

**Distance (3):** tape marks at 0.6 m, 0.75 m, 0.9 m (24″ / mid / 36″ on the actual rig; add far-range shots in the Week-9 hardening pass if demo distance grows).

**Backgrounds:** include cluttered scenes — other objects, a tray with multiple bottles,
hands partially occluding — not just a clean table. ~20% of shots should be "hard".

## Workflow

On a laptop with a display, use the interactive helper (VIS-002):

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

## Voice-guided capture (Pi rig)

On the headless Pi rig, `scripts/capture_guided.py` runs the whole session hands-free:
the robot's speaker announces each bottle / mark / position, waits, then shoots a burst
while you slowly rotate the bottle. One run covers one lighting condition:

```bash
.venv/bin/python -u scripts/capture_guided.py \
    --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
    --lighting bright --position-wait 8
```

Protocol learned the hard way (Jul 18 session): the table must be EMPTY except the one
announced bottle — parked bottles anywhere in frame mean unlabeled instances that poison
training. Spares live on the floor. Hands rotating the bottle during bursts are fine
(realistic occlusion); the final tray stage is the only multi-bottle scene.
