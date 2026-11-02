# MeSA 2.0 — Bill of Materials

What the robot is built from, chosen so every part matches a software plug in the
repository. Prices are approximate (US, 2026) and listings rotate — match the **spec**,
not the exact product. First-party pages (raspberrypi.com, adafruit.com, canakit.com)
are the most durable links.

See [hardware-build.md](hardware-build.md) for assembly and [test-plan.md](test-plan.md)
for how each part is verified.

---

## Compatibility rules (these match the code)

1. **USB webcam, not the Pi Camera (CSI) ribbon module.** The vision code uses
   `cv2.VideoCapture(camera_index)` — a UVC device.
2. **The Pi 5 has no 3.5 mm audio jack.** Audio must be USB: a USB speakerphone gives mic
   and speaker in one device, which is what the voice stack is pinned to by name.
3. **OLED must be the I²C version** (VCC/GND/SDA/SCL), address `0x3C` — matches
   `SSD1306Display`. Not the SPI variant.
4. **PCA9685** at `0x40` (the default the servo driver uses); generic clones work.
5. **Servos get their own 5–6 V supply**, common ground with the Pi — never off the Pi.
6. **Official 27 W USB-C PSU.** The Pi 5 limits USB power on weaker chargers, which bites
   once camera, mic and speaker are all attached.
7. **microSD A2-rated**, 64 GB+.

---

## Tier 1 — the core rig (all five demos run on this) — as built

| Item | Spec | ~$ | Feeds |
|------|------|----|-------|
| Raspberry Pi 5 **8 GB** | 4 GB works but is tight | 80 | the whole stack |
| Official 27 W USB-C PSU | genuine PD | 12 | power |
| microSD 64 GB A2 | SanDisk Extreme / Samsung Evo+ | 13 | OS |
| Active cooler | official Pi 5 cooler | 7 | thermals |
| USB webcam 1080p | **UVC**; Logitech C920 in use | 28–50 | `mesa/vision/` |
| USB speakerphone | USB Audio Class; SP300U in use | 25–30 | `mesa/audio/` |
| LED desk lamp | any neutral/cool LED lamp | ~10 | the measured dim-light fix |
| **Tier 1 total** | | **~$175–200** | |

Kits (CanaKit Pi 5 Starter Kit PRO 8 GB and similar) cover the Pi, PSU, cooler and microSD
in one box.

**Props:** 8 real medication containers, one untrained *bottle* for the wrong-medication
act, masking tape (camera position, 24"/32" marks, lamp outline, fall zone), a tape
measure, cushions for staged falls, an extension cord.

## Tier 2 — robotics personality (stretch; coded, not assembled)

| Item | Spec | ~$ | Feeds |
|------|------|----|-------|
| Pan-tilt kit **with 2× servos** | MG90S (metal gear) over SG90 | 13 | `PanTiltHead` (pan = ch0, tilt = ch1) |
| PCA9685 16-ch driver | generic I²C, 0x40 | 9 | `mesa/hardware/servos.py` |
| OLED SSD1306 **128×64 I²C** | 0x3C, 4-pin | 7 | `mesa/hardware/oled.py` |
| 5 V 3 A supply + screw breakout | separate servo power | 9 | servo V+ |
| Momentary push button + jumper wires | for push-to-talk on BCM 17 | 3 | `voice.push_to_talk.source: gpio` |
| Jumper wires (F-F Dupont) + small breadboard | | 6 | I²C wiring |
| **Tier 2 total** | | **~$47** | |

**Full build: ~$220–250.**

## Where to save
- **4 GB Pi** (−$20): runs YOLOv8n + MediaPipe + Vosk, with less headroom.
- **Generic 1080p webcam** (−$20): detection runs at 640×480, so a cheap UVC camera is
  fine; the C920 helps in dim light.
- **Skip Tier 2**: all five demos run on Tier 1, and the null drivers mean the code runs
  without servos or an OLED.

## Free (no purchase)
- **Caregiver alerts** → ntfy.sh (`mesa/alerts/ntfy.py`).
- **Training** → Google Colab free GPU. **STT model** → Vosk small-en (download in
  `models/README.md`); faster-whisper tiny as the open-vocabulary option.

## One-time Pi setup (not a purchase)
```bash
sudo apt install -y espeak-ng libportaudio2     # pyttsx3 (TTS) + sounddevice (mic)
sudo raspi-config                               # enable I2C for the Tier 2 parts
```
