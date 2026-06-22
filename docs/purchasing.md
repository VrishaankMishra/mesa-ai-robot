# MeSA 2.0 — Hardware Purchasing Guide

A budget-conscious bill of materials for a student, chosen so every part matches a hardware
plug we've already coded. Tick items off as you order. Prices are approximate (US, 2026) —
check **Micro Center (St. Davids, PA)** for local pickup on the Pi bundle to save shipping.

> **Buy links** verified June 2026. Amazon ASINs can rotate or go out of stock; the
> first-party links (raspberrypi.com, adafruit.com, canakit.com) are the most durable. Match
> the **spec**, not the exact listing — any part meeting the "Spec to buy" column works.

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

| ✓ | Item | Spec to buy | ~$ | Software plug it feeds | Buy link |
|---|------|-------------|----|------------------------|----------|
| ☐ | Raspberry Pi 5 **8GB** | 4GB (~$60) works but tight | 80 | whole stack / systemd | [raspberrypi.com](https://www.raspberrypi.com/products/raspberry-pi-5/) · [CanaKit board](https://www.canakit.com/raspberry-pi-5-8gb.html) |
| ☐ | Official 27W USB-C PSU | genuine PD | 12 | power | [CanaKit](https://www.canakit.com/official-raspberry-pi-5-power-supply-27w-usb-c.html) |
| ☐ | microSD 64GB **A2** | SanDisk Extreme / Samsung Evo+ | 13 | OS | [SanDisk Extreme 64GB A2](https://www.amazon.com/SanDisk-Extreme-microSD-UHS-I-Adapter/dp/B07FCMBLV6) |
| ☐ | Active cooler | official Pi 5 cooler | 7 | thermals | included in kits ↓, or raspberrypi.com |
| ☐ | USB webcam 1080p | **UVC**; Logitech C920 ideal, or any $25–30 UVC cam | 28–50 | `mesa/vision/detector.py`, `scripts/pose_live.py` | [Logitech C920S](https://www.amazon.com/Logitech-C920S-Pro-HD-Webcam/dp/B07K986YLL) |
| ☐ | USB speakerphone *(mic + speaker)* | USB Audio Class; or split: USB mic ~$12 + USB speaker ~$13 | 25–30 | `mesa/audio/stt.py` (Vosk) + `mesa/audio/tts.py` | [USB speakerphone](https://www.amazon.com/Microphone-Speaker-Business-Conference-Speakerphone/dp/B078RJK4FW) |
| | **Tier 1 subtotal** | | **~$165–192** | | |

> **One-box bundle** (covers the Pi + PSU + cooler + microSD rows): [CanaKit Pi 5 Starter Kit PRO – 8GB](https://www.amazon.com/CanaKit-Raspberry-Starter-Kit-PRO/dp/B0CRSNCJ6Y) or [Vemico Pi 5 8GB kit](https://www.amazon.com/Vemico-Raspberry-Active-Screwdriver-Included/dp/B0DFMNHL62).

## Tier 2 — Robotics personality add-on (Week 8: head tracking + OLED face)

| ✓ | Item | Spec to buy | ~$ | Software plug it feeds | Buy link |
|---|------|-------------|----|------------------------|----------|
| ☐ | Pan-tilt kit **with 2× servos** | MG90S (metal gear) preferred over SG90 | 13 | `PanTiltHead` (pan = ch0, tilt = ch1) | [Pan-tilt kit + 2 servos](https://www.amazon.com/Compatible-Steering-Bracket-Camera-Ultrasonic/dp/B0H22GM6Z7) — *confirm servos included; else add [MG90S 2-pack](https://www.amazon.com/s?k=MG90S+servo+2+pack)* |
| ☐ | PCA9685 16-ch driver | generic I²C, 0x40 | 9 | `mesa/hardware/servos.py` | [Adafruit #815](https://www.adafruit.com/product/815) · [Amazon](https://www.amazon.com/Adafruit-16-Channel-12-bit-Servo-Driver/dp/B00E4WEXO4) |
| ☐ | OLED SSD1306 **128×64 I²C** | 0x3C, 4-pin | 7 | `mesa/hardware/oled.py` | [Adafruit #326](https://www.adafruit.com/product/326) |
| ☐ | 5V 3A supply + USB/screw breakout | separate servo power | 9 | servo V+ | search "5V 3A + screw-terminal breakout" |
| ☐ | Jumper wires (F-F Dupont) + small breadboard | | 6 | I²C wiring | generic Dupont + breadboard kit |
| | **Tier 2 subtotal** | | **~$44** | | |

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
