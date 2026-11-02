# Voice-Reliability Grid — protocol and results (RES-004)

The audio sibling of the domain-shift study: the same ground-truth-by-construction trick,
applied to the speech stack. The robot speaks each prompt; the operator repeats it after
the "go" cue; the expected utterance and intent are known by construction. 18 scripted
trials ≈ 4 minutes per cell.

## What the grid found, and where it stopped

Four real cells were measured (three quiet cells at taped distances and one in demo
posture). They were enough to settle the question the grid existed for: **the wake word
was the bottleneck, not distance.** Wake-word recognition sat near 70 % and failed by
homophone substitution ("MeSA" heard as `may so`, `made so`, `mr`, `minister`); intent
parsing given a detected wake was 80–91 %. The live build therefore replaced the wake word
with **push-to-talk** (`voice.push_to_talk` in `config.yaml`) and a constrained grammar,
which removed the failure mode the grid measured. The remaining cells (noise conditions, a
second speaker) were not run: they would have measured a listening path the robot no
longer uses. The protocol stays here because it transfers unchanged to any future voice
change.

## The grid as designed

distance {1 m, 2 m, 3 m} × noise {quiet, tv} × speaker {operator, +1 optional}

- Marks at 1 m / 2 m / 3 m from the speakerphone, taped.
- **The microphone is pinned by name, not by index.** The capture script resolves the
  speakerphone by name substring and refuses to run unless it finds exactly one match; the
  device it used is printed at session start and written into every manifest row. This is
  method, not plumbing: sounddevice's default input resolves through ALSA to whatever the
  system picks, the Pi has a second microphone in the webcam, and card numbers move across
  reboots. An unpinned default would silently make "3 m from the speakerphone" mean "3 m
  from the webcam". Override with `--device` only when deliberately changing microphones.
- `tv` cells need one audio source at one fixed volume, written into this file before the
  first session so it becomes part of the method. None was chosen; no `tv` cell was run.
- One command per cell, from the Pi:

```bash
.venv/bin/python scripts/eval_voice_capture.py --condition d1m_quiet_operator \
    --posture standing --position "1m mark"
```

`--posture` and `--position` are **required**: the condition string is a filename, not
evidence, and where the operator actually was is recorded per trial, from the room. Each
trial's audio is saved beside the manifest (`trial_NN.wav`) so a disputed trial can be
settled by ear.

Naming: `d{1m|2m|3m}_{quiet|tv}_{speaker}`. Normal voice; do not lean in or shout — the
study measures the system, not the operator's effort.

## What each trial logs

Transcript (Vosk), wake-word detection, parsed intent, and exact correctness against the
scripted ground truth — including no-wake controls (must NOT trigger), a near-homophone
control ("may sun…"), and the negation guard ("I don't need help" must parse OKAY, not HELP).

Scoring: `scripts/eval_voice_analyze.py` → per-cell wake rate, false-wake rate, intent
accuracy given wake, exact rate → `docs/eval/voice_grid_results.csv`. The analyzer groups
by the manifest's `condition` column, not the directory name, so pilot rows (suffix
`_pilot`) can never merge into the grid.

## Results

### Pilot — 2026-08-27 (one condition, three repeats; not grid data)

Three sessions first labelled `d1m`/`d2m`/`d3m` were in fact three repeats of one seated
position (~0.91 m). The distance claim drawn from them was withdrawn; the sessions were
relabelled `d36in_seated_quiet_operator_pilot_run1/2/3` and kept as a test-retest measurement.

| run (same condition) | wake | false-wake | intent given wake | exact |
|----------------------|------|-----------|-------------------|-------|
| run 1 | 73 % | 67 % | 91 % | 61 % |
| run 2 | 73 % | 0 %  | 100 % | 78 % |
| run 3 | 80 % | 0 %  | 92 % | 78 % |

**Test-retest spread on an unchanged condition: 17 points of exact rate and 7 points of
wake rate.** That is the noise floor; any cell-to-cell difference smaller than it is not an
effect. The 67 % false-wake in run 1 did not reproduce (operator reflex on the no-wake
controls, first session only).

Three protocol defects found here and fixed before the grid: the robot recorded the tail
of its own prompt (a guard gap now drains playback before the cue); the near-homophone
control was passing on silence (a control that cannot fail is worse than none); nothing
recorded what the operator actually said (per-trial audio is now saved).

### Quiet cells — 2026-09-05 (standing at the taped marks)

| cell | wake | false-wake | intent given wake | exact |
|------|------|-----------|-------------------|-------|
| `d1m_quiet` | 73 % | 0 % | 82 % | 67 % |
| `d2m_quiet` | 67 % | 0 % | 80 % | 61 % |
| `d3m_quiet` | 73 % | 0 % | 91 % | 72 % |

**Distance does not measurably affect performance between 1 m and 3 m in a quiet room.**
Wake rate spans 6 points against the 7-point floor; exact rate spans 11 against 17. False
wake was 0 % in all 54 trials, including the near-homophone control, which now genuinely
exercises the wake word.

Two harness defects were found and fixed in this session: the guard gap sat between the
cue and the recording rather than between the prompt and the cue, so the operator spoke
into a closed microphone (3/18 wake before the fix); and the manifest header had drifted
four columns short of the row, so provenance fields were written but unlabelled — the
writer is now schema-driven.

### Demo-posture cell — 2026-09-07 (standing at the station, ~1.5 m)

| | wake | false-wake | intent given wake | exact |
|---|---|---|---|---|
| `station_demo_posture` | **80 %** (12/15) | 0/3 | **67 %** (8/12) | 61 % |

Accepting measured mishearings of the wake word as wake tokens lifted wake rate from ~71 %
to 80 % in live speech; a single cell of 15 trials against a 7-point floor, so the mechanism
is proven and the size of the gain is not. The failures moved downstream to transcription
quality (`mesa one of the next`, `our days it today`), every one returning UNKNOWN and the
graceful "Sorry, I didn't catch that" line. Per command: "call for help", "help me", "I'm
okay" and "I don't need help" all landed; "next medication" and "what day is it" each
failed twice.

## What the live build does now

- Push-to-talk (`voice.push_to_talk.enabled: true`, keyboard by default; GPIO once a button
  is wired). The press is the wake signal; nothing outside the 6 s window reaches the parser.
- A constrained Vosk grammar (`voice.constrain_vocabulary: true`) of ~50 phrases, with
  spoken aliases for medication names the small lexicon lacks (`voice.med_aliases`;
  `scripts/check_vocabulary.py` finds any others).
- The check-in after "Are you okay?" opens its own 30 s window with no press, and an
  unrecognised reply inside it only extends the window. The acknowledgement is "I am okay"
  (the grammar carries no contractions).
- Live-verified on 2026-10-24: two scripted commands answered on the first press; the
  check-in cleared by voice in 8 s.

No measured number exists yet for push-to-talk in a noisy room. If one is wanted, this
protocol produces it: the same capture script with the trigger pressed on the cue.
