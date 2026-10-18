# Domain-Shift Evaluation — Session Runbook (any room)

Goal: measure detection performance across the full lighting grid at a fixed (taped)
camera geometry, for every model arm, in every room the robot is evaluated in. Eight
~9-minute voice-guided sessions per room. **No labeling — scripted placement is the
ground truth.** Each room is a *site*; the same grid run in a new site is a replication
that compares cell-for-cell with every site before it.

## Sites so far

| Site label | Room | Grid captured | Notes |
|---|---|---|---|
| `home_office` | original station (the paper's room) | Aug 8–9, 2026 | predates `--site`; sits directly under `eval_data/` |
| *(next)* | a better-lit room in the house | — | same grid, same 8 medications |

Site labels are lowercase snake_case, chosen once and never renamed: the label is the
directory name, the manifest column, and the key every statistic is grouped by.

## One-time prep for a new site

- [ ] **Geometry first.** Recreate the camera mount as in the original station: C920 at
      the same height, ~40–45° downward view, physically taped. Geometry is load-bearing
      (off-geometry views collapse detection independent of lighting); a new room is a
      new lighting envelope, not a new viewpoint.
- [ ] Tape the 24" and 32" marks from the camera. Photograph the rig for `docs/`.
- [ ] Table empty. The 8 bottles staged on the floor pile, in the usual order:
      mylanta, vitamin_d3, bayer_aspirin, cvs_allergy, omeprazole, melatonin,
      ashwagandha, advil.
- [ ] Benadryl box within reach but OFF the table (it is the unknown probe each session).
- [ ] LED lamp available for the `*_lamp*` sessions; outline its position on the table
      with tape the first time so all three lamp sessions use the same spot.
- [ ] Pi has the current code (`git pull` in `~/mesa-ai-robot`) and the deployed weights
      are untouched — the point is the same model in a different room.
- [ ] Optional: `scripts/site_check.py --label "<room>"` once, for a first read of the
      room's brightness and whether the model sees anything at all there.

For the original site, "prep" was: camera untouched since Aug 7; if bumped, framing check
against an `eval_data/` frame before the first session.

## Running one session

1. Set the room lighting for the condition (table below) and DON'T change it mid-session.
2. On the Pi (or ask Claude to launch it):

   ```bash
   .venv/bin/python scripts/eval_capture.py \
       --site <ROOM> --condition <CONDITION> \
       --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
       --unknown benadryl
   ```

   The first thing MeSA says is the scene brightness (median grey of the empty table);
   it is written to `scene.json` in the session folder. For the original grid the same
   number, recomputed after the fact from whole frames, runs 11 (direct morning sun —
   a bright beam in a dark room) to 122 (midday); see `docs/eval/scene_luminance.csv`.
   A value far outside that is worth a note, not a reason to stop.
3. Follow MeSA's voice: each bottle at the near (24") then far (32") mark, slow rotation
   during bursts; then the Benadryl probe; then all bottles spread ≥ a hand-width apart.
4. She says "Session done" (~9 min). Change lighting, next condition.

Frames and the manifest land in `eval_data/<ROOM>/<CONDITION>/<timestamp>/`.

## The grid (8 sessions)

| # | Condition label | Room lights | Window | LED lamp |
|---|---|---|---|---|
| 1 | `morning_lamps_off` | off | daylight in | off |
| 2 | `morning_lamps_on` | on | daylight in | off |
| 3 | `midday_lamps_off` | off | daylight in | off |
| 4 | `midday_lamp_added` | off | daylight in | **on** |
| 5 | `evening_lights_on` | on | dark | off |
| 6 | `evening_lamp_added` | on | dark | **on** |
| 7 | `evening_dim` | one small lamp only | dark | off |
| 8 | `evening_dim_lamp` | one small lamp only | dark | **on** |

Day 1: sessions 1–4 (morning + midday). Day 2: sessions 5–8 (evening). Lamp-on vs
lamp-off pairs at the same time of day are the **active-illumination ablation**. Use the
same condition labels in every room so cells line up across sites; a room without a
window simply has no morning/midday-daylight sessions, and the statistics compare the
conditions that exist in both.

## LED lamp placement (sessions 4, 6, 8)

- Lamp is the *product* arm: it should ILLUMINATE the bottles, not dramatize them —
  place it **beside/behind the camera, aimed at the marks from ~45° above**, lighting
  label faces. (Not the July "mixed" setup, which backlit the bottles on purpose.)
- Same lamp position and brightness in all three lamp sessions. If it has color modes,
  pick one (prefer neutral/cool) and never change it.
- Sanity check: bottle labels should look evenly lit with soft shadows falling AWAY
  from the camera.

## After each day

Tell Claude the day's sessions are done. Then, on the iMac:

1. rsync `eval_data/` from the Pi (`rsync -av mesa-pi:mesa-ai-robot/eval_data/ eval_data/`);
2. score every site in one pass — the CSV carries a `site` column:

   ```bash
   .venv/bin/python scripts/eval_analyze.py \
       --models models/best.pt,models/best_v1_backup.pt,models/best_v3syn.pt \
       --out docs/eval/domain_shift_results.csv
   ```

3. per-session scene luminance → `docs/eval/scene_luminance.csv`
   (`scripts/eval_luminance.py`; runs wherever the frames are);
4. the statistics pass — Wilson intervals on every rate, the lighting trend, the paired
   lamp analysis, and a cell-for-cell replication table for every site beyond the
   reference (`scripts/eval_stats.py` → `docs/eval/site_stats.md`);
5. figures per site (`scripts/eval_figures.py --site <ROOM>` → `docs/eval/figures/<ROOM>/`).

The per-frame CSV, the luminance CSV and the stats report are committed; frames stay on
the Pi and the iMac (privacy scrub of home context before any release).
