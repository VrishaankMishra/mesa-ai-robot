"""Tests for voice-grid aggregation (RES-004)."""

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "eval_voice_analyze",
    Path(__file__).resolve().parent.parent / "scripts" / "eval_voice_analyze.py")
va = importlib.util.module_from_spec(spec)
sys.modules["eval_voice_analyze"] = va
spec.loader.exec_module(va)


def row(cond="c1", wake_exp=1, wake_det=1, expected="date_time", parsed="date_time", exact=1):
    return {"condition": cond, "wake_expected": str(wake_exp),
            "wake_detected": str(wake_det), "expected_intent": expected,
            "parsed_intent": parsed, "exact_wake_and_intent": str(exact)}


def test_wake_and_intent_rates():
    rows = [
        row(),                                              # wake ok, intent ok
        row(wake_det=0, parsed="", exact=0),                # wake miss
        row(parsed="help", exact=0),                        # wake ok, intent wrong
        row(wake_exp=0, wake_det=0, expected="", parsed="", exact=1),  # control clean
        row(wake_exp=0, wake_det=1, expected="", parsed="unknown", exact=0),  # false wake
    ]
    t = va.aggregate(rows)["c1"]
    assert abs(t["wake_rate"] - 2 / 3) < 1e-9
    assert abs(t["false_wake_rate"] - 1 / 2) < 1e-9
    assert abs(t["intent_acc_given_wake"] - 1 / 2) < 1e-9
    assert t["n_trials"] == 5


def test_conditions_isolated():
    rows = [row(cond="a"), row(cond="b", wake_det=0, parsed="", exact=0)]
    t = va.aggregate(rows)
    assert t["a"]["wake_rate"] == 1.0 and t["b"]["wake_rate"] == 0.0


# --- microphone pinning (RES-004) -------------------------------------------------
# The grid measures distance from the SP300U, so which mic recorded a cell is part of
# the method. These cover the resolver that replaced sounddevice's default input.

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "eval_voice_capture",
    Path(__file__).resolve().parent.parent / "scripts" / "eval_voice_capture.py")
_capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_capture)
resolve_input_device = _capture.resolve_input_device

DEVICES = [
    {"name": "SPEAKPHONE SP300U: USB Audio (hw:2,0)", "max_input_channels": 1},
    {"name": "HD Pro Webcam C920: USB Audio (hw:3,0)", "max_input_channels": 2},
    {"name": "Some Speaker", "max_input_channels": 0},
    {"name": "default", "max_input_channels": 128},
]


def test_resolves_the_speakerphone_by_name():
    idx, name = resolve_input_device("SP300U", DEVICES)
    assert idx == 0 and "SP300U" in name


def test_name_match_is_case_insensitive():
    assert resolve_input_device("sp300u", DEVICES)[0] == 0


def test_card_number_change_does_not_break_the_match():
    """The SP300U was card 3 in July and card 2 on 2026-08-24; name matching survives that."""
    moved = [dict(d) for d in DEVICES]
    moved[0]["name"] = "SPEAKPHONE SP300U: USB Audio (hw:5,0)"
    assert resolve_input_device("SP300U", moved)[0] == 0


def test_resolves_an_explicit_index():
    assert resolve_input_device("1", DEVICES) == (1, DEVICES[1]["name"])


def test_output_only_device_is_not_selectable():
    import pytest
    with pytest.raises(ValueError):
        resolve_input_device("2", DEVICES)


def test_missing_device_raises_and_lists_alternatives():
    import pytest
    with pytest.raises(ValueError) as e:
        resolve_input_device("Blue Yeti", DEVICES)
    assert "SP300U" in str(e.value)  # tells the operator what IS available


def test_ambiguous_match_refuses_rather_than_guessing():
    import pytest
    dupes = DEVICES + [{"name": "SP300U clone", "max_input_channels": 1}]
    with pytest.raises(ValueError) as e:
        resolve_input_device("SP300U", dupes)
    assert "matches 2 devices" in str(e.value)
