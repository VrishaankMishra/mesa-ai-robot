"""Output integration hub (HW-005 / HW-006 wiring).

Ties the decision engine's output hooks to the physical-ish outputs: the OLED face and the
pan/tilt head. It holds whatever drivers :func:`~mesa.hardware.oled.get_display` and
:func:`~mesa.hardware.servos.get_servo_driver` return — real on a Pi, Null on a laptop — so
the whole path is exercisable (and unit-tested) with no hardware attached. When real
hardware arrives, nothing here changes; the factories simply return the real drivers.

The engine calls :meth:`on_emotion` (it sets an explicit ``Emotion``); :meth:`on_event`
maps richer event-type strings (greeting/listening/speaking/escalation_*) through
:class:`~mesa.hardware.emotions.EmotionController` for callers that have an event name
rather than an emotion. :meth:`track` drives the head from a person-center.
"""

from __future__ import annotations

from mesa.config import get
from mesa.hardware.emotions import Emotion, EmotionController
from mesa.hardware.oled import Display, get_display
from mesa.hardware.servos import PanTiltHead, get_servo_driver
from mesa.hardware.tracking import PanTiltController, PanTiltState, Point


class OutputHub:
    """Single place the engine pushes outputs to. Safe with Null or real drivers."""

    def __init__(
        self,
        display: Display,
        head: PanTiltHead | None = None,
        emotions: EmotionController | None = None,
    ):
        self.display = display
        self.head = head
        self.emotions = emotions or EmotionController()
        # Reflect the initial emotion on the display immediately.
        self.display.show_emotion(self.emotions.current)

    def on_emotion(self, emotion: Emotion) -> Emotion:
        """Set an explicit emotion and render it. This is what ``engine.set_emotion`` wires to."""
        self.emotions.set(emotion)
        self.display.show_emotion(emotion)
        return emotion

    def on_event(self, event_type: str) -> Emotion:
        """Map an event-type string to an emotion; only redraw if it changed."""
        before = self.emotions.current
        current = self.emotions.on_event(event_type)
        if current != before:
            self.display.show_emotion(current)
        return current

    def track(self, person_center: Point | None) -> PanTiltState | None:
        """Nudge the head toward the person. No-op (returns None) if no head is configured."""
        if self.head is None:
            return None
        return self.head.track(person_center)

    def center_head(self) -> PanTiltState | None:
        if self.head is None:
            return None
        return self.head.center()

    def close(self) -> None:
        self.display.clear()
        if self.head is not None:
            self.head.close()


def build_output_hub(cfg: dict, prefer_hardware: bool | None = None) -> OutputHub:
    """Construct an :class:`OutputHub` from config.

    ``hardware.enabled`` (or the ``prefer_hardware`` override) decides whether to attempt
    real Pi drivers; either way the factories fall back to Null drivers if the libraries or
    bus aren't present, so this is always safe to call on a laptop.
    """
    enabled = get(cfg, "hardware.enabled", False) if prefer_hardware is None else prefer_hardware
    display = get_display(prefer_hardware=enabled)
    driver = get_servo_driver(prefer_hardware=enabled)
    controller = PanTiltController(
        gain=get(cfg, "hardware.track_gain", 40.0),
        deadzone=get(cfg, "hardware.track_deadzone", 0.05),
        max_step=get(cfg, "hardware.track_max_step", 4.0),
        invert_pan=get(cfg, "hardware.invert_pan", False),
        invert_tilt=get(cfg, "hardware.invert_tilt", False),
    )
    head = PanTiltHead(
        driver,
        controller=controller,
        pan_channel=get(cfg, "hardware.pan_channel", 0),
        tilt_channel=get(cfg, "hardware.tilt_channel", 1),
    )
    return OutputHub(display, head)
