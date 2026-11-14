"""Jetson.GPIO implementation of the actuator GPIO and PWM backends."""

from importlib import import_module
from typing import Any, Sequence


class JetsonGPIOBackend:
    """Configure and drive pins with the optional ``Jetson.GPIO`` package."""

    def __init__(self) -> None:
        self._gpio = import_module("Jetson.GPIO")
        self._pwm_channels: dict[int, Any] = {}

    def setup(self, pins: Sequence[int], mode: str) -> None:
        gpio_mode = getattr(self._gpio, mode)
        self._gpio.setmode(gpio_mode)
        for pin in pins:
            self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)

    def output(self, pins: Sequence[int], values: Sequence[int]) -> None:
        self._gpio.output(list(pins), list(values))

    def setup_input(self, pin: int, mode: str, pull: str | None = "UP") -> None:
        self._gpio.setmode(getattr(self._gpio, mode))
        pull_modes = {
            "UP": self._gpio.PUD_UP,
            "DOWN": self._gpio.PUD_DOWN,
            None: self._gpio.PUD_OFF,
        }
        try:
            pull_mode = pull_modes[pull]
        except KeyError as exc:
            raise ValueError("pull must be 'UP', 'DOWN', or None") from exc
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=pull_mode)

    def input(self, pin: int) -> int:
        return int(self._gpio.input(pin))

    def setup_pwm(self, pin: int, mode: str, frequency_hz: float) -> None:
        self._gpio.setmode(getattr(self._gpio, mode))
        self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.LOW)
        pwm = self._gpio.PWM(pin, frequency_hz)
        pwm.start(0.0)
        self._pwm_channels[pin] = pwm

    def set_duty_cycle(self, pin: int, duty_cycle_percent: float) -> None:
        self._pwm_channels[pin].ChangeDutyCycle(duty_cycle_percent)

    def stop_pwm(self, pin: int) -> None:
        pwm = self._pwm_channels.pop(pin, None)
        if pwm is not None:
            pwm.stop()

    def cleanup(self, pins: Sequence[int]) -> None:
        for pin in pins:
            self.stop_pwm(pin)
        self._gpio.cleanup(list(pins))
