"""Raspberry Pi GPIO backend tests with a mocked lgpio module."""

import pytest

from nectar.actuators.protocols import get_default_gpio_backend
from nectar.actuators.raspberry_gpio import BOARD_TO_BCM, RaspberryPiGPIOBackend

pytestmark = pytest.mark.control


class FakeLGPIOError(Exception):
    pass


class FakeLGPIO:
    error = FakeLGPIOError
    SET_PULL_UP = 1
    SET_PULL_DOWN = 2
    SET_PULL_NONE = 3

    def __init__(self, failing_chips=()):
        self.failing_chips = set(failing_chips)
        self.open_calls = []
        self.claimed_outputs = []
        self.claimed_inputs = []
        self.read_calls = []
        self.write_calls = []
        self.freed = []
        self.closed = []
        self.pwm_calls = []

    def gpiochip_open(self, chip_id):
        self.open_calls.append(chip_id)
        if chip_id in self.failing_chips:
            raise FakeLGPIOError(f"gpiochip{chip_id} unavailable")
        return chip_id + 100

    def gpio_claim_output(self, handle, pin, initial):
        self.claimed_outputs.append((handle, pin, initial))

    def gpio_claim_input(self, handle, pin, flags):
        self.claimed_inputs.append((handle, pin, flags))

    def gpio_read(self, handle, pin):
        self.read_calls.append((handle, pin))
        return 1

    def gpio_write(self, handle, pin, value):
        self.write_calls.append((handle, pin, value))

    def gpio_free(self, handle, pin):
        self.freed.append((handle, pin))

    def gpiochip_close(self, handle):
        self.closed.append(handle)

    def tx_pwm(self, handle, pin, frequency_hz, duty_cycle):
        self.pwm_calls.append((handle, pin, frequency_hz, duty_cycle))


def _make_backend(monkeypatch, gpio):
    monkeypatch.setattr(
        "nectar.actuators.raspberry_gpio.import_module", lambda _name: gpio
    )
    return RaspberryPiGPIOBackend()


def test_board_to_bcm_contains_all_gpio_positions_on_40_pin_header():
    assert BOARD_TO_BCM == {
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


def test_backend_uses_board_translation_for_gpio_and_input_pulls(monkeypatch):
    gpio = FakeLGPIO()
    backend = _make_backend(monkeypatch, gpio)

    backend.setup((11, 13), "BOARD")
    backend.output((11, 13), (1, 0))
    backend.setup_input(7, "BOARD", "UP")
    backend.setup_input(8, "BOARD", "DOWN")
    backend.setup_input(10, "BOARD", None)

    assert gpio.claimed_outputs == [(104, 17, 0), (104, 27, 0)]
    assert gpio.write_calls == [(104, 17, 1), (104, 27, 0)]
    assert gpio.claimed_inputs == [
        (104, 4, gpio.SET_PULL_UP),
        (104, 14, gpio.SET_PULL_DOWN),
        (104, 15, gpio.SET_PULL_NONE),
    ]
    assert backend.input(7) == 1
    assert gpio.read_calls == [(104, 4)]
    with pytest.raises(ValueError, match="not a GPIO pin"):
        backend.setup((1,), "BOARD")
    with pytest.raises(ValueError, match="mix"):
        backend.setup((17,), "BCM")


def test_backend_falls_back_to_gpiochip_zero_and_frees_pins(monkeypatch):
    gpio = FakeLGPIO(failing_chips=(4,))
    backend = _make_backend(monkeypatch, gpio)

    assert gpio.open_calls == [4, 0]
    backend.setup((2,), "BCM")
    backend.setup_input(3, "BCM", None)
    backend.cleanup((2,))

    assert gpio.freed == [(100, 2)]
    assert gpio.closed == []
    backend.cleanup((3,))
    assert gpio.freed == [(100, 2), (100, 3)]
    assert gpio.closed == [100]


def test_explicit_chip_does_not_try_fallback(monkeypatch):
    gpio = FakeLGPIO(failing_chips=(2,))
    monkeypatch.setattr(
        "nectar.actuators.raspberry_gpio.import_module", lambda _name: gpio
    )

    with pytest.raises(RuntimeError, match="gpiochip2"):
        RaspberryPiGPIOBackend(chip=2)
    assert gpio.open_calls == [2]


def test_pwm_uses_bcm_translation_and_cleanup_stops_channel(monkeypatch):
    gpio = FakeLGPIO()
    backend = _make_backend(monkeypatch, gpio)

    backend.setup_pwm(32, "BOARD", 50.0)
    backend.set_duty_cycle(32, 7.5)
    backend.cleanup((32,))

    assert gpio.claimed_outputs == [(104, 12, 0)]
    assert gpio.pwm_calls == [
        (104, 12, 50.0, 0.0),
        (104, 12, 50.0, 7.5),
        (104, 12, 0, 0),
    ]
    assert gpio.freed == [(104, 12)]
    assert gpio.closed == [104]


def test_default_backend_uses_device_tree_model(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        "pathlib.Path.read_text",
        lambda _path, **_kwargs: "Raspberry Pi 5 Model B Rev 1.0",
    )
    monkeypatch.setattr(
        "nectar.actuators.raspberry_gpio.RaspberryPiGPIOBackend",
        lambda: sentinel,
    )

    assert get_default_gpio_backend() is sentinel


def test_pwm_rejects_invalid_duty_cycle(monkeypatch):
    gpio = FakeLGPIO()
    backend = _make_backend(monkeypatch, gpio)
    backend.setup_pwm(18, "BCM", 50.0)

    with pytest.raises(ValueError, match="between 0 and 100"):
        backend.set_duty_cycle(18, 101)
