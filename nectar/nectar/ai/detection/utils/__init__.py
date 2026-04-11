"""
Utilities for the detection module.
"""

from nectar.ai.detection.utils.callbacks import (
    get_hf_upload_ptl_callback,
    setup_ultralytics_gc_callback,
    setup_ultralytics_hf_callbacks,
)
from nectar.ai.detection.utils.device import DeviceManager, get_device
from nectar.ai.detection.utils.huggingface import HuggingFaceUploader
from nectar.ai.detection.utils.tensorboard import TensorBoardManager

__all__ = [
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "TensorBoardManager",
    "get_hf_upload_ptl_callback",
    "setup_ultralytics_hf_callbacks",
    "setup_ultralytics_gc_callback",
]
