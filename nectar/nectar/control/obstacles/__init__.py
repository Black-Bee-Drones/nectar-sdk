"""Obstacle detection and avoidance."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.control.obstacles import strategies
from nectar.control.obstacles.base import BaseObstacleDetector
from nectar.control.obstacles.handler import ObstacleHandler, ObstacleManager
from nectar.control.obstacles.types import ObstacleHandlerConfig
from nectar.control.protocols import ObstacleDirection, ObstacleInfo

_LAZY_ATTRS = {
    "DepthObstacleDetector": "nectar.control.obstacles.depth_camera",
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
    from nectar.control.obstacles.depth_camera import DepthObstacleDetector


__all__ = [
    "BaseObstacleDetector",
    "DepthObstacleDetector",
    "ObstacleHandlerConfig",
    "ObstacleHandler",
    "ObstacleManager",
    "ObstacleInfo",
    "ObstacleDirection",
    "strategies",
]
