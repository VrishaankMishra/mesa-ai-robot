"""Tests for camera control locking (VIS-011).

No camera and no cv2: a fake capture records every ``set`` in order, and a stub cv2
module supplies the property constants. The ordering is the part that matters — a UVC
driver ignores a manual value while its ``auto`` companion is still on.
"""

import pytest

from mesa.vision.camera import AUTO_EXPOSURE_MANUAL, configure_capture


class FakeCv2:
    CAP_PROP_AUTOFOCUS = 39
    CAP_PROP_FOCUS = 28
    CAP_PROP_AUTO_WB = 44
    CAP_PROP_WB_TEMPERATURE = 45
    CAP_PROP_AUTO_EXPOSURE = 21
    CAP_PROP_EXPOSURE = 15


class FakeCapture:
    """Records set() calls; get() returns whatever was last set (driver echo)."""

    def __init__(self, initial=None):
        self.values = dict(initial or {})
        self.calls = []

    def set(self, prop, value):
        self.calls.append((prop, value))
        self.values[prop] = value
        return True

    def get(self, prop):
        return self.values.get(prop, 0.0)


def _cfg(**camera):
    camera.setdefault("enabled", True)
    return {"vision": {"camera": camera}}


def test_disabled_is_a_no_op():
    cap = FakeCapture()
    assert configure_capture(cap, _cfg(enabled=False), cv2_module=FakeCv2) == {}
    assert cap.calls == []


def test_absent_config_is_a_no_op():
    cap = FakeCapture()
    assert configure_capture(cap, {}, cv2_module=FakeCv2) == {}
    assert cap.calls == []


def test_autofocus_is_disabled_before_focus_is_set():
    cap = FakeCapture()
    configure_capture(cap, _cfg(focus=40), cv2_module=FakeCv2)
    props = [p for p, _ in cap.calls]
    assert props.index(FakeCv2.CAP_PROP_AUTOFOCUS) < props.index(FakeCv2.CAP_PROP_FOCUS)
    assert (FakeCv2.CAP_PROP_AUTOFOCUS, 0) in cap.calls
    assert (FakeCv2.CAP_PROP_FOCUS, 40.0) in cap.calls


def test_auto_wb_is_disabled_before_temperature_is_set():
    cap = FakeCapture()
    configure_capture(cap, _cfg(white_balance=4000), cv2_module=FakeCv2)
    props = [p for p, _ in cap.calls]
    assert props.index(FakeCv2.CAP_PROP_AUTO_WB) < props.index(FakeCv2.CAP_PROP_WB_TEMPERATURE)
    assert (FakeCv2.CAP_PROP_WB_TEMPERATURE, 4000.0) in cap.calls


def test_exposure_switches_to_manual_before_pinning_the_value():
    cap = FakeCapture()
    configure_capture(cap, _cfg(exposure=250), cv2_module=FakeCv2)
    props = [p for p, _ in cap.calls]
    assert props.index(FakeCv2.CAP_PROP_AUTO_EXPOSURE) < props.index(FakeCv2.CAP_PROP_EXPOSURE)
    assert (FakeCv2.CAP_PROP_AUTO_EXPOSURE, AUTO_EXPOSURE_MANUAL) in cap.calls
    assert (FakeCv2.CAP_PROP_EXPOSURE, 250.0) in cap.calls


def test_null_value_freezes_what_auto_chose():
    # The camera settled on 312 before we touched it; that is what should be pinned.
    cap = FakeCapture({FakeCv2.CAP_PROP_EXPOSURE: 312.0})
    configure_capture(cap, _cfg(exposure=None), cv2_module=FakeCv2)
    assert (FakeCv2.CAP_PROP_EXPOSURE, 312.0) in cap.calls


def test_locks_are_independent():
    cap = FakeCapture()
    applied = configure_capture(
        cap, _cfg(lock_focus=False, lock_white_balance=False, exposure=100),
        cv2_module=FakeCv2)
    assert "exposure" in applied
    assert "focus" not in applied and "white_balance" not in applied
    assert FakeCv2.CAP_PROP_AUTOFOCUS not in [p for p, _ in cap.calls]


def test_unknown_property_is_survivable():
    """A backend without CAP_PROP_WB_TEMPERATURE must not take the whole lock down."""

    class Partial(FakeCv2):
        CAP_PROP_WB_TEMPERATURE = None

    cap = FakeCapture()
    applied = configure_capture(cap, _cfg(white_balance=4000, exposure=100),
                                cv2_module=Partial)
    assert applied["white_balance"] is None
    assert (FakeCv2.CAP_PROP_EXPOSURE, 100.0) in cap.calls


def test_a_refusing_driver_does_not_raise():
    class Refusing(FakeCapture):
        def set(self, prop, value):
            raise RuntimeError("driver said no")

    applied = configure_capture(Refusing(), _cfg(exposure=100), cv2_module=FakeCv2)
    assert applied  # still reports readbacks rather than blowing up the vision worker
