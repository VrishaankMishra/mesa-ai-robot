"""Tests for the pure detection-classification logic (VIS-006)."""

from mesa.vision.detector import UNKNOWN_LABEL, Detection, classify_detections

NAMES = {0: "tylenol", 1: "vitamin_d", 2: "ibuprofen"}
BOX = (10, 10, 50, 80)


def test_confident_detection_keeps_label():
    out = classify_detections([(0, 0.92, BOX)], NAMES, conf_threshold=0.5)
    assert out == [Detection("tylenol", 0.92, BOX)]
    assert not out[0].is_unknown


def test_low_confidence_becomes_unknown():
    out = classify_detections([(1, 0.30, BOX)], NAMES, conf_threshold=0.5)
    assert out[0].label == UNKNOWN_LABEL
    assert out[0].is_unknown


def test_confidence_exactly_at_threshold_is_kept():
    # >= threshold is confident; only strictly-below is unknown.
    out = classify_detections([(2, 0.50, BOX)], NAMES, conf_threshold=0.5)
    assert out[0].label == "ibuprofen"


def test_out_of_range_class_id_is_unknown():
    out = classify_detections([(99, 0.99, BOX)], NAMES, conf_threshold=0.5)
    assert out[0].is_unknown


def test_names_as_list_supported():
    out = classify_detections([(1, 0.8, BOX)], ["a", "b", "c"], conf_threshold=0.5)
    assert out[0].label == "b"


def test_mixed_batch():
    raw = [(0, 0.95, BOX), (1, 0.10, BOX), (5, 0.99, BOX)]
    labels = [d.label for d in classify_detections(raw, NAMES, 0.5)]
    assert labels == ["tylenol", UNKNOWN_LABEL, UNKNOWN_LABEL]
