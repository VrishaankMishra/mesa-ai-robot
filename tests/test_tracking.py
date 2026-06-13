"""Tests for the pan/tilt tracking control law (HW-005)."""

from mesa.hardware.tracking import PanTiltController


def test_centered_person_no_movement():
    c = PanTiltController()
    state = c.update((0.5, 0.5))
    assert state.pan == 90.0 and state.tilt == 90.0


def test_deadzone_ignores_tiny_error():
    c = PanTiltController(deadzone=0.05)
    state = c.update((0.53, 0.48))  # within deadzone
    assert state.pan == 90.0 and state.tilt == 90.0


def test_person_right_pans_right():
    c = PanTiltController(gain=40, max_step=4)
    state = c.update((0.9, 0.5))    # far right
    assert state.pan > 90.0


def test_step_is_clamped():
    c = PanTiltController(gain=1000, max_step=4)
    state = c.update((1.0, 0.5))    # huge error
    assert state.pan == 94.0        # exactly one max_step, not gain*error


def test_no_detection_holds_position():
    c = PanTiltController()
    c.update((0.9, 0.9))
    held = c.pan, c.tilt
    state = c.update(None)
    assert (state.pan, state.tilt) == held


def test_angles_clamped_to_limits():
    c = PanTiltController(pan_limits=(0, 180), pan_center=178, max_step=4, gain=40)
    state = c.update((1.0, 0.5))
    assert state.pan == 180.0       # clamped, not 182


def test_invert_pan_reverses_direction():
    normal = PanTiltController(invert_pan=False).update((0.9, 0.5)).pan
    inverted = PanTiltController(invert_pan=True).update((0.9, 0.5)).pan
    assert normal > 90.0 and inverted < 90.0


def test_converges_toward_center_over_time():
    c = PanTiltController(gain=40, max_step=4)
    # Person stays slightly right; pan should keep increasing across updates.
    p1 = c.update((0.7, 0.5)).pan
    p2 = c.update((0.7, 0.5)).pan
    assert p2 > p1
