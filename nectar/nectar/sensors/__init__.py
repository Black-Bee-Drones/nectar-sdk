"""Nectar SDK - Sensors module."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.sensors.base import DistanceFilter, DistanceSensor

_LAZY_ATTRS = {
    "TFLuna": "nectar.sensors.benewake.tfluna",
    "ObstacleMaskFilter": "nectar.sensors.filters.obstacle_mask",
    "RangefinderPublisher": "nectar.sensors.rangefinder_publisher",
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
    from nectar.sensors.benewake.tfluna import TFLuna
    from nectar.sensors.filters.obstacle_mask import ObstacleMaskFilter
    from nectar.sensors.rangefinder_publisher import RangefinderPublisher


__all__ = [
    "DistanceSensor",
    "DistanceFilter",
    "TFLuna",
    "ObstacleMaskFilter",
    "RangefinderPublisher",
]
