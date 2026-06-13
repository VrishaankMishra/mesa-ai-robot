# MeSA 2.0 — Manual Test Plan

Per-feature manual checks to run before each demo. Automated unit tests (`pytest`, 120+)
cover the pure logic; this document covers what only a human + hardware can verify.
Each maps to a Definition-of-Done demo. Record pass/fail + notes per run.

> ⚠️ Test fall detection with staged poses on cushions only. MeSA is an assistive aid.

---

## 1. MED-DEMO — medication detection (VIS)
Setup: trained `best.pt` in `models/`, run `python scripts/detect_live.py`.

| # | Step | Expected |
|---|------|----------|
| 1.1 | Place each of the 5–6 known bottles, one at a time, 0.5–1.5 m from camera | Correct label, confidence ≥ threshold, box drawn green |
| 1.2 | Repeat under bright, dim, and mixed lighting | Still correct; note any class that drops below 90% |
| 1.3 | Present an **unknown** bottle (not in training set) | Labeled "unknown" in **red** (wrong-medication path) |
| 1.4 | Present two bottles at once | Both detected and labeled |
| 1.5 | Read FPS overlay | ≥ 5 FPS on the Pi |

## 2. LOG-DEMO — compliance logging (ENG/DASH)
Setup: `python scripts/import_schedule.py examples/prescriptions.csv`, start the dashboard
(`bash scripts/run_dashboard.sh`) and the detection→engine path.

| # | Step | Expected |
|---|------|----------|
| 2.1 | Remove a bottle, wait ~12 s, return it | A `taken` event appears in the dashboard event table |
| 2.2 | Briefly wave a hand over a bottle (<3 s occlusion) | **No** event (debounce holds) |
| 2.3 | Remove and return quickly (<10 s absent) | **No** `taken` event |
| 2.4 | Check "Today's medications" tiles | Returned med flips to ✅ Taken |
| 2.5 | Refresh dashboard from a phone on the LAN | Same data visible (DASH-002) |

## 3. FALL-DEMO — posture & fall (VIS)
Setup: `python scripts/pose_live.py --echo` (use `--echo` to print instead of speak).

| # | Step | Expected |
|---|------|----------|
| 3.1 | Stand in frame | Label "standing" |
| 3.2 | Sit down | Label "sitting" |
| 3.3 | Lie down on cushions | Label "lying" |
| 3.4 | Stay lying > 30 s | Spoken "Are you okay?" check-in fires once |
| 3.5 | Get up before 30 s | No check-in (timer reset) |
| 3.6 | Lie down again after getting up | Check-in fires again (new spell) |

## 4. VOICE-DEMO — voice assistant (VOX)
Setup: Vosk model in `models/`, `python scripts/voice_loop.py` (mic + speaker connected).

| # | Say (after wake word "MeSA") | Expected spoken reply |
|---|------|----------|
| 4.1 | "MeSA, what time is it?" | Current date + time |
| 4.2 | "MeSA, what's my next medication?" | Next scheduled med + time |
| 4.3 | "MeSA, did I take my Vitamin D?" | Correct yes/no from the events table |
| 4.4 | "MeSA, call for help" | "Calling for help" + ntfy push arrives on caregiver phone |
| 4.5 | Speak without the wake word | Ignored |
| 4.6 | Mumble / unknown phrase | "Sorry, say again?" fallback |
| 4.7 | Repeat 4.1–4.4 at 1–2 m in normal room noise | ≥ 90% success (VOX-005) |

## 5. ESCALATE-DEMO — escalation chain (ENG)
Setup: set a real private `alerts.ntfy_topic` in `config.yaml`; subscribe a phone to it.
Tip: temporarily lower `escalation.l1_wait_seconds` to demo quickly.

| # | Step | Expected |
|---|------|----------|
| 5.1 | Trigger a fall (lie > 30 s) and **respond** to the check-in | Escalation resolves, no notification sent |
| 5.2 | Trigger a fall and **don't respond** for the L1 window | L2 ntfy push arrives on the phone |
| 5.3 | Continue not responding through the L2 window | L3 caregiver alert fires |
| 5.4 | Leave the room; no person for the inactivity window | Escalation L1 check-in starts |
| 5.5 | Check the dashboard event log | `escalation_l1/l2/l3` / `escalation_resolved` rows present |

## 6. STRETCH — schedule generator
| # | Step | Expected |
|---|------|----------|
| 6.1 | `python scripts/import_schedule.py examples/prescriptions.csv` | Prints loaded entries; dashboard shows the schedule |
| 6.2 | Add a row with an explicit time | Appears at that time |
| 6.3 | Add a row with `frequency=3` and no times | Scheduled at 08:00/14:00/20:00 |

## 7. Robotics (Week 8, optional / stretch)
| # | Step | Expected |
|---|------|----------|
| 7.1 | `i2cdetect -y 1` | Shows `0x40` (PCA9685) and `0x3c` (OLED) |
| 7.2 | Run servo sweep snippet (hardware-build.md Step 6) | Head pans/tilts through range, no buzzing at rest |
| 7.3 | Walk across the frame | Head follows, keeps you roughly centered, no jitter/oscillation |
| 7.4 | Trigger a fall/help | OLED shows ALERT face |
| 7.5 | Acknowledge | OLED returns to IDLE face |

## 8. Integration / soak (Week 7)
| # | Step | Expected |
|---|------|----------|
| 8.1 | `python scripts/soak_test.py --hours 2` | Peak memory flat |
| 8.2 | Real 2-hour unattended run on the Pi | No crashes in `journalctl -u mesa`; memory stable |
| 8.3 | `sudo reboot` | MeSA auto-starts (HW-003) |

---

### Regression (run every session)
```bash
.venv/bin/python -m pytest      # all green
python main.py --demo           # integrated event flow prints expected sequence
```
