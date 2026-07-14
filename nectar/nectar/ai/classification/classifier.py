"""Unified classifier with factory pattern."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np

from nectar.ai.classification.core.base import BaseClassificationModel
from nectar.ai.classification.core.configs import (
    ClsEvaluationConfig,
    ClsEvaluationMetrics,
    ClsTrainingConfig,
)
from nectar.ai.classification.core.exceptions import ModelNotLoadedError
from nectar.ai.classification.core.types import ClassificationResult
from nectar.ai.core.framework import Framework

logger = logging.getLogger(__name__)

BuilderFunc = Callable[..., BaseClassificationModel]


class Classifier:
    """
    Unified classifier with factory pattern for creating model instances.

    Supports auto-detection from model name or explicit framework specification.

    Parameters
    ----------
    model_source : str
        Model path, name, or HuggingFace ID.
    framework : Optional[Union[Framework, str]]
        Explicit framework. Auto-detects if not provided.
    device : str
        Device ('auto', 'cpu', 'cuda', '0').
    topk : int
        Default number of top predictions to return.
    **kwargs
        Additional arguments passed to the model constructor.

    Examples
    --------
    >>> classifier = Classifier("yolo26n-cls.pt")
    >>> classifier.load()
    >>> result = classifier.classify(image)
    """

    _builders: Dict[str, BuilderFunc] = {}

    def __init__(
        self,
        model_source: str,
        framework: Optional[Union[Framework, str]] = None,
        device: str = "auto",
        topk: int = 5,
        hf_token: Optional[str] = None,
        **kwargs,
    ):
        self.model_source = model_source
        self.device = device
        self.topk = topk
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

        logger.info("Created %s classifier: %s", self._framework.value, model_source)

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

        if any(x in source_lower for x in ["-cls", "_cls", "classify", "classification"]):
            if any(
                x in source_lower
                for x in [
                    "vit",
                    "beit",
                    "swin",
                    "convnext",
                    "resnet",
                    "efficientnet",
                    "google/",
                    "facebook/",
                    "microsoft/",
                ]
            ):
                return Framework.TRANSFORMERS
            return Framework.ULTRALYTICS

        if any(
            x in source_lower
            for x in [
                "vit",
                "beit",
                "swin",
                "convnext",
                "resnet",
                "efficientnet",
                "google/",
                "facebook/",
                "microsoft/",
            ]
        ):
            return Framework.TRANSFORMERS

        if any(x in source_lower for x in ["yolo", "ultralytics"]):
            return Framework.ULTRALYTICS

        return Framework.ULTRALYTICS

    @classmethod
    def _create_model(
        cls, framework: Framework, model_name: str, **kwargs
    ) -> BaseClassificationModel:
        """Create model instance using registered builder."""
        key = framework.value
        builder = cls._builders.get(key)
        if not builder:
            available = ", ".join(cls._builders.keys()) or "(none)"
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
                    from nectar.ai.core.model_loader import ModelLoader

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

    def classify(
        self,
        image: Union[np.ndarray, str, Path],
        topk: Optional[int] = None,
    ) -> ClassificationResult:
        """Run classification on a single image."""
        if not self.is_loaded:
            raise ModelNotLoadedError()
        return self._model.classify(image, topk=topk if topk is not None else self.topk)

    def classify_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        topk: Optional[int] = None,
    ) -> List[ClassificationResult]:
        """Run classification on multiple images."""
        if not self.is_loaded:
            raise ModelNotLoadedError()
        return self._model.classify_batch(images, topk=topk if topk is not None else self.topk)

    def train(self, config: ClsTrainingConfig) -> Dict[str, Any]:
        """Train the model."""
        if not self._loaded:
            self.load()
        return self._model.train(config)

    def evaluate(self, config: ClsEvaluationConfig) -> ClsEvaluationMetrics:
        """Evaluate the model."""
        if not self.is_loaded:
            raise ModelNotLoadedError()
        return self._model.evaluate(config)

    def draw_classification(
        self,
        image: np.ndarray,
        result: ClassificationResult,
        show_confidence: bool = True,
        topk: int = 3,
        text_scale: float = 0.6,
        thickness: int = 2,
    ) -> np.ndarray:
        """Overlay top-k class labels on the image."""
        return self._model.draw_classification(
            image,
            result,
            show_confidence=show_confidence,
            topk=topk,
            text_scale=text_scale,
            thickness=thickness,
        )

    @property
    def model(self) -> BaseClassificationModel:
        """Underlying model for advanced usage."""
        return self._model

    def __repr__(self) -> str:
        status = "loaded" if self.is_loaded else "not loaded"
        return f"Classifier('{self.model_source}', framework={self._framework.value}, {status})"


def _create_ultralytics_cls(model_name: str, **kwargs) -> BaseClassificationModel:
    from nectar.ai.classification.models.ultralytics import UltralyticsClsModel

    return UltralyticsClsModel(model_name, **kwargs)


def _create_transformers_cls(model_name: str, **kwargs) -> BaseClassificationModel:
    from nectar.ai.classification.models.transformers import TransformersClsModel

    return TransformersClsModel(model_name, **kwargs)


Classifier.register(Framework.ULTRALYTICS, _create_ultralytics_cls)
Classifier.register(Framework.TRANSFORMERS, _create_transformers_cls)
