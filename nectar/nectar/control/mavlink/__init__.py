"""Direct MAVLink (pymavlink) control path."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "MavlinkConnection": "nectar.control.mavlink.connection",
    "PymavlinkTransport": "nectar.control.mavlink.transport",
    "MavlinkDrone": "nectar.control.mavlink.drone",
    "VisionPoseBridge": "nectar.control.mavlink.vision_bridge",
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
    from nectar.control.mavlink.connection import MavlinkConnection
    from nectar.control.mavlink.drone import MavlinkDrone
    from nectar.control.mavlink.transport import PymavlinkTransport
    from nectar.control.mavlink.vision_bridge import VisionPoseBridge


__all__ = [
    "MavlinkConnection",
    "PymavlinkTransport",
    "MavlinkDrone",
    "VisionPoseBridge",
]
