"""Direct MAVLink (pymavlink) control path."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "MavlinkConnection": "nectar.control.mavlink.connection",
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


__all__ = ["MavlinkConnection"]
