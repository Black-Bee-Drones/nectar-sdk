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
>>> from mirela_sdk.vision.algorithms.distance import DistanceEstimator
>>> estimator = DistanceEstimator()
>>> distance_cm = estimator.estimate(pixel_height=25.0)
"""

from mirela_sdk.vision.algorithms.distance.calibrator import (
    CalibrationResult,
    ModelCalibrator,
)
from mirela_sdk.vision.algorithms.distance.estimator import DistanceEstimator
from mirela_sdk.vision.algorithms.distance.models import (
    EstimationModel,
    ModelType,
    create_model,
)

__all__ = [
    "ModelType",
    "EstimationModel",
    "create_model",
    "DistanceEstimator",
    "ModelCalibrator",
    "CalibrationResult",
]
