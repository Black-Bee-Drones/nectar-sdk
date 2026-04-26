"""
Nectar SDK - AI module.
"""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.detection import (
    Detection,
    DetectionInput,
    DetectionResult,
    Detector,
    EvaluationConfig,
    EvaluationMetrics,
    Framework,
    Prediction,
    TrainingConfig,
)

_LAZY_ATTRS = {
    # Detection (heavy)
    "BaseDetectionModel": "nectar.ai.detection",
    "ModelLoader": "nectar.ai.detection",
    "UltralyticsModel": "nectar.ai.detection",
    "TransformersModel": "nectar.ai.detection",
    "RFDETRModel": "nectar.ai.detection",
    "ObjectDetectionEvaluator": "nectar.ai.detection",
    "RoboflowUploader": "nectar.ai.detection.datasets.upload",
    # Segmentation (heavy: torch, transformers, rfdetr, matplotlib)
    "Segmentor": "nectar.ai.segmentation",
    "BaseSegmentationModel": "nectar.ai.segmentation",
    "UltralyticsSegModel": "nectar.ai.segmentation",
    "TransformersSegModel": "nectar.ai.segmentation",
    "RFDETRSegModel": "nectar.ai.segmentation",
    "Segmentation": "nectar.ai.segmentation",
    "SegmentationResult": "nectar.ai.segmentation",
    "SegmentationInput": "nectar.ai.segmentation",
    "SegPrediction": "nectar.ai.segmentation",
    "SegTrainingConfig": "nectar.ai.segmentation",
    "SegEvaluationConfig": "nectar.ai.segmentation",
    "SegEvaluationMetrics": "nectar.ai.segmentation",
    "SegmentationEvaluator": "nectar.ai.segmentation",
    "SegFormatConverter": "nectar.ai.segmentation",
    "SegDatasetAnalyzer": "nectar.ai.segmentation",
    "SegDatasetHandlerRegistry": "nectar.ai.segmentation",
    "UltralyticsSegHandler": "nectar.ai.segmentation",
    "RoboflowSegHandler": "nectar.ai.segmentation",
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
    from nectar.ai.detection import (
        BaseDetectionModel,
        ModelLoader,
        ObjectDetectionEvaluator,
        RFDETRModel,
        TransformersModel,
        UltralyticsModel,
    )
    from nectar.ai.detection.datasets.upload import RoboflowUploader
    from nectar.ai.segmentation import (
        BaseSegmentationModel,
        RFDETRSegModel,
        RoboflowSegHandler,
        SegDatasetAnalyzer,
        SegDatasetHandlerRegistry,
        SegEvaluationConfig,
        SegEvaluationMetrics,
        SegFormatConverter,
        Segmentation,
        SegmentationEvaluator,
        SegmentationInput,
        SegmentationResult,
        Segmentor,
        SegPrediction,
        SegTrainingConfig,
        TransformersSegModel,
        UltralyticsSegHandler,
        UltralyticsSegModel,
    )


__all__ = [
    # Detection API
    "Detector",
    "Framework",
    "UltralyticsModel",
    "TransformersModel",
    "RFDETRModel",
    "BaseDetectionModel",
    "Detection",
    "DetectionResult",
    "Prediction",
    "DetectionInput",
    "TrainingConfig",
    "EvaluationConfig",
    "EvaluationMetrics",
    "ModelLoader",
    "ObjectDetectionEvaluator",
    "RoboflowUploader",
    # Segmentation API
    "Segmentor",
    "UltralyticsSegModel",
    "TransformersSegModel",
    "RFDETRSegModel",
    "BaseSegmentationModel",
    "Segmentation",
    "SegmentationResult",
    "SegmentationInput",
    "SegPrediction",
    "SegTrainingConfig",
    "SegEvaluationConfig",
    "SegEvaluationMetrics",
    "SegmentationEvaluator",
    # Segmentation datasets
    "SegFormatConverter",
    "SegDatasetAnalyzer",
    "SegDatasetHandlerRegistry",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
]
