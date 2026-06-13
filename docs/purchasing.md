# MeSA 2.0 — Hardware Purchasing Guide

A budget-conscious bill of materials for a student, chosen so every part matches a hardware
plug we've already coded. Tick items off as you order. Prices are approximate (US, 2026) —
check **Micro Center (St. Davids, PA)** for local pickup on the Pi bundle to save shipping.

> See [hardware-build.md](hardware-build.md) for wiring + assembly, and
> [test-plan.md](test-plan.md) for how to verify each part once it arrives.

---

## ⚠️ Compatibility rules (these match the code)

1. **USB webcam, not the Pi Camera (CSI) ribbon module.** `detector.py` / `pose_live.py`
   use `cv2.VideoCapture(camera_index)` — that's a UVC/USB device.
2. **The Pi 5 has no 3.5 mm audio jack.** The speaker must be **USB audio** (a USB speaker,
   or an ~$8 USB sound-card dongle + any speaker). A USB *speakerphone* gives mic **and**
   speaker in one device.
3. **OLED must be the I²C version** (4 pins: VCC/GND/SDA/SCL), address **0x3C** — matches
   `SSD1306Display` (`SSD1306_I2C(128,64)`). Not the SPI variant.
4. **PCA9685** is standard I²C at **0x40** (the default `PCA9685ServoDriver` uses) — generic
   clones work with the Adafruit library.
5. **Servos get their own 5–6 V supply**, common ground with the Pi — never off the Pi.
6. **Use the official 27 W USB-C PSU** — the Pi 5 limits USB power on weaker chargers, which
   bites once camera + mic + speaker are all attached.
7. **microSD must be A2-rated**, 64 GB+.

---

## Tier 1 — Core build (all 5 graded demos: detection, logging, fall, voice, escalation)

| ✓ | Item | Spec to buy | ~$ | Software plug it feeds |
|---|------|-------------|----|------------------------|
| ☐ | Raspberry Pi 5 **8GB** | 4GB (~$60) works but tight | 80 | whole stack / systemd |
| ☐ | Official 27W USB-C PSU | genuine PD | 12 | power |
| ☐ | microSD 64GB **A2** | SanDisk Extreme / Samsung Evo+ | 13 | OS |
| ☐ | Active cooler | official Pi 5 cooler | 7 | thermals |
| ☐ | USB webcam 1080p | **UVC**; Logitech C920 ideal, or any $25–30 UVC cam | 28–50 | `mesa/vision/detector.py`, `scripts/pose_live.py` |
| ☐ | USB speakerphone *(mic + speaker)* | USB Audio Class; or split: USB mic ~$12 + USB speaker ~$13 | 25–30 | `mesa/audio/stt.py` (Vosk) + `mesa/audio/tts.py` |
| | **Tier 1 subtotal** | | **~$165–192** | |

## Tier 2 — Robotics personality add-on (Week 8: head tracking + OLED face)

| ✓ | Item | Spec to buy | ~$ | Software plug it feeds |
|---|------|-------------|----|------------------------|
| ☐ | Pan-tilt kit **with 2× servos** | MG90S (metal gear) preferred over SG90 | 13 | `PanTiltHead` (pan = ch0, tilt = ch1) |
| ☐ | PCA9685 16-ch driver | generic I²C, 0x40 | 9 | `mesa/hardware/servos.py` |
| ☐ | OLED SSD1306 **128×64 I²C** | 0x3C, 4-pin | 7 | `mesa/hardware/oled.py` |
| ☐ | 5V 3A supply + USB/screw breakout | separate servo power | 9 | servo V+ |
| ☐ | Jumper wires (F-F Dupont) + small breadboard | | 6 | I²C wiring |
| | **Tier 2 subtotal** | | **~$44** | |

**Full build: ~$210–235** (within the plan's $215–285 estimate).

---

## Where to save
- **4GB Pi** (−$20): runs YOLOv8n + MediaPipe + Vosk, but 8GB gives real headroom — keep 8GB if you can.
- **Generic 1080p webcam** vs C920 (−$20): detection runs at 640×480, so a cheap UVC cam is fine; the C920 just helps in dim light.
- **Skip Tier 2 for now**: robotics is a *stretch* in the plan. All five graded demos run on Tier 1 — and the null-driver plugs mean the code runs fine without servos/OLED.

## Free (no purchase)
- **Caregiver alerts** → ntfy.sh (`mesa/alerts/ntfy.py`), free push to your phone.
- **Training** → Google Colab free GPU. **STT model** → Vosk small-en, free download.

## When to order
- **Now:** webcam + mic/speaker (needed for laptop dev, Weeks 2–4).
- **By end of Week 3:** the Pi bundle (Pi, PSU, SD, cooler) so it's ready for Weeks 5/7.
- **Week 6:** the Tier 2 robotics parts.

## One-time Pi setup (not a purchase)
On the Pi, install the system backends the audio plugs need:
```bash
sudo apt install -y espeak-ng libportaudio2     # pyttsx3 (TTS) + sounddevice (mic)
sudo raspi-config                               # enable I2C (servos + OLED) and the camera
```
