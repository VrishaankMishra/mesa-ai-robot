"""Tests for mesa.config — loading and dotted-key lookup."""

import pytest

from mesa.config import get, load_config


def test_load_default_config_has_sections():
    cfg = load_config()
    for section in ("vision", "detection", "pose", "compliance", "escalation", "voice"):
        assert section in cfg, f"missing config section: {section}"


def test_get_dotted_key():
    cfg = load_config()
    assert get(cfg, "pose.lying_trigger_seconds") == 30
    assert get(cfg, "detection.confidence_threshold") == 0.5


def test_get_missing_key_returns_default():
    cfg = load_config()
    assert get(cfg, "nope.not.here") is None
    assert get(cfg, "nope.not.here", default=42) == 42


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.yaml")
