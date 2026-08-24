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
.venv/bin/python scripts/eval_voice_capture.py --condition d1m_quiet_vrishaank
```

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


## Pilot round — 2026-08-24 (NOT grid data)

Three quiet cells were run end-to-end as a **pilot**, to shake out the protocol rather than
to measure the system. Their condition labels carry a `_pilot` suffix *inside the manifests*
as well as in the directory names, so `eval_voice_analyze.py` — which groups by the
`condition` column, not the path — can never merge them into the real grid.

| cell | wake | false-wake | intent given wake | exact |
|------|------|-----------|-------------------|-------|
| `d1m_quiet_vrishaank_pilot` | 73% | 67% | 91% | 61% |
| `d2m_quiet_vrishaank_pilot` | 73% | 0%  | 100% | 78% |
| `d3m_quiet_vrishaank_pilot` | 80% | 0%  | 92% | 78% |

**Provisional signals** (pilot-grade, n=18 per cell, one speaker, one room):
- Distance is not the limiting factor between 1 m and 3 m in a quiet room — wake rate is flat
  (73/73/80) and 3 m scored best. The wake word's acoustic fragility dominates: "MeSA" was
  transcribed as `may so`, `reza so` and `minister` across cells.
- Intent parsing given a detected wake is strong (91–100%). The failure is upstream of intent.

**Two protocol defects to fix before any grid cell is run:**
1. **The robot records its own prompt.** `espeak-ng` returns when it has handed audio to the
   USB speakerphone, not when playback finishes, so the tail of *"Repeat: …"* is still audible
   when the capture window opens. Trial 17 transcribed as `repeat` in two cells and
   `may says wait what repeat` in the third. Fix: a guard gap after the beep so playback
   drains before recording starts.
2. **The near-homophone control passes for the wrong reason.** Trial 17 exists to prove
   "may sun" does not trip the wake word. In all three cells the microphone mostly heard the
   prompt, so `wake=False` was recorded and scored as a pass while nothing was actually
   tested. A control that passes on silence is worse than no control.
3. **Nothing records what the operator actually said** — only Vosk's transcript. That is why
   the 1 m false-wake rate of 67% cannot be attributed: operator habit, ASR hallucination and
   prompt bleed are indistinguishable after the fact. The 2 m and 3 m cells both scoring 0%
   points to first-cell warm-up, but the harness cannot prove it. Fix: save each trial's audio
   into the session directory (own voice, `eval_voice/` is gitignored, privacy stance
   unchanged) so any disputed trial is re-checkable by ear.

**Also still open:** the `tv` volume step is unchosen, so no `tv` cell can start.
