"""
Detection module for object detection training, evaluation, and inference.

Unified interface for object detection across multiple frameworks
(Ultralytics YOLO, HuggingFace Transformers DETR, RF-DETR) with
comprehensive training, evaluation, and post-processing capabilities.

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

from nectar.ai.detection.core.base import BaseDetectionModel

# Configuration classes
from nectar.ai.detection.core.configs import (
    EvaluationConfig,
    EvaluationMetrics,
    TrainingConfig,
    TrainingMetrics,
    TrainingResult,
)

# Exceptions
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

# Core types and data classes
from nectar.ai.detection.core.types import (
    BatchImageType,
    Detection,
    DetectionInput,
    DetectionResult,
    ImageType,
    Prediction,
)
from nectar.ai.detection.detector import Detector, Framework

# Evaluation
from nectar.ai.detection.evaluation import ObjectDetectionEvaluator

# Model implementations
from nectar.ai.detection.models import (
    CocoDetectionDataset,
    ModelLoader,
    RFDETRModel,
    TransformersModel,
    UltralyticsModel,
    load_detection_dataset,
)

# Post-processing
from nectar.ai.detection.postprocess import (
    BaseMergingStrategy,
    NMMStrategy,
    NMSStrategy,
    PerClassConfidenceFilter,
    SoftNMSStrategy,
    WBFStrategy,
)

# Slicing inference
from nectar.ai.detection.slicing import (
    SlicingConfig,
    SlicingInference,
    SlicingStrategy,
)

# Utilities
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
