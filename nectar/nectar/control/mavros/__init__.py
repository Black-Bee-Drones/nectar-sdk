"""MAVROS drone control."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.control.mavros.setpoint_config import SetpointNavConfig

_LAZY_ATTRS = {
    "GPSUtils": "nectar.control.mavros.gps_utils",
    "MavrosDrone": "nectar.control.mavros.drone",
    "MavrosNavigator": "nectar.control.mavros.navigator",
    "TargetComputer": "nectar.control.mavros.target_computer",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from nectar.control.mavros.drone import MavrosDrone
    from nectar.control.mavros.gps_utils import GPSUtils
    from nectar.control.mavros.navigator import MavrosNavigator
    from nectar.control.mavros.target_computer import TargetComputer


__all__ = [
    "MavrosDrone",
    "MavrosNavigator",
    "GPSUtils",
    "SetpointNavConfig",
    "TargetComputer",
]
