"""Tests for the pure detection→presence mapping used by the vision worker (ENG-004)."""

from mesa.vision.detector import Detection
from mesa.vision.worker import UnknownBottleGate, presence_map, unknown_boxes


def det(label: str, conf: float = 0.9) -> Detection:
    return Detection(label=label, confidence=conf, box=(0, 0, 10, 10))


def test_detected_known_med_is_present():
    result = presence_map([det("tylenol")], {"tylenol", "aspirin"})
    assert result == {"tylenol": True, "aspirin": False}


def test_no_detections_marks_all_known_meds_absent():
    assert presence_map([], {"tylenol", "aspirin"}) == {"tylenol": False, "aspirin": False}


def test_unknown_label_is_not_evidence_for_any_med():
    # An "unknown" (low-confidence / wrong-medication) box must not mark anything present.
    result = presence_map([det("unknown")], {"tylenol"})
    assert result == {"tylenol": False}


def test_detection_of_unregistered_bottle_is_ignored():
    result = presence_map([det("mystery_brand")], {"tylenol"})
    assert result == {"tylenol": False}


def test_empty_known_meds_yields_empty_map():
    assert presence_map([det("tylenol")], set()) == {}


# --- unknown_boxes: which "unknown" detections count as a foreign bottle ---


def test_unknown_box_alone_counts():
    assert unknown_boxes([det("unknown", 0.3)]) == [det("unknown", 0.3)]


def test_unknown_box_overlapping_known_bottle_is_a_duplicate_not_a_foreign_bottle():
    # Class-aware NMS can emit a weaker second guess on the same bottle; it shares the box.
    known = Detection(label="advil", confidence=0.6, box=(100, 100, 200, 300))
    dup = Detection(label="unknown", confidence=0.2, box=(104, 98, 198, 296))
    assert unknown_boxes([known, dup]) == []


def test_unknown_box_beside_known_bottle_still_counts():
    known = Detection(label="advil", confidence=0.6, box=(100, 100, 200, 300))
    foreign = Detection(label="unknown", confidence=0.3, box=(300, 100, 400, 300))
    assert unknown_boxes([known, foreign]) == [foreign]


def test_known_boxes_never_count_as_unknown():
    assert unknown_boxes([det("advil"), det("melatonin")]) == []


def test_unknown_below_min_confidence_is_noise_not_a_bottle():
    # The detector predicts at confidence 0; a patterned rug or a lamp base yields
    # permanent 0.08-0.24 "unknown" boxes that must not become "wrong medication".
    noise, bottle = det("unknown", 0.12), det("unknown", 0.31)
    assert unknown_boxes([noise, bottle], min_confidence=0.25) == [bottle]
    assert unknown_boxes([noise], min_confidence=0.25) == []


def test_min_confidence_defaults_to_zero_keeping_old_behaviour():
    assert unknown_boxes([det("unknown", 0.05)]) == [det("unknown", 0.05)]


def test_unknown_box_off_the_table_is_furniture():
    # Same confidence band as a foreign bottle; only the centre's position differs.
    on = Detection(label="unknown", confidence=0.2, box=(300, 300, 340, 360))
    off = Detection(label="unknown", confidence=0.2, box=(50, 50, 90, 110))
    assert unknown_boxes([on, off], roi=(160, 250, 640, 480)) == [on]
    assert unknown_boxes([on, off]) == [on, off]   # no roi: old behaviour


# --- UnknownBottleGate: debounce + rate limit with simulated time ---


def test_gate_waits_for_debounce_before_firing():
    gate = UnknownBottleGate(debounce_seconds=3.0, repeat_seconds=30.0)
    assert gate.update(True, 0.0) is False
    assert gate.update(True, 1.0) is False
    assert gate.update(True, 2.9) is False
    assert gate.update(True, 3.0) is True


def test_brief_unknown_flicker_does_not_fire():
    # A hand passing over a bottle: unknown for 1 s, gone, unknown again for 1 s.
    gate = UnknownBottleGate(debounce_seconds=3.0, repeat_seconds=30.0)
    assert gate.update(True, 0.0) is False
    assert gate.update(True, 1.0) is False
    assert gate.update(False, 1.5) is False
    assert gate.update(True, 2.0) is False
    assert gate.update(True, 3.0) is False   # only 1 s since the unknown reappeared
    assert gate.update(True, 4.9) is False
    assert gate.update(True, 5.0) is True    # 3 s of continuous unknown since t=2


def test_gate_repeats_at_most_once_per_repeat_window_while_unknown_stays():
    gate = UnknownBottleGate(debounce_seconds=3.0, repeat_seconds=30.0)
    fired = [t for t in range(0, 100) if gate.update(True, float(t))]
    assert fired == [3, 33, 63, 93]


def test_gate_rate_limit_survives_bottle_leaving_and_returning():
    # Removing and re-placing the bottle inside the window must not double-speak.
    gate = UnknownBottleGate(debounce_seconds=3.0, repeat_seconds=30.0)
    for t in range(0, 4):
        gate.update(True, float(t))          # fires at t=3
    assert gate.update(False, 5.0) is False
    fired = [t for t in range(6, 40) if gate.update(True, float(t))]
    assert fired == [33]


def test_gate_fires_again_after_long_absence():
    gate = UnknownBottleGate(debounce_seconds=3.0, repeat_seconds=30.0)
    for t in range(0, 4):
        gate.update(True, float(t))          # fires at t=3
    gate.update(False, 10.0)
    assert [t for t in range(100, 104) if gate.update(True, float(t))] == [103]
