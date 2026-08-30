# Plan to the Sept 13 demo — and the STS lane beside it

One hour a day, Aug 30 → Sept 13. School starts **Sept 2**, so days after that are
evening hours; the plan front-loads anything that can be done before then.

**Fixed dates:** URTC edit window closes **Sept 4** · student demos **Sept 13** and
**Sept 20** · Regeneron STS ~mid-Nov `[verify exact date at regeneron.com/sts]` ·
college ED/EA **Nov 1**.

**Status as of Aug 30:** URTC poster **submitted** (CMT still allows Edit/Delete until
Sept 4; the uploaded PDF was verified pixel-identical to the repo render). Branches:
`poster/urtc-compliance` (includes `paper/number-audit`), `vision/demo-hardening`, and
stale `main`.

## The arithmetic, honestly

15 days × 1 hour ≈ 15 hours. The demo-critical list is ~14 of them. That fits with no
slack, which is why the parked section exists. Do not pull parked work forward without
dropping something else.

## Do these first — minutes each, and they unblock hours

1. **Pick the `tv` volume step** (a show + a volume number) and write it into
   `docs/voice-grid-sessions.md`. Until it exists, **6 of 12 voice-grid cells cannot
   start.** This is the cheapest unblock in the project and has been open since Aug 24.
2. **Set `research.enabled: false` in `config.yaml`** until the pose question below is
   settled. It is currently `true`, so every medication pickup writes another clip whose
   pose stream is unusable — the dataset is filling with noise.
3. **Start the STS recommender search.** Suchow has not replied since Aug 12.
   Recommenders need weeks, not days; this is the longest pole on the STS lane.

## One root cause behind two problems

The 40–45° top-down camera geometry that **MED** requires is the same geometry that
starves MediaPipe. It explains both:

- **FALL** — 37 of 41 clip frames had no skeleton; three spurious `possible_fall` → L1
  check-ins have already fired.
- **Research extension #1** — clips carry almost no pose (clip 1: 4 real frames of 32;
  clip 2: **0 of 32**), and both `clip_to_stgcn` and the wrist→bottle baseline read it.

Treat it as one design decision, not two bugs. Options for the research side: reframe the
predictor to object trajectories only, change the geometry, or gate recording on pose
presence. Decide before re-enabling the recorder.

## Days — the demo lane

| Date | Hour | Done when |
|---|---|---|
| **Aug 30** (Sun) | Reconcile branches; close the poster-script leak | `poster/urtc-compliance` merged to `main` |
| **Aug 31** (Mon) | Merge `vision/demo-hardening`; resolve EXCLUDE_PATHS overlap. Do the three quick unblocks above | one clean `main`, tests green |
| **Sept 1** (Tue) | Fix the Aug-24/Aug-27 date error; decide DB rows + clip filenames | provenance recorded or rewritten |
| **Sept 2** (Wed) | *School starts.* Counselor (STS transcript/school report) + SRC human-participants forms | forms submitted |
| **Sept 3** (Thu) | **FALL first.** VIS-010 torso gate live on the Pi | staged lying poses classify; no spurious L1 |
| **Sept 4** (Fri) | URTC edit window closes — final check the CMT abstract says `1,584` / `41–77%`. Then camera values at the station (VIS-011) | `camera.enabled: true`, measured |
| **Sept 5** (Sat) | MED + LOG: schedule import (ENG-002), real `taken` event | dashboard shows the event |
| **Sept 6** (Sun) | ntfy ESCALATE live, L1→L2→L3 — **demo 5 of 5** | phone receives L3 |
| **Sept 7** (Mon) | TUMS / Benadryl wrong-med live check | unknown bottle refused |
| **Sept 8** (Tue) | **VOX-005** voice robustness at the station — 90%+ at 1–2 m, "say again?" fallback | four commands answer reliably |
| **Sept 9** (Wed) | Full feature-by-feature test pass, FALL first | every demo green in one sitting |
| **Sept 10** (Thu) | Dress rehearsal 1 + B-roll | runbook followed start to finish |
| **Sept 11** (Fri) | Fix whatever rehearsal 1 broke | re-run the broken act |
| **Sept 12** (Sat) | Dress rehearsal 2, full dry run | two clean runs back to back |
| **Sept 13** (Sun) | **Demo** | — |

## The STS lane — runs parallel, not after

**STS needs no new research.** The domain-shift paper is 8 pages and ~90% of a ≤20-page
report; it needs student-voice framing and expanded methods, not more data. The voice grid
and the intent predictor strengthen ISEF and interviews — they are **not** on the STS path.

Fit these into the same hour on days the demo lane is light, and take the whole hour after
Sept 13:

- [ ] **Recommender search** — one educator + one who knows the research. Widen beyond
      Suchow now; do not wait on a single silent professor.
- [ ] **Counselor**, week one — transcript + school report.
- [ ] **Verify the exact STS deadline** and open the online application shell.
- [ ] **Fill or cut the two `[anchor ref]` citation slots** in `domain-shift-paper.md`.
      They are stripped from the PDF, but the gap is real and blocks any submission.
- [ ] **Reformat paper → 20-page report**, student voice, expanded methods (Sept–Oct).
- [ ] **Essays** — mine the engineering notebook; they overlap college essays heavily.
- [ ] **AI disclosure** stated plainly in the who-did-what section. The commit history and
      notebook show every decision, test and dataset was Vrishaank's — provenance is a
      strength here.

Front-load Sept–Oct: college ED/EA lands Nov 1, in the same window.

## Voice work — two tracks, do not confuse them

**Demo track (needed for Sept 13):** VOX-005 only — 90%+ command success at 1–2 m with a
mis-recognition fallback. Scheduled Sept 8. Not blocked by anything.

**Research track (paper #2, not needed for Sept 13 or STS):** the 12-cell grid
(3 distances × 2 noise × 2 speakers; 18 with a third speaker), ~2 hours total.

- Harness is **ready** — the three pilot defects were closed in `fea29d0`: 0.8 s guard gap,
  per-trial `trial_NN.wav`, and required `--posture`/`--position`.
- Tape marks at 1/2/3 m are in place.
- **Blocked on:** the `tv` volume step (6 cells) and SRC approval (Mom's cells).
- **All cells must be re-run standing** at real 1/2/3 m. The Aug-24 pilot was three repeats
  of one seated position at ~36 in; that audio was deleted.
- Already banked and still valid: the **17-point test-retest noise floor** on exact rate
  (7 on wake). Any cell-to-cell difference smaller than that is not an effect.

## Parked until after Sept 13

- Voice-reliability grid (above).
- Research extension #1 — blocked on the pose-channel decision.
- Public repo republish. Only two README prose lines are stale; the CSV and figures a
  reviewer would tally against are already correct and already public.
- Entrepreneurship comps (Conrad / Diamond) — only if bandwidth allows after STS.

## Standing rules

- **FALL goes first in any test pass.** The torso gate narrows real fall behavior; if
  staged lying poses come back UNKNOWN, the fix is a separate lower torso threshold,
  **not** a revert.
- Notes and outreach live in `private/`. The PDF scaffolding stripper is the safety net,
  not the plan.
- Never run `publish_public_copy.sh` from a `main` lacking the three script exclusions.
- End every work day with an engineering-notebook entry.
