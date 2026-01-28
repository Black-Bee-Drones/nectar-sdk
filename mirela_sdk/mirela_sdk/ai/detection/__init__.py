"""
Detection module for object detection training, evaluation, and inference.

Unified interface for object detection across multiple frameworks
(Ultralytics YOLO, HuggingFace Transformers DETR, RF-DETR) with
comprehensive training, evaluation, and post-processing capabilities.

Examples
--------
>>> from mirela_sdk.ai.detection import Detector, TrainingConfig
>>>
>>> # Quick inference (auto-detects framework)
>>> detector = Detector("yolov8n.pt")
>>> detector.load()
>>> result = detector.detect(image)
>>> for det in result:
...     print(f"{det.class_name}: {det.confidence:.2f}")
>>>
>>> # Or use specific model classes for advanced usage
>>> from mirela_sdk.ai.detection import UltralyticsModel
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

from mirela_sdk.ai.detection.detector import Detector, Framework

# Core types and data classes
from mirela_sdk.ai.detection.core.types import (
    Detection,
    DetectionResult,
    Prediction,
    DetectionInput,
    ImageType,
    BatchImageType,
)

# Configuration classes
from mirela_sdk.ai.detection.core.configs import (
    TrainingConfig,
    EvaluationConfig,
    TrainingMetrics,
    EvaluationMetrics,
    TrainingResult,
)

# Protocols and base classes
from mirela_sdk.ai.detection.core.protocols import (
    DetectorProtocol,
    TrainableProtocol,
    MergingStrategy,
)
from mirela_sdk.ai.detection.core.base import BaseDetectionModel

# Registry and factory
from mirela_sdk.ai.detection.core.registry import (
    ModelRegistry,
    DetectorFactory,
    registry,
)

# Exceptions
from mirela_sdk.ai.detection.core.exceptions import (
    DetectionError,
    ModelNotLoadedError,
    TrainingError,
    EvaluationError,
    DatasetError,
    ConfigurationError,
    FrameworkError,
    PostProcessingError,
    SlicingError,
    HuggingFaceError,
    DeviceError,
)

# Slicing inference
from mirela_sdk.ai.detection.slicing import (
    SlicingConfig,
    SlicingStrategy,
    SlicingInference,
)

# Model implementations
from mirela_sdk.ai.detection.models import (
    ModelLoader,
    UltralyticsModel,
    TransformersModel,
    RFDETRModel,
    CocoDetectionDataset,
    load_detection_dataset,
)

# Evaluation
from mirela_sdk.ai.detection.evaluation import ObjectDetectionEvaluator

# Post-processing
from mirela_sdk.ai.detection.postprocess import (
    NMSStrategy,
    SoftNMSStrategy,
    WBFStrategy,
    NMMStrategy,
)

# Utilities
from mirela_sdk.ai.detection.utils import (
    HuggingFaceUploader,
    get_device,
    DeviceManager,
    DatasetConverter,
    DatasetMerger,
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
    # Protocols
    "DetectorProtocol",
    "TrainableProtocol",
    "MergingStrategy",
    # Base
    "BaseDetectionModel",
    # Registry
    "ModelRegistry",
    "DetectorFactory",
    "registry",
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
    "NMSStrategy",
    "SoftNMSStrategy",
    "WBFStrategy",
    "NMMStrategy",
    # Utilities
    "HuggingFaceUploader",
    "get_device",
    "DeviceManager",
    "DatasetConverter",
    "DatasetMerger",
]
