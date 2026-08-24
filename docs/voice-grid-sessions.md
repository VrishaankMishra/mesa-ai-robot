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
