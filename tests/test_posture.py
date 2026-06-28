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


def test_low_visibility_legs_are_ignored():
    # Knee geometry alone would say "sitting", but the legs are barely visible
    # (the real Pi failure mode: off-screen legs at ~2% visibility). Must not
    # fabricate sitting — fall back to standing.
    vis = {k: 0.9 for k in SITTING}
    for leg in ("left_knee", "left_ankle", "right_knee", "right_ankle"):
        vis[leg] = 0.05
    assert classify_posture(SITTING, visibility=vis, min_visibility=0.5) == Posture.STANDING


def test_visible_legs_still_detect_sitting():
    vis = {k: 0.9 for k in SITTING}
    assert classify_posture(SITTING, visibility=vis, min_visibility=0.5) == Posture.SITTING


def test_visibility_omitted_keeps_original_behavior():
    # Backward-compat: no visibility info => trust the landmarks as before.
    assert classify_posture(SITTING) == Posture.SITTING
    assert classify_posture(STANDING) == Posture.STANDING


def test_lying_detected_regardless_of_leg_visibility():
    vis = {k: 0.01 for k in LYING}  # legs invisible, but torso says lying
    assert classify_posture(LYING, visibility=vis, min_visibility=0.5) == Posture.LYING


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


def test_monitor_tolerates_brief_detection_dropout():
    # MediaPipe blips to UNKNOWN mid-lie (real Pi failure mode); the spell must
    # NOT reset, so the timer still accumulates and fires.
    m = PostureMonitor(lying_trigger_seconds=10.0, gap_grace_seconds=5.0)
    m.update(Posture.LYING, 0.0)
    m.update(Posture.UNKNOWN, 3.0)            # 3s gap < grace -> hold
    m.update(Posture.LYING, 6.0)
    m.update(Posture.UNKNOWN, 8.0)            # gap from last-lying(6) = 2 -> hold
    event = m.update(Posture.LYING, 10.0)     # spell started at 0 -> elapsed 10 -> fire
    assert isinstance(event, FallEvent)


def test_monitor_resets_after_long_dropout():
    # A long UNKNOWN gap means the person likely left view -> the spell resets.
    m = PostureMonitor(lying_trigger_seconds=10.0, gap_grace_seconds=5.0)
    m.update(Posture.LYING, 0.0)
    assert m.update(Posture.UNKNOWN, 7.0) is None   # gap 7 > grace 5 -> reset
    m.update(Posture.LYING, 8.0)                     # fresh spell at 8
    assert m.update(Posture.LYING, 12.0) is None     # 4s in (would be 12s if not reset)
    assert m.update(Posture.LYING, 18.0) is not None # 10s into the new spell -> fire


def test_monitor_upright_still_resets_through_grace():
    # A *confirmed* upright posture resets immediately, even within the grace.
    m = PostureMonitor(lying_trigger_seconds=10.0, gap_grace_seconds=5.0)
    m.update(Posture.LYING, 0.0)
    m.update(Posture.STANDING, 2.0)           # got up -> reset now
    assert m.update(Posture.LYING, 9.0) is None   # new spell from 9, only ~0s in


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
