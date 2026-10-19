Hand-written caveats, copied verbatim into `site_stats.md` by `eval_stats.py` so they
survive regeneration. Numbers are in the tables; this file says which of them to trust.

**`home_office`** (Aug 8–9, 2026): the paper's grid. Per-session luminance was recomputed
after the fact from whole frames (`source=retro_frame00`); camera gain/exposure were not
recorded then.

**`family_room`** (Oct 19, 2026): grey folding table, patterned rug behind the far mark,
window to the camera's left; LED lamp base taped at the table's near-left. Camera on auto
throughout (gain/exposure in `scene_luminance.csv`). Conditions and their standing:

- `midday_lamps_off` — clean at the far mark. The near mark sits at the bottom edge of the
  frame in this geometry, so near-mark cells vary with centimetres of placement; compare
  sites on the far mark (`mark_m = 0.8`) or pooled, not near alone.
- `midday_lamp_added` — not a clean lamp ablation: the lamp base was off the table in this
  session and on it in the previous one, and the near-mark edge effect dominates the delta.
- `evening_dim` — clean. This room's dim is the camera at gain 255 / exposure 665 holding
  the image up (median grey 135); site A's dim was below the camera's range (median 39).
- `evening_dim_lamp` — **confounded, do not quote**: the far-mark bottle was placed at the
  table's far edge, ~30% smaller in frame than in `evening_dim`, and the lamp head's aim was
  not recorded. The cell scored 10% (deployed arm); a redo with the bottle on the tape and
  the lamp aimed across at the label faces is planned.
- `midday_lamps_off_pilot_steep_manualexp` — pilot, excluded from the grid: camera tilted
  steeper than the reference *and* left in manual exposure (312) by a prior `site_check`
  run (median grey 215 vs 123 for the room). Kept because it shows the geometry failure
  mode: four medications absorbed into `advil` at 0.6–0.7 confidence.
- Not captured, by decision: `morning_lamps_off/on` (no direct beam reaches this table),
  `evening_lights_on`, `evening_lamp_added`.
