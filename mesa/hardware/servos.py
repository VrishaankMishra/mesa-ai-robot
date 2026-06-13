"""Servo driver plug module (HW-004).

Defines the ``ServoDriver`` interface the rest of the code depends on, a real PCA9685
implementation (Adafruit libs imported lazily, Pi-only), and a NullServoDriver fallback so
laptop dev/tests run with no hardware. ``get_servo_driver()`` returns the real driver if
the libraries import, otherwise the null one.

PanTiltHead combines the pure :class:`PanTiltController` with whatever driver is present.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mesa.hardware.tracking import PanTiltController, PanTiltState, Point


@runtime_checkable
class ServoDriver(Protocol):
    def set_angle(self, channel: int, angle: float) -> None: ...
    def close(self) -> None: ...


class NullServoDriver:
    """No-op driver for laptop dev. Optionally prints the commanded angles."""

    def __init__(self, log: bool = False):
        self.log = log
        self.last: dict[int, float] = {}

    def set_angle(self, channel: int, angle: float) -> None:
        self.last[channel] = angle
        if self.log:
            print(f"[servo] ch{channel} -> {angle:.1f}deg")

    def close(self) -> None:
        pass


class PCA9685ServoDriver:  # pragma: no cover - requires Pi + I2C hardware
    """Real driver over I2C via a PCA9685 16-channel PWM board."""

    def __init__(self, frequency: int = 50, min_pulse: int = 500, max_pulse: int = 2500):
        import board
        import busio
        from adafruit_pca9685 import PCA9685
        from adafruit_motor import servo as _servo

        i2c = busio.I2C(board.SCL, board.SDA)
        self._pca = PCA9685(i2c)
        self._pca.frequency = frequency
        self._servo_mod = _servo
        self._min_pulse = min_pulse
        self._max_pulse = max_pulse
        self._servos: dict[int, object] = {}

    def _servo_for(self, channel: int):
        if channel not in self._servos:
            self._servos[channel] = self._servo_mod.Servo(
                self._pca.channels[channel],
                min_pulse=self._min_pulse,
                max_pulse=self._max_pulse,
            )
        return self._servos[channel]

    def set_angle(self, channel: int, angle: float) -> None:
        self._servo_for(channel).angle = max(0.0, min(180.0, angle))

    def close(self) -> None:
        self._pca.deinit()


def get_servo_driver(prefer_hardware: bool = True, **kwargs) -> ServoDriver:
    """Return a real PCA9685 driver if its libraries import, else a NullServoDriver."""
    if prefer_hardware:
        try:
            return PCA9685ServoDriver(**kwargs)
        except Exception:  # ImportError on laptop, I2C errors if board missing
            pass
    return NullServoDriver(**({} if prefer_hardware else kwargs))


class PanTiltHead:
    """Tie the tracking controller to a servo driver. ``track()`` is safe with any driver."""

    def __init__(
        self,
        driver: ServoDriver,
        controller: PanTiltController | None = None,
        pan_channel: int = 0,
        tilt_channel: int = 1,
    ):
        self.driver = driver
        self.controller = controller or PanTiltController()
        self.pan_channel = pan_channel
        self.tilt_channel = tilt_channel

    def track(self, person_center: Point | None) -> PanTiltState:
        state = self.controller.update(person_center)
        self.driver.set_angle(self.pan_channel, state.pan)
        self.driver.set_angle(self.tilt_channel, state.tilt)
        return state

    def center(self) -> PanTiltState:
        state = self.controller.center()
        self.driver.set_angle(self.pan_channel, state.pan)
        self.driver.set_angle(self.tilt_channel, state.tilt)
        return state

    def close(self) -> None:
        self.driver.close()
