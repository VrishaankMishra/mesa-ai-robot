# Domain-Shift Evaluation — 2-Day Session Plan (paper data)

Goal: measure detection performance across the full lighting × illumination grid at the
fixed (taped) camera geometry, for 3 model arms (v1, v2, v3+synthetic). Eight ~9-minute
voice-guided sessions. **No labeling — scripted placement is the ground truth.**

## One-time prep (before session 1)

- [ ] Camera untouched since Aug 7 (taped position). If it was bumped: ask Claude for a
      framing check BEFORE the first session — geometry drift poisons the whole grid.
- [ ] Table empty; 16/24/32-inch marks visible (24 + 32 are the ones the harness uses).
- [ ] The 8 bottles staged on the floor pile, in the usual order:
      mylanta, vitamin_d3, bayer_aspirin, cvs_allergy, omeprazole, melatonin,
      ashwagandha, advil.
- [ ] Benadryl box within reach but OFF the table (it's the unknown probe each session).
- [ ] LED lamp available for the `*_lamp*` sessions (see lamp notes below).

## Running one session

1. Set the room lighting for the condition (table below) and DON'T change it mid-session.
2. SSH is not needed — ask Claude to launch, or run on the Pi:

   ```bash
   .venv/bin/python scripts/eval_capture.py \
       --condition <CONDITION> \
       --bottles mylanta,vitamin_d3,bayer_aspirin,cvs_allergy,omeprazole,melatonin,ashwagandha,advil \
       --unknown benadryl
   ```

3. Follow MeSA's voice: each bottle at the near (24") then far (32") mark, slow rotation
   during bursts; then the Benadryl probe; then all bottles spread ≥ a hand-width apart.
4. She says "Session done" (~9 min). Change lighting, next condition.

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
lamp-off pairs at the same time of day are the **active-illumination ablation** — the
paper's money comparison.

## LED lamp placement (sessions 4, 6, 8)

- Lamp is the *product* arm: it should ILLUMINATE the bottles, not dramatize them —
  place it **beside/behind the camera, aimed at the marks from ~45° above**, lighting
  label faces. This is the opposite of the July "mixed" setup where it backlit the
  bottles on purpose.
- Same lamp position and brightness in all three lamp sessions. If it has color modes,
  pick one (prefer neutral/cool) and never change it.
- Sanity check: bottle labels should look evenly lit with soft shadows falling AWAY
  from the camera.

## After each day

Tell Claude the day's sessions are done. Claude then:
1. rsyncs `eval_data/` from the Pi to the iMac,
2. runs `scripts/eval_analyze.py` with all model arms (v1 backup, v2, v3 when trained),
3. reports the emerging degradation table.

After day 2 + the v3 (synthetic-augmentation) Colab run, the full results table and
figures go into `docs/eval/` and the paper draft.
