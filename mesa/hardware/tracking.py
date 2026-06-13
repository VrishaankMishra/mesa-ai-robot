"""Pan/tilt person-tracking control law (HW-005).

Pure proportional control: given the detected person's center (normalized image coords,
(0.5, 0.5) = frame center), produce new servo angles that nudge the camera to re-center
the person. A deadzone prevents jitter; a max step per update prevents oscillation; angles
are clamped to the servo's safe range. No hardware here — this is the math, fully testable.
The actual servo writes live in mesa.hardware.servos.
"""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class PanTiltState:
    pan: float
    tilt: float


class PanTiltController:
    def __init__(
        self,
        pan_limits: tuple[float, float] = (0.0, 180.0),
        tilt_limits: tuple[float, float] = (0.0, 180.0),
        pan_center: float = 90.0,
        tilt_center: float = 90.0,
        gain: float = 40.0,
        deadzone: float = 0.05,
        max_step: float = 4.0,
        invert_pan: bool = False,
        invert_tilt: bool = False,
    ):
        self.pan_limits = pan_limits
        self.tilt_limits = tilt_limits
        self.gain = gain
        self.deadzone = deadzone
        self.max_step = max_step
        self.invert_pan = invert_pan
        self.invert_tilt = invert_tilt
        self.pan = pan_center
        self.tilt = tilt_center

    def _step(self, error: float, invert: bool) -> float:
        if abs(error) < self.deadzone:
            return 0.0  # deadzone: ignore tiny errors so the head doesn't twitch
        delta = _clamp(self.gain * error, -self.max_step, self.max_step)
        return -delta if invert else delta

    def update(self, person_center: Point | None) -> PanTiltState:
        """Advance toward centering the person. ``None`` (no detection) holds position."""
        if person_center is None:
            return PanTiltState(self.pan, self.tilt)
        ex = person_center[0] - 0.5   # +: person right of center
        ey = person_center[1] - 0.5   # +: person below center
        self.pan = _clamp(self.pan + self._step(ex, self.invert_pan), *self.pan_limits)
        self.tilt = _clamp(self.tilt + self._step(ey, self.invert_tilt), *self.tilt_limits)
        return PanTiltState(self.pan, self.tilt)

    def center(self) -> PanTiltState:
        self.pan = sum(self.pan_limits) / 2.0
        self.tilt = sum(self.tilt_limits) / 2.0
        return PanTiltState(self.pan, self.tilt)
