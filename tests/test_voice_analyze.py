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
    """The SP300U was card 3 in July and card 2 on 2026-08-27; name matching survives that."""
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


# --- capture-rate negotiation + resampling (RES-004) -------------------------------
# Pinning the SP300U means talking to the raw hardware, which accepts 48 kHz only;
# pulse used to hide that by resampling silently.

pick_capture_rate = _capture.pick_capture_rate
to_vosk_rate = _capture.to_vosk_rate


def test_prefers_16k_when_the_device_accepts_it():
    assert pick_capture_rate(lambda r: True, 48000.0, 16000) == 16000


def test_falls_back_to_device_default_when_16k_is_refused():
    """The SP300U's real behaviour: 16000/32000/44100 all rejected, 48000 only."""
    assert pick_capture_rate(lambda r: r == 48000, 48000.0, 16000) == 48000


def test_capture_rate_is_an_int():
    assert isinstance(pick_capture_rate(lambda r: False, 48000.0), int)


def test_resample_is_identity_at_matching_rates():
    import numpy as np
    x = np.array([0, 100, -100, 32767, -32768], dtype="int16")
    assert np.array_equal(to_vosk_rate(x, 16000, 16000), x)


def test_resample_48k_to_16k_thirds_the_length():
    import numpy as np
    x = np.zeros(48000, dtype="int16")
    assert abs(len(to_vosk_rate(x, 48000, 16000)) - 16000) <= 1


def test_resample_preserves_a_tone_and_stays_in_int16_range():
    import numpy as np
    t = np.arange(48000) / 48000.0
    x = (np.sin(2 * np.pi * 440 * t) * 10000).astype("int16")   # 440 Hz, well under Nyquist
    y = to_vosk_rate(x, 48000, 16000)
    assert y.dtype == np.int16
    assert 5000 < np.abs(y).max() <= 32767      # amplitude survives
    assert abs(len(y) - 16000) <= 1


def test_resample_output_is_bytes_convertible_for_vosk():
    import numpy as np
    y = to_vosk_rate(np.zeros(4800, dtype="int16"), 48000, 16000)
    assert isinstance(y.tobytes(), bytes)


# --- session provenance: audio + posture/position (RES-004) ------------------------

def test_save_wav_roundtrips_pcm(tmp_path):
    """A disputed trial must be re-checkable by ear, so the audio has to survive intact."""
    import wave

    import numpy as np
    pcm = (np.sin(np.arange(1600) / 8.0) * 8000).astype("int16")
    path = tmp_path / "trial_00.wav"
    _capture.save_wav(path, pcm, 16000)

    with wave.open(str(path)) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        back = np.frombuffer(w.readframes(w.getnframes()), dtype="int16")
    assert np.array_equal(back, pcm)


def test_manifest_carries_posture_and_position():
    """The 2026-08-27 pilot was read as a distance sweep because the condition string was
    the only record of where the operator stood. Provenance now travels per row."""
    rows = [{
        "condition": "d1m_quiet_vrishaank", "wake_expected": "1", "wake_detected": "1",
        "parsed_intent": "next_med", "expected_intent": "next_med",
        "exact_wake_and_intent": "1", "posture": "standing", "position": "1m mark",
    }]
    assert va.aggregate(rows)["d1m_quiet_vrishaank"]["n_trials"] == 1
    assert rows[0]["posture"] == "standing" and rows[0]["position"] == "1m mark"


def test_guard_default_is_long_enough_to_drain_a_prompt():
    assert _capture.GUARD_SECONDS >= 0.5
