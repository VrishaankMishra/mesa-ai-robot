# MeSA 2.0 — Hardware Build & Robotics Playbook

The step-by-step physical/robotics work that can't be coded. Software hooks already exist
for every item here (servo/OLED plug modules, systemd unit, benchmark/soak scripts).

> ⚠️ **Safety first.** MeSA is an *assistive aid, not a medical device*. Test fall
> detection only with staged poses on cushions. Never rely on it for real emergencies.

---

## A. Procurement (order in this sequence)

**Now / Week 1 — laptop dev peripherals**
- H5 USB webcam (Logitech C920, $50)
- H6 USB microphone ($20)
- H7 Speaker (USB or 3.5 mm, $15)

**By end of Week 3 — the Pi bundle** (so it arrives before Week 5/7)
- H1 Raspberry Pi 5 8GB ($80) · H2 27W USB-C PSU ($12) · H3 64GB+ A2 microSD ($15) · H4 Active cooler ($5)

**Week 6 — robotics extras**
- H8 2× servos (SG90/MG90S, $15) · H9 PCA9685 driver ($10) · H10 Pan-tilt bracket ($15) · H11 SSD1306 OLED 128×64 I2C ($10)

**Test props:** 5–10 real medicine bottles, a tray/“medication station” with a fixed
camera mount, masking tape to mark the floor test zone and bottle positions.

---

## B. Step-by-step build

### Step 1 — Capture rig (Week 1, before dataset)
1. Mount the webcam at the medication-station height, pointed at the bottle tray.
2. Mark bottle positions and the 0.5/1.0/1.5 m floor distances with tape.
3. Photograph the rig and commit the photo to `docs/` (proves repeatability).

### Step 2 — Photograph the dataset (Week 1)
Run `python scripts/capture.py --bottle <name> --lighting <bright|dim|mixed> --angle <deg> --distance <m>`
for every cell of the matrix in `docs/capture-protocol.md`. Target ≥600 images.

### Step 3 — Raspberry Pi 5 bring-up (Week 5, HW-001)
1. Flash **Pi OS 64-bit** to the microSD (Raspberry Pi Imager); set hostname, enable SSH + Wi-Fi.
2. Fit the active cooler, boot, `ssh` in, then:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo raspi-config        # Interface Options -> enable I2C and Camera
   sudo apt install -y python3-venv python3-pip libatlas-base-dev
   git clone https://github.com/VrishaankMishra/mesa-ai-robot.git
   cd mesa-ai-robot && python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt -r requirements-pi.txt
   ```
3. Plug in the webcam; verify it enumerates (`ls /dev/video*`).
4. Benchmark: `python scripts/benchmark.py --model models/best.pt` → record the FPS in
   `docs/eval-report-template.md`. If pose < 5 FPS, raise `detection_every_n_frames` /
   drop resolution in `config.yaml`.

### Step 4 — Deploy as a service (Week 7, HW-003)
```bash
sudo bash deploy/install_pi.sh        # installs + enables mesa.service
journalctl -u mesa -f                 # watch logs
sudo reboot                           # confirm it auto-starts on boot
```

### Step 5 — Dashboard on the LAN (Week 7, DASH-002)
```bash
bash scripts/run_dashboard.sh         # serves on 0.0.0.0:8501
```
Browse to `http://<pi-ip>:8501` from a phone on the same Wi-Fi.

### Step 6 — Servo head wiring (Week 8, HW-004)
PCA9685 ↔ Pi (I2C):

| PCA9685 | Pi 5 pin |
|---------|----------|
| VCC | 3V3 (pin 1) |
| GND | GND (pin 6) |
| SDA | GPIO2 / SDA (pin 3) |
| SCL | GPIO3 / SCL (pin 5) |
| V+ | **external 5–6V** servo supply (not the Pi 3V3) |

1. Power servos from a **separate 5–6V supply**, common ground with the Pi. Never drive
   two servos from the Pi's 3V3.
2. Pan servo → PCA9685 channel **0**, tilt servo → channel **1** (matches `PanTiltHead` defaults).
3. Mount the camera on the pan-tilt bracket.
4. Verify I2C sees the board: `i2cdetect -y 1` (expect `0x40`).
5. Sweep test (in a Python REPL on the Pi):
   ```python
   from mesa.hardware.servos import get_servo_driver
   d = get_servo_driver()
   for a in (0, 90, 180, 90): d.set_angle(0, a)
   ```

### Step 7 — Person tracking (Week 8, HW-005)
The control law (`mesa/hardware/tracking.py`) is done and tested. On the Pi, feed the
detected person's normalized center into a `PanTiltHead`:
```python
head.track((cx, cy))   # cx, cy in [0,1]; (0.5,0.5)=centered
```
Tune `gain`, `deadzone`, `max_step` in code/config until the head follows smoothly with no
jitter/oscillation. Set `invert_pan`/`invert_tilt` if the head moves the wrong way.

### Step 8 — OLED face (Week 8, HW-006)
1. Wire SSD1306 to the same I2C bus (VCC→3V3, GND→GND, SDA→pin 3, SCL→pin 5).
2. `i2cdetect -y 1` should now also show `0x3c`.
3. Pass a display into the engine so events drive the face:
   ```python
   from mesa.hardware.oled import get_display
   disp = get_display()
   engine = DecisionEngine(..., set_emotion=disp.show_emotion)
   ```
   ALERT on fall/help/escalation, IDLE on acknowledge (see `mesa/hardware/emotions.py`).

### Step 9 — Soak test (Week 7, ENG-007)
`python scripts/soak_test.py --hours 2` → peak memory should stay flat. Then do a **real**
2-hour unattended run on the Pi and watch `journalctl -u mesa -f` for crashes.

---

## C. Wiring quick-reference (all I2C on one bus)
```
Pi 5 (I2C bus 1)
 ├─ pin 1  3V3 ───┬── PCA9685 VCC ── SSD1306 VCC
 ├─ pin 3  SDA ───┼── PCA9685 SDA ── SSD1306 SDA
 ├─ pin 5  SCL ───┼── PCA9685 SCL ── SSD1306 SCL
 └─ pin 6  GND ───┴── PCA9685 GND ── SSD1306 GND ── (servo PSU GND, common)
PCA9685 V+  ── external 5–6V servo power supply (+)
PCA9685 ch0 ── pan servo   ·   ch1 ── tilt servo
```
