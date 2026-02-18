"""
Utilities for the detection module.

Device management, HuggingFace integration, and dataset utilities.
"""

from nectar.ai.detection.utils.dataset_converter import DatasetConverter
from nectar.ai.detection.utils.dataset_merger import DatasetMerger
from nectar.ai.detection.utils.device import DeviceManager, get_device
from nectar.ai.detection.utils.huggingface import HuggingFaceUploader

__all__ = [
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "DatasetConverter",
    "DatasetMerger",
]
