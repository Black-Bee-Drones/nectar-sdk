"""Benewake LiDAR drivers."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "BenewakeTF": "nectar.sensors.benewake.tf_series",
    "MODELS": "nectar.sensors.benewake.tf_series",
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
    from nectar.sensors.benewake.tf_series import MODELS, BenewakeTF


__all__ = ["BenewakeTF", "MODELS"]
