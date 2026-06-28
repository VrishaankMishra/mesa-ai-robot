"""Tests for posture classification (VIS-009) and the fall trigger (VIS-010).

Landmarks are normalized image coords with y increasing downward (MediaPipe convention).
"""

from mesa.vision.posture import (
    FallEvent,
    Posture,
    PostureMonitor,
    PostureSmoother,
    classify_posture,
)

# A person standing upright: shoulders high, hips mid, knees lower, ankles lowest,
# all roughly in a vertical line.
STANDING = {
    "left_shoulder": (0.45, 0.20), "right_shoulder": (0.55, 0.20),
    "left_hip": (0.46, 0.50), "right_hip": (0.54, 0.50),
    "left_knee": (0.46, 0.72), "right_knee": (0.54, 0.72),
    "left_ankle": (0.46, 0.95), "right_ankle": (0.54, 0.95),
}

# Sitting: torso still upright, but thighs horizontal -> bent knees.
SITTING = {
    "left_shoulder": (0.45, 0.25), "right_shoulder": (0.55, 0.25),
    "left_hip": (0.46, 0.55), "right_hip": (0.54, 0.55),
    "left_knee": (0.62, 0.56), "right_knee": (0.70, 0.56),
    "left_ankle": (0.62, 0.80), "right_ankle": (0.70, 0.80),
}

# Lying: body horizontal -> shoulders and hips at similar height, spread in x.
LYING = {
    "left_shoulder": (0.25, 0.55), "right_shoulder": (0.25, 0.62),
    "left_hip": (0.60, 0.56), "right_hip": (0.60, 0.63),
    "left_knee": (0.80, 0.57), "right_knee": (0.80, 0.64),
    "left_ankle": (0.95, 0.58), "right_ankle": (0.95, 0.65),
}


def test_classify_standing():
    assert classify_posture(STANDING) == Posture.STANDING


def test_classify_sitting():
    assert classify_posture(SITTING) == Posture.SITTING


def test_classify_lying():
    assert classify_posture(LYING) == Posture.LYING


def test_missing_torso_landmarks_is_unknown():
    assert classify_posture({"left_knee": (0.5, 0.5)}) == Posture.UNKNOWN


def test_upright_without_legs_defaults_standing():
    torso_only = {
        "left_shoulder": (0.45, 0.20), "right_shoulder": (0.55, 0.20),
        "left_hip": (0.46, 0.50), "right_hip": (0.54, 0.50),
    }
    assert classify_posture(torso_only) == Posture.STANDING


def test_monitor_fires_after_threshold():
    m = PostureMonitor(lying_trigger_seconds=30.0)
    assert m.update(Posture.LYING, 0.0) is None
    assert m.update(Posture.LYING, 29.0) is None
    event = m.update(Posture.LYING, 30.0)
    assert isinstance(event, FallEvent)
    assert event.lying_seconds >= 30.0


def test_monitor_fires_only_once_per_spell():
    m = PostureMonitor(lying_trigger_seconds=10.0)
    m.update(Posture.LYING, 0.0)
    assert m.update(Posture.LYING, 10.0) is not None
    assert m.update(Posture.LYING, 15.0) is None  # already fired


def test_monitor_resets_when_no_longer_lying():
    m = PostureMonitor(lying_trigger_seconds=10.0)
    m.update(Posture.LYING, 0.0)
    assert m.update(Posture.LYING, 10.0) is not None
    m.update(Posture.STANDING, 11.0)          # reset
    m.update(Posture.LYING, 12.0)             # new spell
    assert m.update(Posture.LYING, 22.0) is not None


# --- PostureSmoother (de-flicker) -------------------------------------------

def test_smoother_locks_onto_steady_posture():
    s = PostureSmoother(window=5)
    for _ in range(5):
        out = s.update(Posture.STANDING)
    assert out == Posture.STANDING
    assert s.current == Posture.STANDING


def test_smoother_ignores_single_frame_flicker():
    s = PostureSmoother(window=5)
    for _ in range(5):
        s.update(Posture.STANDING)
    # one stray sitting frame must not flip the reported posture
    assert s.update(Posture.SITTING) == Posture.STANDING


def test_smoother_switches_on_sustained_change():
    s = PostureSmoother(window=5)
    for _ in range(5):
        s.update(Posture.STANDING)
    out = None
    for _ in range(5):
        out = s.update(Posture.SITTING)
    assert out == Posture.SITTING


def test_smoother_suppresses_brief_lying_spike():
    # The live test showed ~4 stray 'lying' frames among hundreds; those must
    # NOT register as lying.
    s = PostureSmoother(window=9)
    for _ in range(9):
        s.update(Posture.STANDING)
    s.update(Posture.LYING)
    s.update(Posture.LYING)
    assert s.current != Posture.LYING


def test_smoother_holds_steady_through_borderline_chatter():
    # A ~50/50 standing/sitting boundary (the real-world flicker) must not flip
    # the label once locked — this is the hysteresis the live test motivated.
    import itertools
    s = PostureSmoother(window=15, switch_fraction=0.6)
    for _ in range(15):
        s.update(Posture.STANDING)
    assert s.current == Posture.STANDING
    flips = 0
    prev = s.current
    seq = itertools.cycle([Posture.SITTING, Posture.STANDING])
    for _ in range(40):
        out = s.update(next(seq))
        if out != prev:
            flips += 1
            prev = out
    assert flips == 0


def test_smoother_reset():
    s = PostureSmoother(window=5)
    for _ in range(5):
        s.update(Posture.SITTING)
    s.reset()
    assert s.current == Posture.UNKNOWN


def test_smoothed_lying_survives_flicker_and_fires_monitor():
    """Integration: raw labels flicker but lying dominates -> smoothed stays
    lying -> the fall timer accumulates and fires (which raw flicker would have
    prevented by constantly resetting the monitor)."""
    s = PostureSmoother(window=5)
    m = PostureMonitor(lying_trigger_seconds=10.0)
    raw_seq = [Posture.LYING, Posture.LYING, Posture.STANDING, Posture.LYING, Posture.LYING]
    fired = None
    for i in range(13):
        smoothed = s.update(raw_seq[i % len(raw_seq)])
        ev = m.update(smoothed, float(i))
        if ev is not None:
            fired = ev
    assert isinstance(fired, FallEvent)
