"""
Detection module for object detection training, evaluation, and inference.

Unified interface for object detection across multiple frameworks

Examples
--------
>>> from nectar.ai.detection import Detector, TrainingConfig
>>>
>>> # Quick inference (auto-detects framework)
>>> detector = Detector("yolov8n.pt")
>>> detector.load()
>>> result = detector.detect(image)
>>> for det in result:
...     print(f"{det.class_name}: {det.confidence:.2f}")
>>>
>>> # Or use specific model classes for advanced usage
>>> from nectar.ai.detection import UltralyticsModel
>>> model = UltralyticsModel("yolov8n.pt")
>>> model.load_model()
>>> result = model.detect(image, conf=0.5)
>>>
>>> # Training
>>> config = TrainingConfig(
...     dataset_path="/path/to/dataset",
...     epochs=100,
...     batch_size=16,
...     tensorboard=True,
... )
>>> result = detector.train(config)
"""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.detection.core.configs import (
    EvaluationConfig,
    EvaluationMetrics,
    TrainingConfig,
    TrainingMetrics,
    TrainingResult,
)
from nectar.ai.detection.core.exceptions import (
    ConfigurationError,
    DatasetError,
    DetectionError,
    DeviceError,
    EvaluationError,
    FrameworkError,
    HuggingFaceError,
    ModelNotLoadedError,
    PostProcessingError,
    SlicingError,
    TrainingError,
)
from nectar.ai.detection.core.types import (
    BatchImageType,
    Detection,
    DetectionInput,
    DetectionResult,
    ImageType,
    Prediction,
)
from nectar.ai.detection.detector import Detector, Framework

_LAZY_ATTRS = {
    "BaseDetectionModel": "nectar.ai.detection.core.base",
    # Models (heavy: pull torch, ultralytics, transformers, rfdetr)
    "ModelLoader": "nectar.ai.detection.models.model_loader",
    "UltralyticsModel": "nectar.ai.detection.models.ultralytics",
    "TransformersModel": "nectar.ai.detection.models.transformers",
    "RFDETRModel": "nectar.ai.detection.models.rfdetr",
    "CocoDetectionDataset": "nectar.ai.detection.models.dataset",
    "load_detection_dataset": "nectar.ai.detection.models.dataset",
    # Evaluation (heavy: pulls matplotlib, supervision)
    "ObjectDetectionEvaluator": "nectar.ai.detection.evaluation",
    # Post-processing (light, but kept lazy for symmetry)
    "BaseMergingStrategy": "nectar.ai.detection.postprocess",
    "NMSStrategy": "nectar.ai.detection.postprocess",
    "SoftNMSStrategy": "nectar.ai.detection.postprocess",
    "WBFStrategy": "nectar.ai.detection.postprocess",
    "NMMStrategy": "nectar.ai.detection.postprocess",
    "PerClassConfidenceFilter": "nectar.ai.detection.postprocess",
    # Slicing (pulls supervision)
    "SlicingConfig": "nectar.ai.detection.slicing",
    "SlicingStrategy": "nectar.ai.detection.slicing",
    "SlicingInference": "nectar.ai.detection.slicing",
    # Utilities
    "HuggingFaceUploader": "nectar.ai.detection.utils.huggingface",
    "get_device": "nectar.ai.detection.utils.device",
    "DeviceManager": "nectar.ai.detection.utils.device",
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
    from nectar.ai.detection.core.base import BaseDetectionModel
    from nectar.ai.detection.evaluation import ObjectDetectionEvaluator
    from nectar.ai.detection.models import (
        CocoDetectionDataset,
        ModelLoader,
        RFDETRModel,
        TransformersModel,
        UltralyticsModel,
        load_detection_dataset,
    )
    from nectar.ai.detection.postprocess import (
        BaseMergingStrategy,
        NMMStrategy,
        NMSStrategy,
        PerClassConfidenceFilter,
        SoftNMSStrategy,
        WBFStrategy,
    )
    from nectar.ai.detection.slicing import (
        SlicingConfig,
        SlicingInference,
        SlicingStrategy,
    )
    from nectar.ai.detection.utils import (
        DeviceManager,
        HuggingFaceUploader,
        get_device,
    )


__all__ = [
    # Simple API
    "Detector",
    "Framework",
    # Core types
    "Detection",
    "DetectionResult",
    "Prediction",
    "DetectionInput",
    "ImageType",
    "BatchImageType",
    # Configs
    "TrainingConfig",
    "EvaluationConfig",
    "TrainingMetrics",
    "EvaluationMetrics",
    "TrainingResult",
    # Base
    "BaseDetectionModel",
    # Exceptions
    "DetectionError",
    "ModelNotLoadedError",
    "TrainingError",
    "EvaluationError",
    "DatasetError",
    "ConfigurationError",
    "FrameworkError",
    "PostProcessingError",
    "SlicingError",
    "HuggingFaceError",
    "DeviceError",
    # Slicing
    "SlicingConfig",
    "SlicingStrategy",
    "SlicingInference",
    # Models
    "ModelLoader",
    "UltralyticsModel",
    "TransformersModel",
    "RFDETRModel",
    "CocoDetectionDataset",
    "load_detection_dataset",
    # Evaluation
    "ObjectDetectionEvaluator",
    # Post-processing
    "BaseMergingStrategy",
    "NMSStrategy",
    "SoftNMSStrategy",
    "WBFStrategy",
    "NMMStrategy",
    "PerClassConfidenceFilter",
    # Utilities
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
]
