"""
Shared AI core: framework enum, model loading, exceptions, and utilities.

Task packages (detection, segmentation, classification) build on this module.
"""

from nectar.ai.core.exceptions import AIError, ModelNotLoadedError, TrainingError
from nectar.ai.core.framework import Framework
from nectar.ai.core.model_loader import ModelLoader
from nectar.ai.core.registry import HandlerRegistry
from nectar.ai.core.utils import (
    DeviceManager,
    HuggingFaceUploader,
    TensorBoardManager,
    get_device,
)

__all__ = [
    "AIError",
    "DeviceManager",
    "Framework",
    "HandlerRegistry",
    "HuggingFaceUploader",
    "ModelLoader",
    "ModelNotLoadedError",
    "TensorBoardManager",
    "TrainingError",
    "get_device",
]
