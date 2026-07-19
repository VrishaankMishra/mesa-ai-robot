"""Tests for the pure rotation-fallback mapping (VIS-009 robustness)."""

from mesa.vision.pose_estimator import LANDMARK_IDS, posture_from_rotated
from mesa.vision.posture import Posture


def test_upright_in_rotated_frame_means_lying():
    assert posture_from_rotated(Posture.STANDING) == Posture.LYING


def test_sitting_in_rotated_frame_means_lying_with_bent_knees():
    assert posture_from_rotated(Posture.SITTING) == Posture.LYING


def test_lying_in_rotated_frame_is_not_trusted():
    # "Lying" in a rotated frame would mean upright in reality — but the primary
    # pass should have caught that, so don't fabricate a posture from it.
    assert posture_from_rotated(Posture.LYING) == Posture.UNKNOWN


def test_unknown_stays_unknown():
    assert posture_from_rotated(Posture.UNKNOWN) == Posture.UNKNOWN


def test_landmark_map_covers_classifier_needs():
    needed = {"left_shoulder", "right_shoulder", "left_hip", "right_hip",
              "left_knee", "right_knee", "left_ankle", "right_ankle"}
    assert needed == set(LANDMARK_IDS)


def test_180_preserves_lying_only():
    from mesa.vision.pose_estimator import posture_from_180
    assert posture_from_180(Posture.LYING) == Posture.LYING
    assert posture_from_180(Posture.STANDING) == Posture.UNKNOWN
    assert posture_from_180(Posture.SITTING) == Posture.UNKNOWN
    assert posture_from_180(Posture.UNKNOWN) == Posture.UNKNOWN
