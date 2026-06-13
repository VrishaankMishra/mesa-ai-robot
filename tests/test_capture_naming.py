"""Tests for the capture filename slug logic (VIS-002).

Only the pure naming helper is tested; the camera loop needs hardware + opencv.
"""

import argparse
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("capture", REPO_ROOT / "scripts" / "capture.py")
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)


def _ns(bottle, lighting, angle, distance):
    return argparse.Namespace(bottle=bottle, lighting=lighting, angle=angle, distance=distance)


def test_slug_basic():
    assert capture.slug(_ns("tylenol", "bright", 0, 0.5)) == "tylenol__bright__a0__d05"


def test_slug_distance_padding():
    assert capture.slug(_ns("aspirin", "dim", 30, 1.5)) == "aspirin__dim__a30__d15"
    assert capture.slug(_ns("aspirin", "dim", 30, 1.0)) == "aspirin__dim__a30__d10"


def test_slug_negative_angle_is_filename_safe():
    # Negative angles must not produce a leading '-' in the filename stem.
    assert capture.slug(_ns("calcium", "mixed", -30, 0.5)) == "calcium__mixed__an30__d05"
