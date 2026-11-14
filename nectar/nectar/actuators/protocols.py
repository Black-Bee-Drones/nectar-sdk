"""Hardware backend protocols shared by actuator drivers."""

from importlib.util import find_spec
from pathlib import Path
from typing import Protocol, Sequence


class GPIOBackend(Protocol):
    """Digital GPIO operations required by actuator drivers."""

    def setup(self, pins: Sequence[int], mode: str) -> None: ...

    def setup_input(self, pin: int, mode: str, pull: str | None = "UP") -> None: ...

    def input(self, pin: int) -> int: ...

    def output(self, pins: Sequence[int], values: Sequence[int]) -> None: ...

    def cleanup(self, pins: Sequence[int]) -> None: ...


class PWMBackend(Protocol):
    """PWM operations required by servo and other PWM actuator drivers."""

    def setup_pwm(self, pin: int, mode: str, frequency_hz: float) -> None: ...

    def set_duty_cycle(self, pin: int, duty_cycle_percent: float) -> None: ...

    def stop_pwm(self, pin: int) -> None: ...

    def cleanup(self, pins: Sequence[int]) -> None: ...


class GPIOPWMBackend(GPIOBackend, PWMBackend, Protocol):
    """Backend implementing both digital GPIO and PWM operations."""


def get_default_gpio_backend() -> GPIOPWMBackend:
    """Create the GPIO backend matching the current board.

    Device-tree model information is preferred. On hosts without that file,
    installed backend packages are used as a fallback.
    """
    try:
        model = Path("/proc/device-tree/model").read_text(
            encoding="utf-8", errors="replace"
        ).strip("\x00\n ").lower()
    except OSError:
        model = ""

    if "jetson" in model or "nvidia" in model:
        from nectar.actuators.jetson_gpio import JetsonGPIOBackend

        return JetsonGPIOBackend()
    if "raspberry pi" in model or "raspberrypi" in model:
        from nectar.actuators.raspberry_gpio import RaspberryPiGPIOBackend

        return RaspberryPiGPIOBackend()

    if _module_available("Jetson.GPIO"):
        from nectar.actuators.jetson_gpio import JetsonGPIOBackend

        return JetsonGPIOBackend()
    if _module_available("lgpio"):
        from nectar.actuators.raspberry_gpio import RaspberryPiGPIOBackend

        return RaspberryPiGPIOBackend()
    raise RuntimeError(
        "Unable to detect a supported GPIO backend. Install Jetson.GPIO or lgpio, "
        "or pass an explicit GPIO backend."
    )


def _module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False
