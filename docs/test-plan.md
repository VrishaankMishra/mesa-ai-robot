# MeSA 2.0 — Manual Test Plan

Per-feature checks to run before a demo or after any change to the camera position, the
weights, or the voice stack. Automated tests (`pytest`, 360+) cover the pure logic; this
document covers what only a person with the hardware can verify. Each section maps to a
Definition-of-Done demo. Record pass/fail and notes per run; the Oct 24, 2026 run is the
reference (`docs/eval/events_archive_2026-10-24.csv`).

> ⚠️ Test fall detection with staged poses on cushions only. MeSA is an assistive aid, not
> a medical device.

---

## 0. Clean start (every live run)

Bottles on their marks, nobody in frame, then start `main.py --live`. Wait 30 s and confirm
**zero events**. Anyone in frame at startup makes every unseen bottle log a `taken` on first
sight ("absent 158 s").

```bash
bash scripts/run_dashboard.sh                      # second terminal
.venv/bin/python -u main.py --live 2>&1 | tee ~/mesa-run-$(date +%F-%H%M).log
```

Expected on startup: `[live] push-to-talk: press ENTER, then speak your command.` and a
Vosk grammar load with **no** "Ignoring word missing in vocabulary" lines.

## 1. MED-DEMO — medication detection

Setup: `models/best.pt` present; camera at its taped position, 40–45° down over the
station; bottles at the 24" / 32" marks, ≥ 20 cm apart; table otherwise empty.

| # | Step | Expected |
|---|------|----------|
| 1.1 | `python scripts/detect_live.py`, each of the 8 medications alone at a mark | Correct label, confidence ≥ 0.45 |
| 1.2 | Three bottles at once | All three detected (four or more pushes the weakest under threshold; eight clustered reads as `tray`) |
| 1.3 | Probe each bottle you intend to stage, at 640×480 | ≥ 0.6 — anything that reads under 0.45 is an "unknown" and will trigger the wrong-medication line |
| 1.4 | Repeat under the lighting you will run in | Still ≥ 0.45; note any class that drops (the lighting envelope is measured in `docs/eval/`) |
| 1.5 | FPS overlay on the Pi | ≥ 5 FPS pose, detection every 3rd frame |

## 2. LOG-DEMO — compliance logging

Setup: schedule imported (`python scripts/import_schedule.py examples/prescriptions.csv`),
dashboard up, `main.py --live` running after a clean start.

| # | Step | Expected |
|---|------|----------|
| 2.1 | Lift a bottle **out of the frame**, wait ≥ 13 s, put it back on its mark | `taken <med>` row on the dashboard within a few seconds of its return |
| 2.2 | Wave a hand over a bottle (< 3 s) | No event (debounce) |
| 2.3 | Lift and return within 10 s | No `taken` |
| 2.4 | Hold the bottle *up* under the camera | No event — it never leaves the frame; a lift must leave the view |
| 2.5 | "Today's medications" tiles | The returned medication's doses tick ✅ (one event marks every scheduled dose of that medication for the day) |
| 2.6 | Open the dashboard from a phone on the same network | Same data at `http://<pi>:8501` |

## 3. Wrong medication (MED, unknown path)

Setup: `detection.table_roi` set for the rig (unknown boxes count only when their centre
is on the table).

| # | Step | Expected |
|---|------|----------|
| 3.1 | Known bottles staged, 2 minutes | **No** `wrong_medication` events (furniture boxes are outside the ROI) |
| 3.2 | Clear the table; an untrained **bottle** (TUMS) alone at a mark, ≥ 3 s | Spoken "That bottle isn't one of your medications." + `wrong_medication` row; repeats at most every 30 s while it stays |
| 3.3 | An untrained **box** (Benadryl) | Expect absorption into `mylanta` — this is the open-set finding, which is why the prop is a bottle |

## 4. FALL-DEMO — posture and fall

Setup: camera re-aimed at the fall zone (floor the camera sees with nothing in between),
then `python scripts/fall_diag.py --seconds 12` to confirm torso visibility ≈ 1.0 on a
staged lying pose. `python scripts/pose_live.py --echo` prints labels instead of speaking.

| # | Step | Expected |
|---|------|----------|
| 4.1 | Stand / sit / lie on cushions | `standing` / `sitting` / `lying` |
| 4.2 | Stay lying > 30 s | "Are you okay? possible fall detected" once; `possible_fall` row |
| 4.3 | Get up before 30 s | No check-in |
| 4.4 | Lie down again after getting up | New spell, new check-in |
| 4.5 | Lie behind the table edge | No body found — the fall zone must be clear floor |

## 5. VOICE-DEMO — push-to-talk

Setup: SP300U speakerphone at ~75 % volume (it clips above ~80 %); the Enter press goes
to the terminal running `main.py`.

| # | Press, then say | Expected spoken reply |
|---|------|----------|
| 5.1 | "what time is it" | Current date and time (read as "16:00") |
| 5.2 | "what is my next medication" | Next scheduled dose and time |
| 5.3 | "did I take my advil today" | Correct yes/no from the events table |
| 5.4 | "call for help" | "Okay, I'm calling for help now." + ntfy push |
| 5.5 | Say nothing after the press | "I didn't hear anything. Press the button and try again." |
| 5.6 | Mumble | "Sorry, I didn't catch that. Please say it again." |
| 5.7 | "stomach pill" / "antacid" / "herbal supplement" / "vitamin d" / "allergy pill" | The aliased medication is understood (`voice.med_aliases`) |

## 6. ESCALATE-DEMO — the chain

Setup: a private `alerts.ntfy_topic` in `config.yaml`; a phone subscribed. The room must be
**silent** after "Are you okay?" — the check-in window hears counting as `[unk]`.

| # | Step | Expected |
|---|------|----------|
| 6.1 | Fall, then answer **"I am okay"** (three words; no press needed) | `escalation_resolved`; nothing sent |
| 6.2 | Fall, stay silent 60 s | L2 push on the phone; `escalation_l2` row |
| 6.3 | Keep silent to 120 s | L3 caregiver alert; `escalation_l3` row. Open the ntfy app and refresh — iOS batches pushes when the app is idle |
| 6.4 | After L3, speak any coherent command | Escalation acknowledged; a new fall will ask again |
| 6.5 | Leave the room for the inactivity window | L1 check-in starts |

## 7. Stretch — schedule generator

| # | Step | Expected |
|---|------|----------|
| 7.1 | `python scripts/import_schedule.py examples/prescriptions.csv` | Entries printed; dashboard shows the schedule |
| 7.2 | A row with `frequency=3` and no times | 08:00 / 14:00 / 20:00 |

## 8. Robotics (stretch, not yet verified on hardware)

| # | Step | Expected |
|---|------|----------|
| 8.1 | `i2cdetect -y 1` | `0x40` (PCA9685) and `0x3c` (OLED) |
| 8.2 | Servo sweep (`docs/hardware-build.md`) | Head pans/tilts, no buzzing at rest |
| 8.3 | Walk across the frame | Head follows without oscillation |
| 8.4 | Trigger a fall / acknowledge | OLED ALERT face, then IDLE |

## 9. Soak

| # | Step | Expected |
|---|------|----------|
| 9.1 | `python scripts/soak_test.py --hours 2` | Peak memory flat (reference: `docs/eval/soak_results.md`) |
| 9.2 | Multi-hour unattended live run on the Pi | No crashes; memory stable — **not yet done** |
| 9.3 | Auto-start on reboot | **Not available yet** (HW-003): the service unit does not pass `--live` and keyboard push-to-talk needs a TTY |

---

### Regression (every session)

```bash
.venv/bin/python -m pytest      # all green
python main.py --demo           # synthetic event sequence end to end
```
