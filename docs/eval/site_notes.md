Hand-written caveats, copied verbatim into `site_stats.md` by `eval_stats.py` so they
survive regeneration. Numbers are in the tables; this file says which of them to trust.

**`home_office`** (Aug 8–9, 2026): the paper's grid. Per-session luminance was recomputed
after the fact from whole frames (`source=retro_frame00`); camera gain/exposure were not
recorded then. `evening_dim` there was captured at 21:11 with only computer screens lit.

**`family_room`** (Oct 19 and 22, 2026): grey folding table, patterned rug behind the far
mark, window to the camera's left; LED lamp base taped at the table's near-left. Camera on
auto throughout (gain/exposure in `scene_luminance.csv`). Conditions and their standing:

- `midday_lamps_off` (Oct 19, 14:12) — clean at the far mark. The near mark sits at the
  bottom edge of the frame in this geometry, so near-mark cells vary with centimetres of
  placement; compare sites on the far mark (`mark_m = 0.8`) or pooled, not near alone.
- `midday_lamp_added` (Oct 19, 14:24) — not a clean lamp ablation: the lamp base was off
  the table in this session and on it in the previous one, and the near-mark edge effect
  dominates the delta.
- `afternoon_blinds_dim` (Oct 19, 14:58) — an extra condition this site has and site A
  does not: mid-afternoon, blinds closed, ceiling lights off. The camera was at gain 255 /
  exposure 665 holding the image up (median grey 135), so it is dim by the instrument but
  it is not an evening cell. It was captured and first reported under the label
  `evening_dim`; renamed Oct 22.
- `afternoon_blinds_dim_lamp` (Oct 19, 15:08) — **confounded, do not quote**: the far-mark
  bottle was placed at the table's far edge, ~30% smaller in frame than in the paired cell,
  and the lamp head's aim was not recorded. 10% under the deployed arm.
- `evening_dim` / `evening_dim_lamp` (Oct 23, 20:52 and 21:01, after dark) — the true
  evening pair, comparable to site A's. Room lit only by the **kitchen lights spilling in
  from the adjacent room** (this room's ceiling lights off); with everything off the
  camera read median grey 3, i.e. nothing, so that was not used. `evening_dim` reads
  median 18 at gain 255 / exposure 665 — darker than site A's 39; the lamp cell reads 69
  at the same gain and exposure with 0% blown, the lamp head aimed across at the label
  faces from beside the camera, not down at the table. Bottles on the tape marks; the
  32" tape sits at this table's far edge. Camera remounted that evening with the table's
  far edge at 30% of the frame — steeper than the Oct 19 cells (44%) — so the
  evening-vs-midday comparison within this site carries a small geometry difference;
  the lamp pair itself shares one position.
- `midday_lamps_off_pilot_steep_manualexp` — pilot, excluded from the grid: camera tilted
  steeper than the reference *and* left in manual exposure (312) by a prior `site_check`
  run (median grey 215 vs 123 for the room). Kept because it shows the geometry failure
  mode: four medications absorbed into `advil` at 0.6–0.7 confidence.
- Not captured, by decision: `morning_lamps_off/on` (no direct beam reaches this table),
  `evening_lights_on`, `evening_lamp_added`.
