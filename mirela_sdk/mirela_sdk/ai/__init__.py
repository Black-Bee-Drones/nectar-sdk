"""AI module for detection, inference, and model management."""

from .detection import YOLODetector, BaseDetectionModel, UltralyticsDetectionModel
from .detection import Detection, DetectionResult, ModelLoader
from .utils import RoboflowUploader

__all__ = [
    "YOLODetector",
    "BaseDetectionModel",
    "UltralyticsDetectionModel",
    "Detection",
    "DetectionResult",
    "ModelLoader",
    "RoboflowUploader",
]
