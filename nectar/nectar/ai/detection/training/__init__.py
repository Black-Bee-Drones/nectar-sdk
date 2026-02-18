"""
Training configuration for detection models.
"""

from nectar.ai.detection.training.config import (
    RFDETRTrainingConfig,
    TrainingConfig,
    TransformersTrainingConfig,
    UltralyticsTrainingConfig,
)

__all__ = [
    # Configs
    "TrainingConfig",
    "UltralyticsTrainingConfig",
    "TransformersTrainingConfig",
    "RFDETRTrainingConfig",
]
