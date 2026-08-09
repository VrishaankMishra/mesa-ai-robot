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
