"""
Distance estimation from pixel measurements.

This module provides tools for estimating real-world distances from
pixel measurements using various calibrated regression models.

Classes
-------
DistanceEstimator
    Main interface for distance estimation with pre-calibrated models.
ModelCalibrator
    Calibrate models from (distance, pixel) measurement data.
CalibrationResult
    Results container for fitted model parameters and metrics.

Enums
-----
ModelType
    Available model types (LINEAR, POLYNOMIAL, EXPONENTIAL, etc.).

Functions
---------
create_model
    Factory function to create model instances.

Example
-------
>>> from nectar.vision.algorithms.distance import DistanceEstimator
>>> estimator = DistanceEstimator()
>>> distance_cm = estimator.estimate(pixel_height=25.0)
"""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.vision.algorithms.distance.estimator import DistanceEstimator
from nectar.vision.algorithms.distance.models import (
    EstimationModel,
    ModelType,
    create_model,
)

_LAZY_ATTRS = {
    # Pulls matplotlib for calibration plots
    "ModelCalibrator": "nectar.vision.algorithms.distance.calibrator",
    "CalibrationResult": "nectar.vision.algorithms.distance.calibrator",
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
    from nectar.vision.algorithms.distance.calibrator import (
        CalibrationResult,
        ModelCalibrator,
    )


__all__ = [
    "ModelType",
    "EstimationModel",
    "create_model",
    "DistanceEstimator",
    "ModelCalibrator",
    "CalibrationResult",
]
