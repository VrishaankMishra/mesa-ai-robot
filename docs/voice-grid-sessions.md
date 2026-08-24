# Voice-Reliability Grid — session protocol (RES-004, paper #2)

The audio sibling of the domain-shift study: same free-ground-truth trick, applied to
the speech stack. Robot speaks each prompt; the operator repeats it after the "go" cue;
expected utterance + intent are known by construction. 18 scripted trials ≈ 4 minutes
per cell.

## The grid (12 cells minimum, 18 with a third speaker)

distance {1m, 2m, 3m} × noise {quiet, tv} × speaker {vrishaank, mom, (+1 optional)}

- Mark 1m / 2m / 3m from the SP300U speakerphone with tape (one-time). **Done 2026-08-24.**
- **The microphone is pinned by name, not by index.** The capture script resolves the
  SP300U by name substring and refuses to run if it cannot find exactly one match; the
  device it used is printed at session start and written into every manifest row. This is
  method, not plumbing: sounddevice's default input resolves through ALSA `default` to
  whatever pulse picks, the Pi has a second mic in the C920, and card numbers move across
  reboots (the SP300U was card 3 in July and card 2 on 2026-08-24). An unpinned default
  would make "3m from the speakerphone" silently mean "3m from the webcam". Override with
  `--device` only when deliberately changing microphones — and say so in the paper.
- `tv` cells: the same audio source at the same volume every time (pick a show, note
  the volume step in this doc after the first session; it becomes part of the method).
  **Still to choose — the `tv` cells cannot start until it is fixed and written here.**
- One command per cell, run from the Pi:

```bash
.venv/bin/python scripts/eval_voice_capture.py --condition d1m_quiet_vrishaank \
    --posture standing --position "1m mark"
```

`--posture` and `--position` are **required**: on 2026-08-24 three sessions were labelled
`d1m`/`d2m`/`d3m` and read as a distance sweep when all three had in fact been run from one
seated position. The condition string is a filename, not evidence — where the operator was
is now recorded per trial, from the room. Each trial's audio is also saved beside the
manifest (`trial_NN.wav`), so a disputed trial can be settled by ear instead of by argument.

Naming: `d{1m|2m|3m}_{quiet|tv}_{speaker}`. Speak at your normal voice; do NOT lean in
or shout — the study measures the system, not the operator's effort.

## What each trial logs
Transcript (Vosk), wake-word detection, parsed intent, and exact-correctness vs the
scripted ground truth — including no-wake controls (should NOT trigger), a
near-homophone control ("may sun…"), and the negation-guard trial ("I don't need help"
must parse OKAY, not HELP).

## After a batch
```bash
.venv/bin/python scripts/eval_voice_analyze.py
```
Per-cell: wake rate, false-wake rate, intent accuracy given wake, exact rate →
`docs/eval/voice_grid_results.csv`. ~2 hours total across a few days completes the grid.


## Pilot round — 2026-08-24 (NOT grid data — one condition, three repeats)

Three quiet sessions were run end-to-end as a **pilot**, to shake out the protocol rather than
to measure the system. Their condition labels carry a `_pilot` suffix *inside the manifests* as
well as in the directory names, so `eval_voice_analyze.py` — which groups by the `condition`
column, not the path — can never merge them into the real grid.

**Correction (recorded deliberately).** These were first labelled `d1m` / `d2m` / `d3m` and read
as a distance sweep. They were not: all three ran from **~36 inches (0.91 m), seated in a chair**.
They are three repeats of one condition, relabelled `d36in_seated_quiet_vrishaank_pilot_run1/2/3`.
The earlier reading — "distance is not the limiting factor between 1 m and 3 m" — was unsupported
and has been withdrawn. Flat numbers across three identical conditions are what identical
conditions look like.

| run (same condition) | wake | false-wake | intent given wake | exact |
|----------------------|------|-----------|-------------------|-------|
| run 1 | 73% | 67% | 91% | 61% |
| run 2 | 73% | 0%  | 100% | 78% |
| run 3 | 80% | 0%  | 92% | 78% |

**What this round does support** (pilot-grade, n=18 per run, one speaker, one position):
- **Test-retest spread on an unchanged condition: 17 points of exact rate (61→78%) and 7 points
  of wake rate.** That is the noise floor. Any cell-to-cell difference in the real grid smaller
  than this cannot be read as an effect, which is a number worth having before collecting 12 cells.
- Intent parsing given a detected wake is strong (91–100%). The failure is upstream of intent:
  "MeSA" was transcribed as `may so`, `reza so` and `minister`.
- The 67% false-wake in run 1 did not reproduce in runs 2 or 3 (both 0%), consistent with
  first-run warm-up on the no-wake controls — the reflex to say the wake word anyway.

**A variable the grid design does not currently control:** these runs were **seated**, while the
grid assumes standing at a taped mark. Mouth height and orientation relative to the SP300U differ
between the two. Posture needs to be fixed in the protocol and recorded per session, or it becomes
an uncontrolled variable riding along with distance.

**Three protocol defects to fix before any grid cell is run:**
1. **The robot records its own prompt.** `espeak-ng` returns when it has handed audio to the USB
   speakerphone, not when playback finishes, so the tail of *"Repeat: …"* is still audible when the
   capture window opens. Trial 17 transcribed as `repeat` in two runs and `may says wait what
   repeat` in the third. Fix: a guard gap after the beep so playback drains before recording starts.
2. **The near-homophone control passes for the wrong reason.** Trial 17 exists to prove "may sun"
   does not trip the wake word. In all three runs the microphone mostly heard the prompt, so
   `wake=False` was recorded and scored as a pass while nothing was actually tested. A control that
   passes on silence is worse than no control.
3. **Nothing records what the operator actually said** — only Vosk's transcript. That is why run 1's
   false-wake rate cannot be attributed: operator habit, ASR hallucination and prompt bleed are
   indistinguishable after the fact. Fix: save each trial's audio into the session directory (own
   voice, `eval_voice/` is gitignored, privacy stance unchanged).

**Also still open:** the `tv` volume step is unchosen, so no `tv` cell can start.
