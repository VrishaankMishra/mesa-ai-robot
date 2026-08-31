"""Camera control locking (VIS-011).

The C920 ships with auto-exposure, auto-white-balance and continuous autofocus all on.
That is the right default for a video call and the wrong one here: MeSA watches a fixed
medication station, so every automatic adjustment is the camera silently changing the
very thing the detector was trained on. Measured 2026-08-24 on the Pi — ``auto_exposure``
in Aperture Priority, ``white_balance_automatic`` on, ``focus_automatic_continuous`` on,
and ``exposure_dynamic_framerate`` on (the camera is free to drop FPS in dim light, which
is exactly where posture already struggles).

The domain-shift study argues for engineering the operating envelope rather than chasing
invariance with data; this is that argument applied to MeSA's own lens. Lock the controls
at the station, under the lighting the demo will actually run in.

Pure glue over ``cv2.VideoCapture.set``: the capture object and the ``cv2`` module are
both injectable, so the ordering logic is unit-testable with no camera attached.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from mesa.config import get

# V4L2/UVC semantics as exposed by OpenCV's V4L2 backend: auto-exposure is a *menu*,
# not a bool — 1 = Manual Mode, 3 = Aperture Priority (auto). Autofocus and auto-WB
# are plain 0/1 bools.
AUTO_EXPOSURE_MANUAL = 1.0
AUTO_EXPOSURE_AUTO = 3.0


def _set(cap, prop: int | None, value: float) -> bool:
    if prop is None:
        return False
    try:
        return bool(cap.set(prop, value))
    except Exception:  # a backend that doesn't know the property
        return False


def _prop(cv2_module, name: str) -> int | None:
    return getattr(cv2_module, name, None)


def configure_capture(cap, cfg: dict, cv2_module=None) -> dict[str, Any]:
    """Apply ``vision.camera`` locks to an already-open capture.

    Each lock is independent, so a camera that refuses one still gets the others. Where a
    value is left unset in config the control is locked at whatever the camera's own
    automatic pass last chose — read back *before* switching to manual, which is the
    honest way to freeze "what it looks like right now" at the station.

    Returns a ``{setting: value}`` map read back from the driver after the writes, for
    logging. An empty dict means ``vision.camera`` is absent or disabled.
    """
    if cv2_module is None:  # pragma: no cover - real camera path
        import cv2 as cv2_module

    if not get(cfg, "vision.camera.enabled", False):
        return {}

    applied: dict[str, Any] = {}

    # --- focus: autofocus OFF before the fixed value, or the driver ignores it.
    if get(cfg, "vision.camera.lock_focus", True):
        autofocus = _prop(cv2_module, "CAP_PROP_AUTOFOCUS")
        focus_prop = _prop(cv2_module, "CAP_PROP_FOCUS")
        current = cap.get(focus_prop) if focus_prop is not None else None
        _set(cap, autofocus, 0)
        target = get(cfg, "vision.camera.focus", None)
        _set(cap, focus_prop, float(target if target is not None else (current or 0)))
        applied["focus"] = cap.get(focus_prop) if focus_prop is not None else None
        applied["autofocus"] = cap.get(autofocus) if autofocus is not None else None

    # --- white balance: auto OFF before the temperature.
    if get(cfg, "vision.camera.lock_white_balance", True):
        auto_wb = _prop(cv2_module, "CAP_PROP_AUTO_WB")
        wb_prop = _prop(cv2_module, "CAP_PROP_WB_TEMPERATURE")
        current = cap.get(wb_prop) if wb_prop is not None else None
        _set(cap, auto_wb, 0)
        target = get(cfg, "vision.camera.white_balance", None)
        if target is not None or current:
            _set(cap, wb_prop, float(target if target is not None else current))
        applied["white_balance"] = cap.get(wb_prop) if wb_prop is not None else None
        applied["auto_wb"] = cap.get(auto_wb) if auto_wb is not None else None

    # --- exposure: read what auto chose, THEN switch to manual and pin it.
    if get(cfg, "vision.camera.lock_exposure", True):
        auto_exp = _prop(cv2_module, "CAP_PROP_AUTO_EXPOSURE")
        exp_prop = _prop(cv2_module, "CAP_PROP_EXPOSURE")
        current = cap.get(exp_prop) if exp_prop is not None else None
        _set(cap, auto_exp, AUTO_EXPOSURE_MANUAL)
        target = get(cfg, "vision.camera.exposure", None)
        if target is not None or current:
            _set(cap, exp_prop, float(target if target is not None else current))
        applied["exposure"] = cap.get(exp_prop) if exp_prop is not None else None
        applied["auto_exposure"] = cap.get(auto_exp) if auto_exp is not None else None

    return applied


def disable_dynamic_framerate(device: str = "/dev/video0") -> bool:
    """Turn off ``exposure_dynamic_framerate`` (V4L2 only; no OpenCV property exists).

    With it on, the camera lengthens exposure by dropping frames — in dim light the
    C920 can fall well below the 30 FPS the pipeline assumes, and ``pose.min_fps`` is 5.
    Returns True if the control was set. Silently a no-op wherever ``v4l2-ctl`` isn't
    installed (laptop dev, CI), so callers can call it unconditionally.
    """
    if not shutil.which("v4l2-ctl"):
        return False
    result = subprocess.run(
        ["v4l2-ctl", "-d", device, "--set-ctrl", "exposure_dynamic_framerate=0"],
        capture_output=True, check=False,
    )
    return result.returncode == 0
