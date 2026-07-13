"""
Nectar SDK - Image Classification Module.

Supports image classification via Ultralytics YOLO-cls and HuggingFace
Transformers (ViT, etc.) behind one ``Classifier``.

Examples
--------
>>> from nectar.ai.classification import Classifier
>>> classifier = Classifier("yolo26n-cls.pt")
>>> classifier.load()
>>> result = classifier.classify(image)
"""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.classification.core.configs import (
    ClsEvaluationConfig,
    ClsEvaluationMetrics,
    ClsTrainingConfig,
)
from nectar.ai.classification.core.types import (
    Classification,
    ClassificationInput,
    ClassificationResult,
    ClsPrediction,
)

_LAZY_ATTRS = {
    "BaseClassificationModel": "nectar.ai.classification.core.base",
    "Classifier": "nectar.ai.classification.classifier",
    "TransformersClsModel": "nectar.ai.classification.models.transformers",
    "UltralyticsClsModel": "nectar.ai.classification.models.ultralytics",
    "ClassificationEvaluator": "nectar.ai.classification.evaluation.evaluator",
    "ClsDatasetAnalyzer": "nectar.ai.classification.datasets",
    "ClsDatasetHandlerRegistry": "nectar.ai.classification.datasets",
    "ClsFormatConverter": "nectar.ai.classification.datasets",
    "ImageFolderDetector": "nectar.ai.classification.datasets",
    "UltralyticsClsHandler": "nectar.ai.classification.datasets",
    "RoboflowClsHandler": "nectar.ai.classification.datasets",
    "HuggingFaceClsHandler": "nectar.ai.classification.datasets",
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
    from nectar.ai.classification.classifier import Classifier
    from nectar.ai.classification.core.base import BaseClassificationModel
    from nectar.ai.classification.datasets import (
        ClsDatasetAnalyzer,
        ClsDatasetHandlerRegistry,
        ClsFormatConverter,
        HuggingFaceClsHandler,
        ImageFolderDetector,
        RoboflowClsHandler,
        UltralyticsClsHandler,
    )
    from nectar.ai.classification.evaluation.evaluator import ClassificationEvaluator
    from nectar.ai.classification.models.transformers import TransformersClsModel
    from nectar.ai.classification.models.ultralytics import UltralyticsClsModel


__all__ = [
    "Classifier",
    "BaseClassificationModel",
    "UltralyticsClsModel",
    "TransformersClsModel",
    "Classification",
    "ClassificationResult",
    "ClassificationInput",
    "ClsPrediction",
    "ClsTrainingConfig",
    "ClsEvaluationConfig",
    "ClsEvaluationMetrics",
    "ClassificationEvaluator",
    "ImageFolderDetector",
    "ClsFormatConverter",
    "ClsDatasetAnalyzer",
    "ClsDatasetHandlerRegistry",
    "UltralyticsClsHandler",
    "RoboflowClsHandler",
    "HuggingFaceClsHandler",
]
