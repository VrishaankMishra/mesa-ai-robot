# Plan to the Sept 13 demo

One hour a day, Aug 30 → Sept 13. School starts **Sept 2**, so days after that are
evening hours; the plan front-loads anything that can be done before then.

**Fixed dates:** URTC edit window closes **Sept 4** · student demos **Sept 13** and
**Sept 20** · Regeneron STS ~mid-Nov.

**Status as of Aug 30:** URTC poster **submitted** (CMT still allows Edit/Delete until
Sept 4). Three branches outstanding: `poster/urtc-compliance` (this one, includes
`paper/number-audit`), `vision/demo-hardening`, and stale `main`.

## The arithmetic, honestly

15 days × 1 hour ≈ 15 hours. The demo-critical list below is ~14 of them. That fits with
no slack, which is why the "parked" section exists. Do not pull parked items forward
without dropping something else.

## Days

| Date | Hour | Done when |
|---|---|---|
| **Aug 30** (Sun) | Reconcile branches; close the poster-script leak | `poster/urtc-compliance` merged to `main` |
| **Aug 31** (Mon) | Merge `vision/demo-hardening`; resolve the EXCLUDE_PATHS overlap | one clean `main`, tests green |
| **Sept 1** (Tue) | Fix the Aug-24/Aug-27 date error; decide DB rows + clip filenames | provenance recorded or rewritten |
| **Sept 2** (Wed) | *School starts.* Counselor + SRC human-participants forms | forms submitted (unblocks Mom's voice cells) |
| **Sept 3** (Thu) | **FALL first.** VIS-010 torso gate live on the Pi | staged lying poses classify; no spurious L1 |
| **Sept 4** (Fri) | URTC edit window closes — final check of the CMT abstract. Then camera values at the station (VIS-011) | `camera.enabled: true` with measured values |
| **Sept 5** (Sat) | MED + LOG pass: schedule import (ENG-002), real `taken` event | dashboard shows the event |
| **Sept 6** (Sun) | ntfy ESCALATE live, L1→L2→L3 — **demo 5 of 5** | phone receives L3 |
| **Sept 7** (Mon) | TUMS / Benadryl wrong-med live check | unknown bottle refused |
| **Sept 8** (Tue) | VOICE pass at the station; the four commands end to end | all four answer |
| **Sept 9** (Wed) | Full feature-by-feature test pass, FALL first | every demo green in one sitting |
| **Sept 10** (Thu) | Dress rehearsal 1 + B-roll | runbook followed start to finish |
| **Sept 11** (Fri) | Fix whatever rehearsal 1 broke | re-run the broken act |
| **Sept 12** (Sat) | Dress rehearsal 2, full dry run | two clean runs back to back |
| **Sept 13** (Sun) | **Demo** | — |

## Parked until after Sept 13

- Voice-reliability grid redo (standing, 1/2/3 m). Mom's cells blocked on SRC anyway.
- Research fork: intent clips are missing the pose channel that ST-GCN needs. Every
  pickup logged before this is settled banks another object-only clip.
- Public repo republish. Only two README prose lines are stale; the CSV and figures a
  reviewer would tally against are already correct and already public.
- Regeneron STS packaging (~mid-Nov; the 20-page report is largely the paper reformatted).
- Suchow. No reply since Aug 12. URTC needed no mentor; arXiv does. Widen the outreach
  shortlist rather than wait.

## Standing rules

- **FALL goes first in any test pass.** The torso gate narrows real fall behavior; if
  staged lying poses come back UNKNOWN, the fix is a separate lower torso threshold,
  **not** a revert.
- Notes and outreach live in `private/`. The PDF scaffolding stripper is the safety net,
  not the plan.
- End every work day with an engineering-notebook entry.
