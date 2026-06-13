"""Tests for hardware plug modules using the null fallbacks (HW-004/006).

These verify the interfaces + factories behave on a laptop (no Pi). The real PCA9685 /
SSD1306 paths require hardware and are excluded from coverage.
"""

from mesa.hardware.emotions import Emotion, EmotionController, emotion_for
from mesa.hardware.oled import Display, NullDisplay, face_for, get_display
from mesa.hardware.servos import (
    NullServoDriver,
    PanTiltHead,
    ServoDriver,
    get_servo_driver,
)


# --- servos ---
def test_get_servo_driver_falls_back_to_null():
    driver = get_servo_driver(prefer_hardware=False)
    assert isinstance(driver, NullServoDriver)
    assert isinstance(driver, ServoDriver)  # satisfies the protocol


def test_pantilt_head_writes_both_channels():
    driver = NullServoDriver()
    head = PanTiltHead(driver, pan_channel=0, tilt_channel=1)
    head.track((0.9, 0.5))
    assert 0 in driver.last and 1 in driver.last
    assert driver.last[0] > 90.0  # panned right toward the person


def test_pantilt_center():
    driver = NullServoDriver()
    head = PanTiltHead(driver)
    state = head.center()
    assert state.pan == 90.0 and driver.last[0] == 90.0


# --- emotions ---
def test_emotion_for_known_and_unknown():
    assert emotion_for("possible_fall") == Emotion.ALERT
    assert emotion_for("escalation_resolved") == Emotion.IDLE
    assert emotion_for("nonsense") is None


def test_emotion_controller_keeps_state_on_unmapped_event():
    ec = EmotionController()
    ec.on_event("help_request")
    assert ec.current == Emotion.ALERT
    ec.on_event("nonsense")           # unmapped -> unchanged
    assert ec.current == Emotion.ALERT
    ec.on_event("escalation_resolved")
    assert ec.current == Emotion.IDLE


# --- oled ---
def test_get_display_falls_back_to_null():
    disp = get_display(prefer_hardware=False)
    assert isinstance(disp, NullDisplay)
    assert isinstance(disp, Display)


def test_null_display_tracks_current_emotion():
    disp = NullDisplay()
    disp.show_emotion(Emotion.GREETING)
    assert disp.current == Emotion.GREETING
    disp.clear()
    assert disp.current is None


def test_every_emotion_has_a_face():
    for e in Emotion:
        assert isinstance(face_for(e), str) and face_for(e)
