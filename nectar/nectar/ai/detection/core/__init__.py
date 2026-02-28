"""
Core detection module components.

Base classes, types, protocols, and registry for the detection module.
"""

from nectar.ai.detection.core.base import BaseDetectionModel
from nectar.ai.detection.core.configs import (
    EvaluationConfig,
    EvaluationMetrics,
    TrainingConfig,
    TrainingMetrics,
    TrainingResult,
)
from nectar.ai.detection.core.exceptions import (
    ConfigurationError,
    DatasetError,
    DetectionError,
    EvaluationError,
    ModelNotLoadedError,
    TrainingError,
)
from nectar.ai.detection.core.types import (
    BatchImageType,
    Detection,
    DetectionInput,
    DetectionResult,
    ImageType,
    Prediction,
)

__all__ = [
    # Types
    "Detection",
    "DetectionResult",
    "Prediction",
    "DetectionInput",
    "ImageType",
    "BatchImageType",
    # Configs
    "TrainingConfig",
    "EvaluationConfig",
    "TrainingMetrics",
    "EvaluationMetrics",
    "TrainingResult",
    # Base
    "BaseDetectionModel",
    # Exceptions
    "DetectionError",
    "ModelNotLoadedError",
    "TrainingError",
    "EvaluationError",
    "DatasetError",
    "ConfigurationError",
]
