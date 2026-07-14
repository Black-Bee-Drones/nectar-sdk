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
from nectar.ai.core.utils.ultralytics_datasets import nectar_ultralytics_datasets_dir

__all__ = [
    "HF_SYNC_IGNORE_PATTERNS",
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "TensorBoardManager",
    "get_hf_upload_ptl_callback",
    "get_hf_upload_transformers_callback",
    "nectar_ultralytics_datasets_dir",
    "setup_ultralytics_hf_callbacks",
    "setup_ultralytics_gc_callback",
]
