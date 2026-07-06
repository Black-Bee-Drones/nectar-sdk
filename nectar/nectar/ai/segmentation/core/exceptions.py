"""Segmentation exceptions -- reexports from detection for consistency."""

from nectar.ai.detection.core.exceptions import (
    ModelNotLoadedError,
    TrainingError,
)

__all__ = ["ModelNotLoadedError", "TrainingError"]
