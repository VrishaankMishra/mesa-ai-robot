"""Tests for the output integration hub (HW-005/006 wiring) and the person-center helper.

All run on Null drivers — no hardware — so the full engine->output path is verified on a
laptop. When real drivers are present the same code drives the OLED + servos unchanged."""

import pytest

from mesa.hardware.emotions import Emotion
from mesa.hardware.oled import NullDisplay
from mesa.hardware.outputs import OutputHub, build_output_hub
from mesa.hardware.servos import NullServoDriver, PanTiltHead
from mesa.hardware.tracking import person_center_from_pose


def _hub():
    disp = NullDisplay()
    head = PanTiltHead(NullServoDriver())
    return OutputHub(disp, head), disp, head


# --- OutputHub ---


def test_hub_renders_initial_emotion():
    disp = NullDisplay()
    OutputHub(disp)
    assert disp.current == Emotion.IDLE  # initial emotion shown on construction


def test_on_emotion_sets_and_renders():
    hub, disp, _ = _hub()
    hub.on_emotion(Emotion.ALERT)
    assert hub.emotions.current == Emotion.ALERT
    assert disp.current == Emotion.ALERT


def test_on_event_maps_and_renders():
    hub, disp, _ = _hub()
    hub.on_event("possible_fall")
    assert disp.current == Emotion.ALERT
    # unmapped event leaves it unchanged
    hub.on_event("nonsense")
    assert disp.current == Emotion.ALERT
    hub.on_event("escalation_resolved")
    assert disp.current == Emotion.IDLE


def test_track_drives_head_toward_person():
    hub, _, head = _hub()
    state = hub.track((0.9, 0.5))  # person to the right
    assert state is not None
    assert head.driver.last[0] > 90.0  # panned right


def test_track_without_head_is_noop():
    hub = OutputHub(NullDisplay(), head=None)
    assert hub.track((0.9, 0.5)) is None


def test_close_clears_display():
    hub, disp, _ = _hub()
    hub.on_emotion(Emotion.ALERT)
    hub.close()
    assert disp.current is None


# --- build_output_hub from config ---


def test_build_output_hub_uses_null_when_disabled():
    cfg = {"hardware": {"enabled": False, "pan_channel": 3, "tilt_channel": 4}}
    hub = build_output_hub(cfg)
    assert isinstance(hub.display, NullDisplay)
    assert isinstance(hub.head.driver, NullServoDriver)
    assert hub.head.pan_channel == 3 and hub.head.tilt_channel == 4


def test_build_output_hub_defaults_safe_with_empty_config():
    hub = build_output_hub({})  # no hardware block -> all defaults, Null drivers
    assert isinstance(hub.display, NullDisplay)
    assert hub.head.pan_channel == 0 and hub.head.tilt_channel == 1


# --- person_center_from_pose ---


def test_center_prefers_shoulder_midpoint():
    lm = {"left_shoulder": (0.4, 0.5), "right_shoulder": (0.6, 0.5), "nose": (0.0, 0.0)}
    assert person_center_from_pose(lm) == (0.5, 0.5)


def test_center_falls_back_to_nose_then_hips():
    assert person_center_from_pose({"nose": (0.3, 0.2)}) == (0.3, 0.2)
    cx, cy = person_center_from_pose({"left_hip": (0.2, 0.8), "right_hip": (0.4, 0.8)})
    assert (cx, cy) == pytest.approx((0.3, 0.8))


def test_center_none_when_no_usable_landmarks():
    assert person_center_from_pose({}) is None
    assert person_center_from_pose({"left_shoulder": (0.4, 0.5)}) is None  # need both


def test_center_drives_head_end_to_end():
    # the producer (pose -> center) feeding the consumer (head) on Null drivers
    hub, _, head = _hub()
    center = person_center_from_pose({"left_shoulder": (0.85, 0.5), "right_shoulder": (0.95, 0.5)})
    hub.track(center)
    assert head.driver.last[0] > 90.0
