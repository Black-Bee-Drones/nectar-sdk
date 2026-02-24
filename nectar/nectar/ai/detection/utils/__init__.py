"""
Utilities for the detection module.

Device management and HuggingFace integration.
"""

from nectar.ai.detection.utils.device import DeviceManager, get_device
from nectar.ai.detection.utils.huggingface import HuggingFaceUploader

__all__ = [
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
]
