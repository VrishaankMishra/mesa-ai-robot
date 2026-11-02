# MeSA 2.0 — Hardware Build

The physical side of the robot: what the rig is, how it was brought up, and what the
stretch hardware still needs. Software plugs exist for everything here (null drivers keep
the code runnable without the parts).

> ⚠️ **Safety first.** MeSA is an *assistive aid, not a medical device*. Test fall
> detection only with staged poses on cushions. Never rely on it for real emergencies.

---

## A. The rig as built

| Part | What is in use | Notes |
|------|----------------|-------|
| Compute | Raspberry Pi 5 8 GB, official 27 W USB-C PSU, A2 microSD, active cooler | A phone charger browns out under camera + inference load |
| Camera | Logitech C920 (UVC) | Taped above the medication station, looking down 40–45°, bottle marks at 24" and 32" from the lens |
| Audio | USB speakerphone (SP300U) | Mic and speaker in one device; the Pi 5 has no 3.5 mm jack. Run at ~75 % volume — it clips above ~80 % |
| Light | LED desk lamp at a taped outline | The active-illumination arm of the study; aimed across at the label faces, not down at the table |
| Props | 8 real medication containers + an untrained bottle (TUMS) as the wrong-medication prop | Boxes get absorbed into the trained box class; the prop must be a bottle |
| Fall zone | Cushions on floor the camera can see with nothing in between | The camera is re-aimed from the station to the floor for the fall act |

Parts cost about $150 (see `docs/purchasing.md`).

**Geometry is load-bearing.** The detector was trained from the top-down station view; a
side-on or across-the-room view drops confidence to 0.1–0.4. The same geometry cannot see
the floor, so one camera serves medication detection *or* fall detection at a time — a
second camera or a much wider field of view is the first hardware change a product would
need. Any camera move is followed by a frame check against `eval_data/` (station) or
`scripts/fall_diag.py` (fall zone).

**Camera controls.** The C920 defaults to auto-exposure, auto-white-balance and continuous
autofocus, each of which silently changes what the detector sees. `vision.camera` in
`config.yaml` can lock them at values measured at the station; UVC settings outlive the
process, so `restore_auto()` runs after any locked pass.

## B. Bring-up, as done

### Step 1 — Capture rig
Camera at station height, marks taped, rig photographed (`docs/media/`). The dataset
protocol is in `docs/capture-protocol.md`.

### Step 2 — Raspberry Pi 5
1. Pi OS 64-bit via Raspberry Pi Imager; SSH and Wi-Fi set in the imager.
2. Cooler fitted; then on the Pi:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y python3-venv python3-pip espeak-ng libportaudio2
   sudo raspi-config        # Interface Options -> I2C (for the stretch hardware)
   git clone <repo> && cd mesa-ai-robot
   bash scripts/setup_env.sh
   .venv/bin/pip install -r requirements-pi.txt
   ```
   `espeak-ng` backs pyttsx3; `libportaudio2` backs sounddevice — without them the audio
   stack imports but produces nothing.
3. Camera enumerates as `/dev/video0`; the speakerphone shows in `aplay -l` / `arecord -l`.
   Card numbers move across reboots, so the capture scripts resolve the speakerphone by
   name, not index.
4. Benchmark: `python scripts/benchmark.py --model models/best.pt`. The live worker runs
   640×480, pose every frame, YOLO every 3rd frame, which holds ≥ 5 FPS on the Pi 5.

### Step 3 — Running it
MeSA is started by hand over SSH (`docs/test-plan.md` §0). The systemd unit
(`deploy/mesa.service`, `deploy/install_pi.sh`) is not yet usable: it launches `main.py`
without `--live`, and keyboard push-to-talk needs a TTY that systemd does not provide.
Auto-start on boot (HW-003) waits on a GPIO push-to-talk button
(`voice.push_to_talk.source: gpio`, BCM 17) or a dashboard "Talk" button.

### Step 4 — Dashboard on the LAN
```bash
bash scripts/run_dashboard.sh         # serves on 0.0.0.0:8501
```
Reachable from a phone on the same network. Away from home, a phone hotspot with
"Maximize Compatibility" on (2.4 GHz) is what works; public Wi-Fi usually isolates clients
and the Pi cannot pass a captive portal.

### Step 5 — Soak
`python scripts/soak_test.py --hours 2` drives the decision engine with synthetic events;
the recorded run (`docs/eval/soak_results.md`) shows flat peak memory over a simulated
week. A multi-hour unattended live run on the robot has not been done.

## C. Stretch hardware — coded, not yet on the bench

### Servo head (HW-004/005)
PCA9685 ↔ Pi (I2C):

| PCA9685 | Pi 5 pin |
|---------|----------|
| VCC | 3V3 (pin 1) |
| GND | GND (pin 6) |
| SDA | GPIO2 / SDA (pin 3) |
| SCL | GPIO3 / SCL (pin 5) |
| V+ | **external 5–6 V** servo supply (never the Pi's 3V3) |

1. Servos on their own 5–6 V supply, common ground with the Pi.
2. Pan servo → channel **0**, tilt → channel **1** (`hardware.pan_channel` / `tilt_channel`).
3. `i2cdetect -y 1` shows `0x40`.
4. Sweep test on the Pi:
   ```python
   from mesa.hardware.servos import get_servo_driver
   d = get_servo_driver()
   for a in (0, 90, 180, 90): d.set_angle(0, a)
   ```
5. Tracking: `mesa/hardware/tracking.py` is a tested proportional controller; feed the
   detected person's normalised centre into a `PanTiltHead` and tune `track_gain`,
   `track_deadzone`, `track_max_step` in `config.yaml`. Note that a moving camera
   invalidates the taped station geometry — the head belongs on a second camera.

### OLED face (HW-006)
SSD1306 128×64 I²C on the same bus (VCC→3V3, GND→GND, SDA→pin 3, SCL→pin 5);
`i2cdetect` shows `0x3c`. The engine drives it through `set_emotion`
(`mesa/hardware/emotions.py`: ALERT on fall/help/escalation, IDLE on acknowledge).
`hardware.enabled: true` in `config.yaml` selects the real drivers; the factories fall
back to null drivers if the libraries or bus are absent, so `true` is always safe to try.

### Push-to-talk button (HW-003 prerequisite)
A momentary button on BCM 17 to ground; set `voice.push_to_talk.source: gpio` only once it
is wired and tested. `auto` prefers GPIO and gpiozero constructs a Button on an unwired pin
without raising, so on a button-less Pi `auto` yields a trigger that can never fire.

## D. Wiring quick-reference (all I2C on one bus)
```
Pi 5 (I2C bus 1)
 ├─ pin 1  3V3 ───┬── PCA9685 VCC ── SSD1306 VCC
 ├─ pin 3  SDA ───┼── PCA9685 SDA ── SSD1306 SDA
 ├─ pin 5  SCL ───┼── PCA9685 SCL ── SSD1306 SCL
 └─ pin 6  GND ───┴── PCA9685 GND ── SSD1306 GND ── (servo PSU GND, common)
PCA9685 V+  ── external 5–6V servo power supply (+)
PCA9685 ch0 ── pan servo   ·   ch1 ── tilt servo
GPIO17 ── momentary button ── GND   (push-to-talk)
```
