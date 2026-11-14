"""Servo and other pulse-width-controlled actuator support."""

from dataclasses import dataclass
from math import isfinite

from nectar.actuators.protocols import PWMBackend, get_default_gpio_backend


@dataclass(frozen=True)
class ServoConfig:
    """PWM pin and pulse-to-angle calibration for a hobby servo."""

    pin: int = 32
    gpio_mode: str = "BOARD"
    frequency_hz: float = 50.0
    min_angle: float = 0.0
    max_angle: float = 180.0
    min_pulse_us: float = 500.0
    max_pulse_us: float = 2500.0
    initial_angle: float | None = None

    def __post_init__(self) -> None:
        if self.gpio_mode not in ("BOARD", "BCM"):
            raise ValueError("gpio_mode must be 'BOARD' or 'BCM'")
        if not isfinite(self.frequency_hz) or self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be finite and positive")
        if not isfinite(self.min_angle) or not isfinite(self.max_angle):
            raise ValueError("angle limits must be finite")
        if self.min_angle >= self.max_angle:
            raise ValueError("min_angle must be less than max_angle")
        if (
            not isfinite(self.min_pulse_us)
            or not isfinite(self.max_pulse_us)
            or not 0 < self.min_pulse_us < self.max_pulse_us
            or self.max_pulse_us >= 1_000_000.0 / self.frequency_hz
        ):
            raise ValueError("pulse limits must be positive, increasing, and shorter than the period")
        if self.initial_angle is not None and (
            not isfinite(self.initial_angle)
            or not self.min_angle <= self.initial_angle <= self.max_angle
        ):
            raise ValueError("initial_angle must be finite and within the configured angle limits")


class ServoMotor:
    """Control a servo using PWM and an injected hardware backend."""

    def __init__(
        self,
        config: ServoConfig = ServoConfig(),
        backend: PWMBackend | None = None,
    ) -> None:
        if backend is None:
            backend = get_default_gpio_backend()
        self.config = config
        self._backend = backend
        self._closed = False
        self._current_angle: float | None = None
        self._backend.setup_pwm(config.pin, config.gpio_mode, config.frequency_hz)
        if config.initial_angle is not None:
            try:
                self.set_angle(config.initial_angle)
            finally:
                if self._current_angle is None:
                    self.close()

    @property
    def current_angle(self) -> float | None:
        """Return the last angle command, or ``None`` after direct pulse control."""
        return self._current_angle

    def set_angle(self, angle: float, clamp: bool = False) -> float:
        """Set a target angle, optionally clamping it to the configured limits."""
        self._ensure_open()
        if not isfinite(angle):
            raise ValueError("angle must be finite")
        if clamp:
            angle = min(max(angle, self.config.min_angle), self.config.max_angle)
        elif not self.config.min_angle <= angle <= self.config.max_angle:
            raise ValueError("angle is outside the configured limits")
        angle_span = self.config.max_angle - self.config.min_angle
        pulse_span = self.config.max_pulse_us - self.config.min_pulse_us
        pulse_us = self.config.min_pulse_us + (
            (angle - self.config.min_angle) / angle_span * pulse_span
        )
        self._backend.set_duty_cycle(
            self.config.pin, pulse_us * self.config.frequency_hz / 10_000.0
        )
        self._current_angle = angle
        return angle

    def set_pulse_width_us(self, pulse_us: float) -> None:
        """Set a pulse width directly, within the configured safety limits."""
        self._ensure_open()
        if not isfinite(pulse_us) or not self.config.min_pulse_us <= pulse_us <= self.config.max_pulse_us:
            raise ValueError("pulse_us must be finite and within the configured pulse limits")
        duty_cycle = pulse_us * self.config.frequency_hz / 10_000.0
        self._backend.set_duty_cycle(self.config.pin, duty_cycle)
        self._current_angle = None

    def detach(self) -> None:
        """Stop the PWM pulse while keeping the channel configured."""
        self._ensure_open()
        self._backend.set_duty_cycle(self.config.pin, 0.0)

    def close(self) -> None:
        """Stop PWM and release the configured GPIO pin."""
        if self._closed:
            return
        self._closed = True
        try:
            self._backend.stop_pwm(self.config.pin)
        finally:
            self._backend.cleanup((self.config.pin,))

    def __enter__(self) -> "ServoMotor":
        self._ensure_open()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("servo motor is closed")
