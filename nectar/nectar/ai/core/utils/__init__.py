"""Shared AI utilities (device, Hub upload, TensorBoard, training callbacks)."""

from nectar.ai.core.utils.callbacks import (
    HF_SYNC_IGNORE_PATTERNS,
    get_hf_upload_ptl_callback,
    get_hf_upload_transformers_callback,
    setup_ultralytics_gc_callback,
    setup_ultralytics_hf_callbacks,
)
from nectar.ai.core.utils.device import DeviceManager, get_device
from nectar.ai.core.utils.huggingface import HuggingFaceUploader
from nectar.ai.core.utils.tensorboard import TensorBoardManager

__all__ = [
    "HF_SYNC_IGNORE_PATTERNS",
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "TensorBoardManager",
    "get_hf_upload_ptl_callback",
    "get_hf_upload_transformers_callback",
    "setup_ultralytics_hf_callbacks",
    "setup_ultralytics_gc_callback",
]
