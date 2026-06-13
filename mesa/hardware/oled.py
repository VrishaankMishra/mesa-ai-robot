"""OLED display plug module (HW-006).

``Display`` interface + a real SSD1306 implementation (Adafruit/PIL imported lazily,
Pi-only) + a NullDisplay fallback for laptop dev. ``get_display()`` picks the real one if
its libraries import. The face drawn per emotion is intentionally simple ASCII-ish art.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mesa.hardware.emotions import Emotion

# Tiny text "faces" — also used by NullDisplay's echo output.
_FACES = {
    Emotion.IDLE: "( o _ o )",
    Emotion.GREETING: "( ^ _ ^ )/",
    Emotion.LISTENING: "( o . o )?",
    Emotion.SPEAKING: "( o o o )~",
    Emotion.ALERT: "( ! _ ! )",
}


def face_for(emotion: Emotion) -> str:
    return _FACES.get(emotion, _FACES[Emotion.IDLE])


@runtime_checkable
class Display(Protocol):
    def show_emotion(self, emotion: Emotion) -> None: ...
    def clear(self) -> None: ...


class NullDisplay:
    """No-op display for laptop dev. Optionally prints the face."""

    def __init__(self, log: bool = False):
        self.log = log
        self.current: Emotion | None = None

    def show_emotion(self, emotion: Emotion) -> None:
        self.current = emotion
        if self.log:
            print(f"[oled] {emotion.value}: {face_for(emotion)}")

    def clear(self) -> None:
        self.current = None


class SSD1306Display:  # pragma: no cover - requires Pi + I2C hardware
    """Real 128x64 SSD1306 OLED over I2C, drawing a simple face per emotion."""

    def __init__(self, width: int = 128, height: int = 64):
        import adafruit_ssd1306
        import board
        import busio
        from PIL import Image, ImageDraw, ImageFont

        i2c = busio.I2C(board.SCL, board.SDA)
        self._disp = adafruit_ssd1306.SSD1306_I2C(width, height, i2c)
        self._Image, self._ImageDraw, self._ImageFont = Image, ImageDraw, ImageFont
        self.width, self.height = width, height
        self.clear()

    def show_emotion(self, emotion: Emotion) -> None:
        img = self._Image.new("1", (self.width, self.height))
        draw = self._ImageDraw.Draw(img)
        font = self._ImageFont.load_default()
        draw.text((4, self.height // 2 - 6), face_for(emotion), font=font, fill=255)
        self._disp.image(img)
        self._disp.show()

    def clear(self) -> None:
        self._disp.fill(0)
        self._disp.show()


def get_display(prefer_hardware: bool = True, **kwargs) -> Display:
    if prefer_hardware:
        try:
            return SSD1306Display(**kwargs)
        except Exception:
            pass
    return NullDisplay(**({} if prefer_hardware else kwargs))
