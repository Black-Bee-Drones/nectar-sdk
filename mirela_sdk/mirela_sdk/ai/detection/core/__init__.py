"""
Core detection module components.

Base classes, types, protocols, and registry for the detection module.
"""

from mirela_sdk.ai.detection.core.base import BaseDetectionModel
from mirela_sdk.ai.detection.core.configs import (
    EvaluationConfig,
    EvaluationMetrics,
    TrainingConfig,
    TrainingMetrics,
    TrainingResult,
)
from mirela_sdk.ai.detection.core.exceptions import (
    ConfigurationError,
    DatasetError,
    DetectionError,
    EvaluationError,
    ModelNotLoadedError,
    TrainingError,
)
from mirela_sdk.ai.detection.core.protocols import (
    DetectorProtocol,
    MergingStrategy,
    TrainableProtocol,
    TrainingCallback,
)
from mirela_sdk.ai.detection.core.registry import ModelRegistry, registry
from mirela_sdk.ai.detection.core.types import (
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
    # Protocols
    "DetectorProtocol",
    "TrainableProtocol",
    "MergingStrategy",
    "TrainingCallback",
    # Base
    "BaseDetectionModel",
    # Registry
    "ModelRegistry",
    "registry",
    # Exceptions
    "DetectionError",
    "ModelNotLoadedError",
    "TrainingError",
    "EvaluationError",
    "DatasetError",
    "ConfigurationError",
]
