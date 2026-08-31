# MeSA Demo Runbook — friendly audience edition

The scripted 10-minute show, staging rules learned the hard way, and the pre-flight
checklist. Target: first friendly-audience run ~Aug 12–13; dress rehearsal (ENG-008)
twice before anyone watches.

## Staging rules (non-negotiable — each one is a measured finding)

1. **Camera stays at its taped position.** Geometry is load-bearing
   (docs/eval/eval-report-v1.md). Never re-aim for a demo.
2. **LED lamp ON at its outlined spot** for any demo after ~6 PM or in a dim room.
   (Evening-dim detection: 41–77% without, 95–100% with — lamp_recovery.png.)
3. **Never demo 7:30–9:00 AM with the window uncovered** — direct-beam sun is the
   worst measured condition (0–41% on six meds). If morning: curtain closed, lights on.
4. **Bottles spread ≥20 cm apart at the marks** — clusters read as "tray".
5. **bayer_aspirin lives at the near (24") mark** — it under-confidences at 32".
6. **Wrong-med prop = an untrained BOTTLE (TUMS), not the Benadryl box** — boxes get
   absorbed into the mylanta class (open-set finding, 4.4 in the paper).
7. Table otherwise empty; no keyboard, no spare meds in frame.

## Pre-flight (T-30 min)

- [ ] Pi booted; `ssh mesa-pi` reachable; `git log -1` matches main.
- [ ] `models/best.pt` = current champion (v3 if it wins, else v2).
- [ ] Lighting per rules above; ask Claude for a light-check photo.
- [ ] `config.yaml`: real ntfy topic set; phone subscribed to it (ntfy app).
- [ ] events.db backed up/cleared for a clean dashboard.
- [ ] Streamlit dashboard up (`scripts/run_dashboard.sh`), phone on LAN can load it.
- [ ] Vosk + speaker sanity: "MeSA, what time is it?" answered aloud.
- [ ] Cushions placed for the FALL segment; camera swivel plan rehearsed (10 s).
- [ ] Fallback: pre-recorded demo video on the laptop, just in case.

## The show (~10 min)

**Act 1 — MED + LOG (3 min).** Bottles at the marks. Narrate: "MeSA watches the
medication station." Lift the advil, count 12, put it back → show the `taken` event
appear on the dashboard (phone in hand, audience can see). Ask MeSA: *"Did I take my
Advil?"* → "Yes, you've taken Advil today."

**Act 2 — Wrong medication (1 min).** Place the TUMS bottle at a mark → MeSA flags
unknown medication. One sentence on why this matters for an elderly user.

**Act 3 — VOICE (1 min).** "MeSA, what's my next medication?" / "What time is it?"
(Speak clearly, "MAY-suh", 1–2 m from the speakerphone.)

**Act 4 — FALL + ESCALATE (4 min).** Swivel camera to the fall zone (rehearsed move).
Vrishaank lies on the cushions. ~30 s → "Are you okay?" → stay silent → L2 push
notification arrives on the caregiver phone (show the phone). Second run: answer
*"MeSA, I'm okay"* → escalation clears by voice. Stand up, bow.

**Act 5 — the science (1 min).** Show the heatmap figure: "We measured exactly when
her eyes fail and what fixes it — that's the research paper." Point at the lamp.

## Q&A ammunition

- "What if the lighting changes?" → heatmap + lamp story (docs/eval/figures/).
- "What if it's the wrong pill?" → Act 2 + the box-absorption finding (honesty wins).
- "Is it a medical device?" → No: assistive aid framing, staged falls on cushions only.
- "What's it built on?" → Pi 5, one webcam, offline STT/TTS, ~$150 total, 10 weeks.
