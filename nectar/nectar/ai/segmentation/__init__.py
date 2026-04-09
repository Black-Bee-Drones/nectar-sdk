"""
Nectar SDK - Image Segmentation Module.

Supports instance segmentation (Ultralytics, RF-DETR, Mask2Former) and
semantic segmentation (SegFormer) via a unified API.

Examples
--------
>>> from nectar.ai.segmentation import Segmentor
>>> segmentor = Segmentor("yolov8n-seg.pt")
>>> segmentor.load()
>>> result = segmentor.segment(image)
"""

from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import (
    SegEvaluationConfig,
    SegEvaluationMetrics,
    SegTrainingConfig,
)
from nectar.ai.segmentation.core.types import (
    Segmentation,
    SegmentationInput,
    SegmentationResult,
    SegPrediction,
)
from nectar.ai.segmentation.datasets import (
    SegDatasetAnalyzer,
    SegDatasetHandlerRegistry,
    SegFormatConverter,
    UltralyticsSegHandler,
    RoboflowSegHandler,
)
from nectar.ai.segmentation.evaluation.evaluator import SegmentationEvaluator
from nectar.ai.segmentation.models.rfdetr import RFDETRSegModel
from nectar.ai.segmentation.models.transformers import TransformersSegModel
from nectar.ai.segmentation.models.ultralytics import UltralyticsSegModel
from nectar.ai.segmentation.segmentor import Segmentor

__all__ = [
    # Facade
    "Segmentor",
    # Base
    "BaseSegmentationModel",
    # Model classes
    "UltralyticsSegModel",
    "TransformersSegModel",
    "RFDETRSegModel",
    # Types
    "Segmentation",
    "SegmentationResult",
    "SegmentationInput",
    "SegPrediction",
    # Configs
    "SegTrainingConfig",
    "SegEvaluationConfig",
    "SegEvaluationMetrics",
    # Evaluation
    "SegmentationEvaluator",
    # Datasets
    "SegFormatConverter",
    "SegDatasetAnalyzer",
    "SegDatasetHandlerRegistry",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
]
