"""
Utilities for the detection module.

Device management, HuggingFace integration, and dataset utilities.
"""

from mirela_sdk.ai.detection.utils.huggingface import HuggingFaceUploader
from mirela_sdk.ai.detection.utils.device import get_device, DeviceManager
from mirela_sdk.ai.detection.utils.dataset_converter import DatasetConverter
from mirela_sdk.ai.detection.utils.dataset_merger import DatasetMerger

__all__ = [
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "DatasetConverter",
    "DatasetMerger",
]
