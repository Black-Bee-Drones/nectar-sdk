"""Raspberry Pi GPIO and PWM backend using the ``lgpio`` Linux GPIO interface."""

from importlib import import_module
from math import isfinite
from typing import Sequence


BOARD_TO_BCM = {
    3: 2,
    5: 3,
    7: 4,
    8: 14,
    10: 15,
    11: 17,
    12: 18,
    13: 27,
    15: 22,
    16: 23,
    18: 24,
    19: 10,
    21: 9,
    22: 25,
    23: 11,
    24: 8,
    26: 7,
    27: 0,
    28: 1,
    29: 5,
    31: 6,
    32: 12,
    33: 13,
    35: 19,
    36: 16,
    37: 26,
    38: 20,
    40: 21,
}


class RaspberryPiGPIOBackend:
    """Implement actuator GPIO/PWM operations with ``lgpio``.

    ``lgpio`` uses BCM GPIO numbering. ``BOARD`` pin numbers are translated
    using the standard Raspberry Pi 40-pin header layout.
    """

    def __init__(self, chip: int | None = None) -> None:
        self._lgpio = import_module("lgpio")
        self._handle: int | None = None
        self._chip_id: int | None = None
        self._mode: str | None = None
        self._claimed_pins: set[int] = set()
        self._pin_map: dict[int, int] = {}
        self._pwm_freqs: dict[int, float] = {}

        candidates = (4, 0) if chip is None else (chip,)
        failures: list[tuple[int, Exception]] = []
        for chip_id in candidates:
            try:
                handle = self._lgpio.gpiochip_open(chip_id)
            except self._lgpio.error as exc:
                failures.append((chip_id, exc))
                continue
            if handle < 0:
                failures.append((chip_id, RuntimeError("gpiochip_open returned an invalid handle")))
                continue
            self._handle = handle
            self._chip_id = chip_id
            break
        else:
            attempted = ", ".join(f"gpiochip{chip_id}" for chip_id, _ in failures)
            error = RuntimeError(f"Unable to open Raspberry Pi GPIO chip ({attempted})")
            if failures:
                raise error from failures[-1][1]
            raise error

    def setup(self, pins: Sequence[int], mode: str) -> None:
        for pin in pins:
            bcm_pin = self._resolve_pin(pin, mode)
            self._lgpio.gpio_claim_output(self._handle, bcm_pin, 0)
            self._claimed_pins.add(bcm_pin)

    def setup_input(self, pin: int, mode: str, pull: str | None = "UP") -> None:
        pull_flags = {
            "UP": self._lgpio.SET_PULL_UP,
            "DOWN": self._lgpio.SET_PULL_DOWN,
            None: self._lgpio.SET_PULL_NONE,
        }
        try:
            flags = pull_flags[pull]
        except KeyError as exc:
            raise ValueError("pull must be 'UP', 'DOWN', or None") from exc
        bcm_pin = self._resolve_pin(pin, mode)
        self._lgpio.gpio_claim_input(self._handle, bcm_pin, flags)
        self._claimed_pins.add(bcm_pin)

    def input(self, pin: int) -> int:
        bcm_pin = self._resolve_pin(pin)
        return int(self._lgpio.gpio_read(self._handle, bcm_pin))

    def output(self, pins: Sequence[int], values: Sequence[int]) -> None:
        if len(pins) != len(values):
            raise ValueError("pins and values must have the same length")
        for pin, value in zip(pins, values):
            bcm_pin = self._resolve_pin(pin)
            self._lgpio.gpio_write(self._handle, bcm_pin, int(value))

    def cleanup(self, pins: Sequence[int]) -> None:
        for pin in pins:
            bcm_pin = self._pin_map.get(pin)
            if bcm_pin is None or bcm_pin not in self._claimed_pins:
                continue
            self._stop_pwm_bcm(bcm_pin)
            self._lgpio.gpio_free(self._handle, bcm_pin)
            self._claimed_pins.remove(bcm_pin)
            del self._pin_map[pin]
        if not self._claimed_pins and self._handle is not None:
            self._lgpio.gpiochip_close(self._handle)
            self._handle = None

    def setup_pwm(self, pin: int, mode: str, frequency_hz: float) -> None:
        if not isfinite(frequency_hz) or frequency_hz <= 0:
            raise ValueError("frequency_hz must be finite and positive")
        bcm_pin = self._resolve_pin(pin, mode)
        self._lgpio.gpio_claim_output(self._handle, bcm_pin, 0)
        self._claimed_pins.add(bcm_pin)
        self._lgpio.tx_pwm(self._handle, bcm_pin, frequency_hz, 0.0)
        self._pwm_freqs[bcm_pin] = frequency_hz

    def set_duty_cycle(self, pin: int, duty_cycle_percent: float) -> None:
        if not isfinite(duty_cycle_percent) or not 0.0 <= duty_cycle_percent <= 100.0:
            raise ValueError("duty_cycle_percent must be finite and between 0 and 100")
        bcm_pin = self._resolve_pin(pin)
        try:
            frequency_hz = self._pwm_freqs[bcm_pin]
        except KeyError as exc:
            raise RuntimeError(f"PWM is not configured for pin {pin}") from exc
        self._lgpio.tx_pwm(self._handle, bcm_pin, frequency_hz, duty_cycle_percent)

    def stop_pwm(self, pin: int) -> None:
        bcm_pin = self._pin_map.get(pin)
        if bcm_pin is not None:
            self._stop_pwm_bcm(bcm_pin)

    def _stop_pwm_bcm(self, bcm_pin: int) -> None:
        if bcm_pin not in self._pwm_freqs:
            return
        self._lgpio.tx_pwm(self._handle, bcm_pin, 0, 0)
        del self._pwm_freqs[bcm_pin]

    def _resolve_pin(self, pin: int, mode: str | None = None) -> int:
        self._ensure_open()
        if mode is not None:
            if mode not in ("BOARD", "BCM"):
                raise ValueError("mode must be 'BOARD' or 'BCM'")
            if self._mode is not None and self._mode != mode:
                raise ValueError("one RaspberryPiGPIOBackend cannot mix BOARD and BCM modes")
            self._mode = mode
        if self._mode is None:
            raise RuntimeError("GPIO numbering mode has not been configured")
        if pin in self._pin_map:
            return self._pin_map[pin]
        if self._mode == "BCM":
            bcm_pin = pin
        else:
            try:
                bcm_pin = BOARD_TO_BCM[pin]
            except KeyError as exc:
                raise ValueError(f"BOARD pin {pin} is not a GPIO pin on the 40-pin header") from exc
        self._pin_map[pin] = bcm_pin
        return bcm_pin

    def _ensure_open(self) -> None:
        if self._handle is None:
            raise RuntimeError("Raspberry Pi GPIO backend is closed")
