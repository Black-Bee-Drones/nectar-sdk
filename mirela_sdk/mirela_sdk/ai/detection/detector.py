"""
Unified detector with factory pattern.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from mirela_sdk.ai.detection.core.base import BaseDetectionModel
from mirela_sdk.ai.detection.core.types import DetectionResult
from mirela_sdk.ai.detection.core.configs import TrainingConfig, EvaluationConfig

logger = logging.getLogger(__name__)


class Framework(Enum):
    """Supported detection frameworks."""

    ULTRALYTICS = "ultralytics"
    TRANSFORMERS = "transformers"
    RFDETR = "rfdetr"


BuilderFunc = Callable[..., BaseDetectionModel]


class Detector:
    """
    Unified detector with factory pattern for creating model instances.

    Supports auto-detection from model name or explicit framework specification.

    Parameters
    ----------
    model_source : str
        Model path, name, or HuggingFace ID.
    framework : Optional[Union[Framework, str]], optional
        Explicit framework. Auto-detects if not provided.
    device : str, optional
        Device ('auto', 'cpu', 'cuda', '0'). Defaults to 'auto'.
    confidence_threshold : float, optional
        Default confidence threshold. Defaults to 0.25.
    **kwargs
        Additional arguments passed to the model constructor.

    Attributes
    ----------
    framework : Framework
        The framework being used.
    class_names : Dict[int, str]
        Class ID to name mapping.
    is_loaded : bool
        Whether model is loaded.

    Examples
    --------
    >>> detector = Detector("yolov8n.pt")
    >>> detector.load()
    >>> result = detector.detect(image)
    >>>
    >>> # Explicit framework
    >>> detector = Detector("model.pt", framework="ultralytics")
    >>>
    >>> # Using enum
    >>> detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)
    """

    _builders: Dict[str, BuilderFunc] = {}

    def __init__(
        self,
        model_source: str,
        framework: Optional[Union[Framework, str]] = None,
        device: str = "auto",
        confidence_threshold: float = 0.25,
        **kwargs,
    ):
        self.model_source = model_source
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._kwargs = kwargs

        # Resolve framework
        if framework is not None:
            if isinstance(framework, str):
                framework = Framework(framework.lower())
            self._framework = framework
        else:
            self._framework = self._detect_framework(model_source)

        # Create model
        self._model = self._create_model(self._framework, model_source, **kwargs)
        self._loaded = False

        logger.info("Created %s detector: %s", self._framework.value, model_source)

    @classmethod
    def register(cls, framework: Union[Framework, str], builder: BuilderFunc) -> None:
        """
        Register a framework builder.

        Parameters
        ----------
        framework : Union[Framework, str]
            Framework identifier.
        builder : BuilderFunc
            Factory function (model_name, **kwargs) -> BaseDetectionModel.
        """
        key = framework.value if isinstance(framework, Framework) else framework.lower()
        cls._builders[key] = builder

    @classmethod
    def available_frameworks(cls) -> List[str]:
        """
        Get registered frameworks.

        Returns
        -------
        List[str]
            Available framework names.
        """
        return list(cls._builders.keys())

    @classmethod
    def _detect_framework(cls, source: str) -> Framework:
        """Auto-detect framework from model source."""
        source_lower = source.lower()

        if "rfdetr" in source_lower:
            return Framework.RFDETR
        if any(x in source_lower for x in ["detr", "facebook/", "microsoft/"]):
            return Framework.TRANSFORMERS
        return Framework.ULTRALYTICS

    @classmethod
    def _create_model(
        cls, framework: Framework, model_name: str, **kwargs
    ) -> BaseDetectionModel:
        """Create model instance using registered builder."""
        key = framework.value
        builder = cls._builders.get(key)

        if not builder:
            available = ", ".join(cls._builders.keys())
            raise ValueError(f"Unknown framework: '{key}'. Available: {available}")

        return builder(model_name, **kwargs)

    @property
    def framework(self) -> Framework:
        """Framework: The framework being used."""
        return self._framework

    def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load the model.

        Parameters
        ----------
        model_path : Optional[str], optional
            Override model path.

        Returns
        -------
        bool
            True if loaded successfully.
        """
        try:
            if model_path is None and self._framework == Framework.ULTRALYTICS:
                if "/" in self.model_source and ":" in self.model_source:
                    from mirela_sdk.ai.detection.models.model_loader import ModelLoader

                    model_path = ModelLoader.load(self.model_source)

            self._model.load_model(model_path)
            self._loaded = True
            logger.info("Model loaded: %s", self.model_source)
            return True
        except Exception as e:
            logger.error("Failed to load: %s", e)
            self._loaded = False
            raise

    @property
    def is_loaded(self) -> bool:
        """bool: Check if model is loaded."""
        return self._loaded and self._model.is_loaded

    @property
    def class_names(self) -> Dict[int, str]:
        """Dict[int, str]: Class ID to name mapping."""
        return getattr(self._model, "class_names", {})

    def detect(
        self,
        image: Union[np.ndarray, str, Path],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> DetectionResult:
        """
        Run detection on a single image.

        Parameters
        ----------
        image : Union[np.ndarray, str, Path]
            Input image (BGR format or path).
        conf : Optional[float], optional
            Confidence threshold.
        iou : Optional[float], optional
            IoU threshold for NMS.

        Returns
        -------
        DetectionResult
            Detection results.

        Raises
        ------
        RuntimeError
            If model not loaded.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        conf = conf if conf is not None else self.confidence_threshold
        iou = iou if iou is not None else 0.5

        return self._model.detect(image, conf=conf, iou=iou)

    def detect_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> List[DetectionResult]:
        """
        Run detection on multiple images.

        Parameters
        ----------
        images : List[Union[np.ndarray, str, Path]]
            List of input images.
        conf : Optional[float], optional
            Confidence threshold.
        iou : Optional[float], optional
            IoU threshold.

        Returns
        -------
        List[DetectionResult]
            List of detection results.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        conf = conf if conf is not None else self.confidence_threshold
        iou = iou if iou is not None else 0.5

        return self._model.detect_batch(images, conf=conf, iou=iou)

    def train(self, config: TrainingConfig) -> Dict[str, Any]:
        """
        Train the model.

        Parameters
        ----------
        config : TrainingConfig
            Training configuration.

        Returns
        -------
        Dict[str, Any]
            Training results with model_path and metrics.
        """
        if not self._loaded:
            self.load()
        return self._model.train(config)

    def evaluate(self, config: EvaluationConfig) -> Dict[str, Any]:
        """
        Evaluate the model.

        Parameters
        ----------
        config : EvaluationConfig
            Evaluation configuration.

        Returns
        -------
        Dict[str, Any]
            Evaluation metrics.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        return self._model.evaluate(config)

    def draw_detections(
        self,
        image: np.ndarray,
        result: DetectionResult,
        show_labels: bool = True,
        show_confidence: bool = True,
        show_class: bool = True,
        annotator_type: str = "box",
        thickness: int = 2,
        text_scale: float = 0.5,
    ) -> np.ndarray:
        """
        Draw detection annotations on image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR).
        result : DetectionResult
            Detection results.
        show_labels : bool
            Show labels.
        show_confidence : bool
            Show confidence.
        show_class : bool
            Show class names.
        annotator_type : str
            Style: 'box', 'round_box', 'color'.
        thickness : int
            Line thickness.
        text_scale : float
            Text scale.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        return self._model.draw_detections(
            image,
            result,
            show_labels=show_labels,
            show_confidence=show_confidence,
            show_class=show_class,
            annotator_type=annotator_type,
            thickness=thickness,
            text_scale=text_scale,
        )

    def enable_slicing(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Enable slicing inference for high-resolution images."""
        self._model.enable_slicing(config)

    def disable_slicing(self) -> None:
        """Disable slicing inference."""
        self._model.disable_slicing()

    @property
    def model(self) -> BaseDetectionModel:
        """BaseDetectionModel: Underlying model for advanced usage."""
        return self._model

    def __repr__(self) -> str:
        status = "loaded" if self.is_loaded else "not loaded"
        return f"Detector('{self.model_source}', framework={self._framework.value}, {status})"


# Register default frameworks
def _create_ultralytics(model_name: str, **kwargs) -> BaseDetectionModel:
    from mirela_sdk.ai.detection.models.ultralytics import UltralyticsModel

    return UltralyticsModel(model_name, **kwargs)


def _create_transformers(model_name: str, **kwargs) -> BaseDetectionModel:
    from mirela_sdk.ai.detection.models.transformers import TransformersModel

    return TransformersModel(model_name, **kwargs)


def _create_rfdetr(model_name: str, **kwargs) -> BaseDetectionModel:
    from mirela_sdk.ai.detection.models.rfdetr import RFDETRModel

    return RFDETRModel(model_name, **kwargs)


Detector.register(Framework.ULTRALYTICS, _create_ultralytics)
Detector.register(Framework.TRANSFORMERS, _create_transformers)
Detector.register(Framework.RFDETR, _create_rfdetr)
