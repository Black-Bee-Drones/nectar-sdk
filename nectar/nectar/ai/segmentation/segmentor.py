"""Unified segmentor with factory pattern."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from nectar.ai.detection.detector import Framework
from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import SegEvaluationConfig, SegTrainingConfig
from nectar.ai.segmentation.core.types import SegmentationResult

logger = logging.getLogger(__name__)

BuilderFunc = Callable[..., BaseSegmentationModel]


class Segmentor:
    """
    Unified segmentor with factory pattern for creating model instances.

    Supports auto-detection from model name or explicit framework specification.

    Parameters
    ----------
    model_source : str
        Model path, name, or HuggingFace ID.
    framework : Optional[Union[Framework, str]]
        Explicit framework. Auto-detects if not provided.
    device : str
        Device ('auto', 'cpu', 'cuda', '0').
    confidence_threshold : float
        Default confidence threshold.
    **kwargs
        Additional arguments passed to the model constructor.

    Examples
    --------
    >>> segmentor = Segmentor("yolov8n-seg.pt")
    >>> segmentor.load()
    >>> result = segmentor.segment(image)
    """

    _builders: Dict[str, BuilderFunc] = {}

    def __init__(
        self,
        model_source: str,
        framework: Optional[Union[Framework, str]] = None,
        device: str = "auto",
        confidence_threshold: float = 0.25,
        hf_token: Optional[str] = None,
        **kwargs,
    ):
        self.model_source = model_source
        self.device = device
        self.confidence_threshold = confidence_threshold
        self._hf_token = hf_token
        self._kwargs = kwargs

        if framework is not None:
            if isinstance(framework, str):
                framework = Framework(framework.lower())
            self._framework = framework
        else:
            self._framework = self._detect_framework(model_source)

        self._model = self._create_model(self._framework, model_source, **kwargs)
        self._loaded = False

        logger.info("Created %s segmentor: %s", self._framework.value, model_source)

    @classmethod
    def register(cls, framework: Union[Framework, str], builder: BuilderFunc) -> None:
        """Register a framework builder."""
        key = framework.value if isinstance(framework, Framework) else framework.lower()
        cls._builders[key] = builder

    @classmethod
    def available_frameworks(cls) -> List[str]:
        """Get registered frameworks."""
        return list(cls._builders.keys())

    @classmethod
    def _detect_framework(cls, source: str) -> Framework:
        """Auto-detect framework from model source."""
        source_lower = source.lower()

        if "rfdetr" in source_lower and "seg" in source_lower:
            return Framework.RFDETR
        if any(x in source_lower for x in ["-seg", "_seg"]):
            if any(x in source_lower for x in ["yolo", "ultralytics"]):
                return Framework.ULTRALYTICS
        if any(x in source_lower for x in ["mask2former", "maskformer", "segformer", "segmentation"]):
            return Framework.TRANSFORMERS
        if "rfdetr" in source_lower:
            return Framework.RFDETR
        if any(x in source_lower for x in ["facebook/", "microsoft/", "nvidia/"]):
            return Framework.TRANSFORMERS
        return Framework.ULTRALYTICS

    @classmethod
    def _create_model(
        cls, framework: Framework, model_name: str, **kwargs
    ) -> BaseSegmentationModel:
        """Create model instance using registered builder."""
        key = framework.value
        builder = cls._builders.get(key)
        if not builder:
            available = ", ".join(cls._builders.keys())
            raise ValueError(f"Unknown framework: '{key}'. Available: {available}")
        return builder(model_name, **kwargs)

    @property
    def framework(self) -> Framework:
        return self._framework

    def load(self, model_path: Optional[str] = None) -> bool:
        """Load the model."""
        try:
            if model_path is None and self._framework == Framework.ULTRALYTICS:
                if "/" in self.model_source and ":" in self.model_source:
                    from nectar.ai.detection.models.model_loader import ModelLoader

                    model_path = ModelLoader.load(self.model_source, token=self._hf_token)

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
        return self._loaded and self._model.is_loaded

    @property
    def class_names(self) -> Dict[int, str]:
        return getattr(self._model, "class_names", {})

    def segment(
        self,
        image: Union[np.ndarray, str, Path],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> SegmentationResult:
        """Run segmentation on a single image."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        conf = conf if conf is not None else self.confidence_threshold
        iou = iou if iou is not None else 0.5
        return self._model.segment(image, conf=conf, iou=iou)

    def segment_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> List[SegmentationResult]:
        """Run segmentation on multiple images."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        conf = conf if conf is not None else self.confidence_threshold
        iou = iou if iou is not None else 0.5
        return self._model.segment_batch(images, conf=conf, iou=iou)

    def train(self, config: SegTrainingConfig) -> Dict[str, Any]:
        """Train the model."""
        if not self._loaded:
            self.load()
        return self._model.train(config)

    def evaluate(self, config: SegEvaluationConfig) -> Dict[str, Any]:
        """Evaluate the model."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        return self._model.evaluate(config)

    def draw_segmentations(
        self,
        image: np.ndarray,
        result: SegmentationResult,
        show_labels: bool = True,
        show_confidence: bool = True,
        show_masks: bool = True,
        show_boxes: bool = False,
        opacity: float = 0.4,
        text_scale: float = 0.5,
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw segmentation annotations on image."""
        return self._model.draw_segmentations(
            image,
            result,
            show_labels=show_labels,
            show_confidence=show_confidence,
            show_masks=show_masks,
            show_boxes=show_boxes,
            opacity=opacity,
            text_scale=text_scale,
            thickness=thickness,
        )

    @property
    def model(self) -> BaseSegmentationModel:
        """Underlying model for advanced usage."""
        return self._model

    def __repr__(self) -> str:
        status = "loaded" if self.is_loaded else "not loaded"
        return f"Segmentor('{self.model_source}', framework={self._framework.value}, {status})"


def _create_ultralytics_seg(model_name: str, **kwargs) -> BaseSegmentationModel:
    from nectar.ai.segmentation.models.ultralytics import UltralyticsSegModel

    return UltralyticsSegModel(model_name, **kwargs)


def _create_transformers_seg(model_name: str, **kwargs) -> BaseSegmentationModel:
    from nectar.ai.segmentation.models.transformers import TransformersSegModel

    return TransformersSegModel(model_name, **kwargs)


def _create_rfdetr_seg(model_name: str, **kwargs) -> BaseSegmentationModel:
    from nectar.ai.segmentation.models.rfdetr import RFDETRSegModel

    return RFDETRSegModel(model_name, **kwargs)


Segmentor.register(Framework.ULTRALYTICS, _create_ultralytics_seg)
Segmentor.register(Framework.TRANSFORMERS, _create_transformers_seg)
Segmentor.register(Framework.RFDETR, _create_rfdetr_seg)
