"""PX4 firmware specialization of the shared vehicle core."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "Px4Drone": "nectar.control.px4.drone",
    "Px4MavrosDrone": "nectar.control.px4.mavros_drone",
    "Px4MavlinkDrone": "nectar.control.px4.mavlink_drone",
    "Px4ModeCodec": "nectar.control.px4.mavlink_drone",
    "Px4DdsDrone": "nectar.control.px4.dds_drone",
    "Px4DdsTransport": "nectar.control.px4.dds_transport",
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
    from nectar.control.px4.dds_drone import Px4DdsDrone
    from nectar.control.px4.dds_transport import Px4DdsTransport
    from nectar.control.px4.drone import Px4Drone
    from nectar.control.px4.mavlink_drone import Px4MavlinkDrone, Px4ModeCodec
    from nectar.control.px4.mavros_drone import Px4MavrosDrone


__all__ = [
    "Px4Drone",
    "Px4MavrosDrone",
    "Px4MavlinkDrone",
    "Px4ModeCodec",
    "Px4DdsDrone",
    "Px4DdsTransport",
]
