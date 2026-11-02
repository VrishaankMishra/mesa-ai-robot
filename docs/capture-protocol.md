# Dataset Capture Protocol (VIS-001)

The repeatable photo protocol behind the MeSA medication dataset, as it was actually run
(Jul 18 and Aug 7, 2026), with the two lessons that decide whether a capture is usable.
The *evaluation* protocol — scripted placements with ground truth by construction — is a
different document: `docs/domain-shift-sessions.md`.

## Classes

Eight real medication containers plus a `tray` class for the group scene:

| Class id | Label         | Container                               |
|----------|---------------|-----------------------------------------|
| 0        | mylanta       | box (blue/red)                          |
| 1        | vitamin_d3    | dark amber bottle, black cap            |
| 2        | bayer_aspirin | small white bottle, orange label        |
| 3        | cvs_allergy   | small white bottle, green cap           |
| 4        | omeprazole    | small bottle, purple cap                |
| 5        | melatonin     | green bottle                            |
| 6        | ashwagandha   | amber bottle, green label               |
| 7        | advil         | white bottle, red label                 |
| 8        | tray          | the multi-bottle group scene            |

**Held-out "wrong medication" probe:** the Benadryl box is deliberately never captured or
trained, so it exercises the unknown-bottle path. In the live demo the prop is an untrained
*bottle* (TUMS): boxes are absorbed into the `mylanta` class (the open-set finding).

The class list must match `data.yaml` (`names:`) used for training; the DB medication
names must equal the detector labels exactly (presence matching is by string).

## The rig

- **Logitech C920** taped above the medication station, looking down ~40–45°.
- Bottle marks taped at **24" and 32"** from the lens.
- Table empty apart from the one announced container (and the lamp base, which is in
  every frame).
- The rig is photographed (`docs/media/`) so it can be reproduced after any move.

Geometry is load-bearing: a view that is steeper, side-on or across the room collapses
detection independent of lighting (the family-room pilot session shows four medications
absorbed into `advil` from too high a view).

## What was captured

| Round | Date | Condition | Source images | Notes |
|-------|------|-----------|---------------|-------|
| v1 | Jul 18 | evening: bright / dim / mixed (lamp behind the bottle) | 924 | voice-guided, hands-free |
| v2 daylight | Aug 7 | morning daylight, deployed geometry | 308 | after the lighting gap showed up live |
| discarded | Jul 18 | two passes with parked bottles in frame | 616 | unlabelled instances poison training |

All 1,232 kept images were hand-labelled in Roboflow (`docs/roboflow-setup.md`); split
70/20/10. Per-arm training records: `docs/training/`.

## Voice-guided capture (the method that worked)

On the headless Pi, `scripts/capture_guided.py` runs a whole session hands-free: the
speaker announces each container, mark and position, waits, then shoots a burst while the
operator slowly rotates the container. One run covers one lighting condition:

```bash
.venv/bin/python -u scripts/capture_guided.py \
    --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
    --lighting bright --position-wait 8
```

The laptop helper (`scripts/capture.py --bottle <label> --lighting <bright|dim|mixed>
--angle <deg> --distance <m>`) does the same with a display and SPACE to shoot; it writes
`datasets/raw/<bottle>/<bottle>__<lighting>__a<angle>__d<dist>__NNNN.jpg`.

## Two rules learned the hard way

1. **The table is EMPTY except the one announced container.** Parked bottles anywhere in
   frame are unlabelled instances that poison training. Spares live on the floor. Hands
   rotating the container during bursts are fine (realistic occlusion); the tray stage is
   the only multi-bottle scene — and because every other image is single-bottle, a crowd
   of bottles *is* the `tray` class to the model (the three-bottle cap in the runbook).
2. **Filenames are not ground truth.** A few cells were shot with the wrong container on
   the mark (voice-prompt mix-ups: "bayer" announced, mylanta placed). The Roboflow
   annotations are the ground truth; the condition-encoded filenames are only *mostly*
   right. Never audit, split or script against the filename's prefix — go through the
   annotations.
