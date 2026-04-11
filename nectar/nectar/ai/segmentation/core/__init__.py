"""Core segmentation types, configs, and base classes."""

from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import (
    SegEvaluationConfig,
    SegEvaluationMetrics,
    SegTrainingConfig,
)
from nectar.ai.segmentation.core.types import (
    Segmentation,
    SegmentationInput,
    SegmentationResult,
    SegPrediction,
)

__all__ = [
    "BaseSegmentationModel",
    "SegTrainingConfig",
    "SegEvaluationConfig",
    "SegEvaluationMetrics",
    "Segmentation",
    "SegmentationResult",
    "SegmentationInput",
    "SegPrediction",
]
