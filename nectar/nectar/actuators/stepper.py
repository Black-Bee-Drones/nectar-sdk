"""Stepper motor control independent of the underlying GPIO library."""

from dataclasses import dataclass
from math import ceil, floor, isfinite
from time import sleep

from nectar.actuators.exceptions import HomingError
from nectar.actuators.protocols import GPIOBackend, get_default_gpio_backend

HALF_STEP_SEQUENCE = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)


@dataclass(frozen=True)
class StepperConfig:
    """Hardware and motor parameters for a four-coil stepper."""

    pins: tuple[int, ...] = (11, 13, 15, 16)
    steps_per_revolution: int = 4096
    gpio_mode: str = "BOARD"
    sequence: tuple[tuple[int, ...], ...] = HALF_STEP_SEQUENCE
    home_pin: int | None = None
    home_active_state: int = 0
    home_pull: str | None = "UP"
    home_direction: int = -1
    max_homing_degrees: float = 360.0

    def __post_init__(self) -> None:
        if not self.pins or len(set(self.pins)) != len(self.pins):
            raise ValueError("pins must be a non-empty sequence of unique pin numbers")
        if self.steps_per_revolution <= 0:
            raise ValueError("steps_per_revolution must be positive")
        if self.gpio_mode not in ("BOARD", "BCM"):
            raise ValueError("gpio_mode must be 'BOARD' or 'BCM'")
        if len(self.sequence) < 2 or any(
            len(phase) != len(self.pins) or any(value not in (0, 1) for value in phase)
            for phase in self.sequence
        ):
            raise ValueError("sequence phases must contain one 0/1 value for each pin")
        if self.home_pin is not None and self.home_pin in self.pins:
            raise ValueError("home_pin must not overlap a motor output pin")
        if self.home_active_state not in (0, 1):
            raise ValueError("home_active_state must be 0 or 1")
        if self.home_pull not in (None, "UP", "DOWN"):
            raise ValueError("home_pull must be 'UP', 'DOWN', or None")
        if self.home_direction not in (-1, 1):
            raise ValueError("home_direction must be -1 or 1")
        if not isfinite(self.max_homing_degrees) or self.max_homing_degrees <= 0:
            raise ValueError("max_homing_degrees must be finite and positive")


class StepperMotor:
    """Drive a stepper motor through an injected GPIO backend.

    ``steps_per_revolution`` should reflect the motor, gearbox, and driver
    microstepping configuration. ``velocity_rpm`` is output-shaft RPM.
    """

    def __init__(
        self,
        config: StepperConfig = StepperConfig(),
        backend: GPIOBackend | None = None,
    ) -> None:
        if backend is None:
            backend = get_default_gpio_backend()
        self.config = config
        self._backend = backend
        self._step_index = 0
        self._position_steps = 0
        self._is_homed = False
        self._closed = False
        self._backend.setup(config.pins, config.gpio_mode)
        if config.home_pin is not None:
            self._backend.setup_input(config.home_pin, config.gpio_mode, config.home_pull)

    def rotate_by_degrees(self, degrees: float, velocity_rpm: float = 1.0) -> int:
        """Rotate by a relative angle at a positive output-shaft RPM.

        Returns the number of half-steps issued. Small angles may round to zero
        steps; negative angles rotate in reverse.
        """
        if not isfinite(degrees):
            raise ValueError("degrees must be finite")
        if not isfinite(velocity_rpm) or velocity_rpm <= 0:
            raise ValueError("velocity_rpm must be finite and positive")
        steps = round(abs(degrees) * self.config.steps_per_revolution / 360.0)
        direction = 1 if degrees >= 0 else -1
        interval = 60.0 / (velocity_rpm * self.config.steps_per_revolution)
        return self._run_steps(steps, direction, interval)

    def rotate_by_velocity(self, velocity_rpm: float, duration_s: float) -> int:
        """Rotate at signed output-shaft RPM for a finite duration.

        Positive RPM rotates forward and negative RPM reverses. Returns the
        number of half-steps issued; very short durations may round to zero.
        """
        if not isfinite(velocity_rpm) or velocity_rpm == 0:
            raise ValueError("velocity_rpm must be finite and non-zero")
        if not isfinite(duration_s) or duration_s <= 0:
            raise ValueError("duration_s must be finite and positive")
        steps_per_second = (
            abs(velocity_rpm) * self.config.steps_per_revolution / 60.0
        )
        steps = round(steps_per_second * duration_s)
        interval = 1.0 / steps_per_second
        direction = 1 if velocity_rpm > 0 else -1
        return self._run_steps(steps, direction, interval)

    @property
    def position_degrees(self) -> float:
        """Return the estimated relative output-shaft position."""
        return self._position_steps * 360.0 / self.config.steps_per_revolution

    @property
    def is_homed(self) -> bool:
        """Whether the limit-switch reference position has been established."""
        return self._is_homed

    def home(self, velocity_rpm: float = 2.0, backoff_degrees: float = 5.0) -> int:
        """Seek, release, and re-latch the configured home limit switch.

        Each switch-seeking stage is bounded by ``max_homing_degrees``. The
        returned value is the total number of half-steps issued in all stages.
        """
        self._ensure_open()
        if self.config.home_pin is None:
            raise HomingError("home_pin is not configured")
        if not isfinite(velocity_rpm) or velocity_rpm <= 0:
            raise ValueError("velocity_rpm must be finite and positive")
        if not isfinite(backoff_degrees) or backoff_degrees < 0:
            raise ValueError("backoff_degrees must be finite and non-negative")

        self._is_homed = False
        max_steps = floor(
            self.config.max_homing_degrees * self.config.steps_per_revolution / 360.0
        )
        backoff_steps = ceil(
            backoff_degrees * self.config.steps_per_revolution / 360.0
        )
        direction = self.config.home_direction
        interval = 60.0 / (velocity_rpm * self.config.steps_per_revolution)

        try:
            fast_seek = self._seek_home_state(
                self.config.home_active_state, direction, max_steps, interval, "fast seek"
            )
            switch_release = self._seek_home_state(
                1 - self.config.home_active_state,
                -direction,
                max_steps,
                interval,
                "switch back-off",
            )
            self._run_steps_energized(backoff_steps, -direction, interval)
            if backoff_steps:
                sleep(interval)
            if self._backend.input(self.config.home_pin) != 1 - self.config.home_active_state:
                raise HomingError("limit switch reactivated during switch back-off")
            slow_latch = self._seek_home_state(
                self.config.home_active_state,
                direction,
                max_steps,
                interval * 4.0,
                "slow latch",
            )
            self._position_steps = 0
            self._is_homed = True
            return fast_seek + switch_release + backoff_steps + slow_latch
        finally:
            self._write_low()

    def rotate_to_degrees(self, target_degrees: float, velocity_rpm: float = 1.0) -> int:
        """Move to a relative angle measured from the last successful home."""
        self._ensure_open()
        if not self._is_homed:
            raise RuntimeError("stepper motor must be homed before absolute movement")
        return self.rotate_by_degrees(target_degrees - self.position_degrees, velocity_rpm)

    def close(self) -> None:
        """De-energize the coils and release GPIO resources."""
        if self._closed:
            return
        self._closed = True
        pins = self.config.pins
        if self.config.home_pin is not None:
            pins = (*pins, self.config.home_pin)
        try:
            self._write_low()
        finally:
            self._backend.cleanup(pins)

    def __enter__(self) -> "StepperMotor":
        self._ensure_open()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    def _run_steps(self, steps: int, direction: int, interval: float) -> int:
        self._ensure_open()
        try:
            return self._run_steps_energized(steps, direction, interval)
        finally:
            self._write_low()

    def _run_steps_energized(self, steps: int, direction: int, interval: float) -> int:
        for step in range(steps):
            self._step_index = (self._step_index + direction) % len(self.config.sequence)
            self._position_steps += direction
            self._backend.output(self.config.pins, self.config.sequence[self._step_index])
            if step + 1 < steps:
                sleep(interval)
        return steps

    def _seek_home_state(
        self,
        state: int,
        direction: int,
        max_steps: int,
        interval: float,
        stage: str,
    ) -> int:
        pin = self.config.home_pin
        if pin is None:
            raise HomingError("home_pin is not configured")
        for steps in range(max_steps + 1):
            if self._backend.input(pin) == state:
                return steps
            if steps == max_steps:
                break
            self._run_steps_energized(1, direction, interval)
            sleep(interval)
        raise HomingError(
            f"limit switch did not reach state {state} during {stage} "
            f"within {self.config.max_homing_degrees:g} degrees"
        )

    def _write_low(self) -> None:
        self._backend.output(self.config.pins, (0,) * len(self.config.pins))

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("stepper motor is closed")
