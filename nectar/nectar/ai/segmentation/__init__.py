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

from importlib import import_module
from typing import TYPE_CHECKING

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

_LAZY_ATTRS = {
    "BaseSegmentationModel": "nectar.ai.segmentation.core.base",
    # Heavy: pull torch + framework
    "Segmentor": "nectar.ai.segmentation.segmentor",
    "RFDETRSegModel": "nectar.ai.segmentation.models.rfdetr",
    "TransformersSegModel": "nectar.ai.segmentation.models.transformers",
    "UltralyticsSegModel": "nectar.ai.segmentation.models.ultralytics",
    # Pulls matplotlib via visualizations
    "SegmentationEvaluator": "nectar.ai.segmentation.evaluation.evaluator",
    # Datasets (re-exported)
    "RoboflowSegHandler": "nectar.ai.segmentation.datasets",
    "SegDatasetAnalyzer": "nectar.ai.segmentation.datasets",
    "SegDatasetHandlerRegistry": "nectar.ai.segmentation.datasets",
    "SegFormatConverter": "nectar.ai.segmentation.datasets",
    "UltralyticsSegHandler": "nectar.ai.segmentation.datasets",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from nectar.ai.segmentation.core.base import BaseSegmentationModel
    from nectar.ai.segmentation.datasets import (
        RoboflowSegHandler,
        SegDatasetAnalyzer,
        SegDatasetHandlerRegistry,
        SegFormatConverter,
        UltralyticsSegHandler,
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
