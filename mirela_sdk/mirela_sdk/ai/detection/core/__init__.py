"""
Core detection module components.

Base classes, types, protocols, and registry for the detection module.
"""

from mirela_sdk.ai.detection.core.types import (
    Detection,
    DetectionResult,
    Prediction,
    DetectionInput,
    ImageType,
    BatchImageType,
)
from mirela_sdk.ai.detection.core.configs import (
    TrainingConfig,
    EvaluationConfig,
    TrainingMetrics,
    EvaluationMetrics,
    TrainingResult,
)
from mirela_sdk.ai.detection.core.protocols import (
    DetectorProtocol,
    TrainableProtocol,
    MergingStrategy,
    TrainingCallback,
)
from mirela_sdk.ai.detection.core.base import BaseDetectionModel
from mirela_sdk.ai.detection.core.registry import ModelRegistry, registry
from mirela_sdk.ai.detection.core.exceptions import (
    DetectionError,
    ModelNotLoadedError,
    TrainingError,
    EvaluationError,
    DatasetError,
    ConfigurationError,
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
