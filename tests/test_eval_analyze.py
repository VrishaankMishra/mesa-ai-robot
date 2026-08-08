"""Tests for the domain-shift evaluation scoring rules (paper data integrity)."""

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "eval_analyze", Path(__file__).resolve().parent.parent / "scripts" / "eval_analyze.py"
)
ea = importlib.util.module_from_spec(spec)
sys.modules["eval_analyze"] = ea
spec.loader.exec_module(ea)

KNOWN = {"advil", "melatonin", "omeprazole", "vitamin_d3"}


class TestScoreSingle:
    def test_correct_top_detection(self):
        assert ea.score_single([("advil", 0.8)], "advil", 0.45)

    def test_wrong_label_fails(self):
        assert not ea.score_single([("melatonin", 0.8)], "advil", 0.45)

    def test_below_threshold_fails(self):
        assert not ea.score_single([("advil", 0.3)], "advil", 0.45)

    def test_tray_is_ignored_not_counted_as_answer(self):
        # tray at high conf must neither satisfy nor block the real match.
        assert ea.score_single([("tray", 0.9), ("advil", 0.6)], "advil", 0.45)
        assert not ea.score_single([("tray", 0.9)], "advil", 0.45)

    def test_top_confidence_wins_among_real_dets(self):
        dets = [("advil", 0.5), ("melatonin", 0.7)]
        assert not ea.score_single(dets, "advil", 0.45)
        assert ea.score_single(dets, "melatonin", 0.45)


class TestScoreUnknown:
    def test_no_detections_is_correct(self):
        assert ea.score_unknown([], KNOWN, 0.45)

    def test_low_conf_known_label_is_correct(self):
        # Below threshold means the pipeline reports "unknown" — right answer.
        assert ea.score_unknown([("advil", 0.3)], KNOWN, 0.45)

    def test_confident_misidentification_is_wrong(self):
        assert not ea.score_unknown([("advil", 0.6)], KNOWN, 0.45)

    def test_tray_detection_alone_is_correct(self):
        assert ea.score_unknown([("tray", 0.8)], KNOWN, 0.45)


class TestScoreGroup:
    def test_full_recall(self):
        dets = [(m, 0.6) for m in KNOWN]
        assert ea.score_group(dets, KNOWN, 0.45) == 1.0

    def test_partial_recall(self):
        assert ea.score_group([("advil", 0.6)], KNOWN, 0.45) == 0.25

    def test_tray_not_counted(self):
        assert ea.score_group([("tray", 0.9)], KNOWN, 0.45) == 0.0


def test_best_conf_for_picks_ground_truth_match():
    dets = [("advil", 0.42), ("advil", 0.61), ("melatonin", 0.9)]
    assert ea.best_conf_for(dets, "advil") == 0.61
    assert ea.best_conf_for(dets, "vitamin_d3") == 0.0
