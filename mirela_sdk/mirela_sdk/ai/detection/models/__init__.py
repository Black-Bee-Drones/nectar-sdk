"""
Detection model implementations.

Model implementations for different frameworks (Ultralytics, Transformers, RF-DETR).
"""

from mirela_sdk.ai.detection.models.model_loader import ModelLoader
from mirela_sdk.ai.detection.models.ultralytics import UltralyticsModel
from mirela_sdk.ai.detection.models.transformers import TransformersModel
from mirela_sdk.ai.detection.models.rfdetr import RFDETRModel
from mirela_sdk.ai.detection.models.dataset import (
    CocoDetectionDataset,
    DetectionDataset,
    load_detection_dataset,
    collate_fn,
)

__all__ = [
    "ModelLoader",
    "UltralyticsModel",
    "TransformersModel",
    "RFDETRModel",
    "CocoDetectionDataset",
    "DetectionDataset",
    "load_detection_dataset",
    "collate_fn",
]
