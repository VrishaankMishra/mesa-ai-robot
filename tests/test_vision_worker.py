"""Tests for the pure detection→presence mapping used by the vision worker (ENG-004)."""

from mesa.vision.detector import Detection
from mesa.vision.worker import presence_map


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
