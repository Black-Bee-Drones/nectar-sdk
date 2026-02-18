"""
Detection model implementations.

Model implementations for different frameworks (Ultralytics, Transformers, RF-DETR).
"""

from nectar.ai.detection.models.dataset import (
    CocoDetectionDataset,
    DetectionDataset,
    collate_fn,
    load_detection_dataset,
)
from nectar.ai.detection.models.model_loader import ModelLoader
from nectar.ai.detection.models.rfdetr import RFDETRModel
from nectar.ai.detection.models.transformers import TransformersModel
from nectar.ai.detection.models.ultralytics import UltralyticsModel

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
