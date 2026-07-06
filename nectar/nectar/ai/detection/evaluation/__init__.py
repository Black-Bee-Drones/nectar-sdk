"""
Evaluation module for detection models.
"""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "ObjectDetectionEvaluator": "nectar.ai.detection.evaluation.evaluator",
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
    from nectar.ai.detection.evaluation.evaluator import ObjectDetectionEvaluator


__all__ = [
    "ObjectDetectionEvaluator",
]
