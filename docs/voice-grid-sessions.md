# Voice-Reliability Grid — session protocol (RES-004, paper #2)

The audio sibling of the domain-shift study: same free-ground-truth trick, applied to
the speech stack. Robot speaks each prompt; the operator repeats it after the "go" cue;
expected utterance + intent are known by construction. 18 scripted trials ≈ 4 minutes
per cell.

## The grid (12 cells minimum, 18 with a third speaker)

distance {1m, 2m, 3m} × noise {quiet, tv} × speaker {vrishaank, mom, (+1 optional)}

- Mark 1m / 2m / 3m from the SP300U speakerphone with tape (one-time).
- `tv` cells: the same audio source at the same volume every time (pick a show, note
  the volume step in this doc after the first session; it becomes part of the method).
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
