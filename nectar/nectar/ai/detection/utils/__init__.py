"""
Utilities for the detection module.
"""

from nectar.ai.detection.utils.device import DeviceManager, get_device
from nectar.ai.detection.utils.huggingface import HuggingFaceUploader
from nectar.ai.detection.utils.tensorboard import TensorBoardManager

__all__ = [
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "TensorBoardManager",
]
