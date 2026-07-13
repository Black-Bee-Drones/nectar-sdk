"""Abstract base class for all classification models."""

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from nectar.ai.classification.core.configs import (
    ClsEvaluationConfig,
    ClsEvaluationMetrics,
    ClsTrainingConfig,
)
from nectar.ai.classification.core.exceptions import ModelNotLoadedError
from nectar.ai.classification.core.types import (
    ClassificationInput,
    ClassificationResult,
    ClsPrediction,
)


class BaseClassificationModel(ABC):
    """
    Abstract base class for all classification models.

    Parameters
    ----------
    model_name : str
        Name or path of the model.
    framework : str
        Framework identifier ('ultralytics', 'transformers').
    """

    def __init__(self, model_name: str, framework: str = ""):
        self.model_name = model_name
        self.framework = framework
        self.model = None
        self.class_names: Dict[int, str] = {0: "object"}
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    @abstractmethod
    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load model weights."""

    @abstractmethod
    def _predict_single(self, cls_input: ClassificationInput) -> ClsPrediction:
        """Run inference on a single image."""

    @abstractmethod
    def train(self, config: ClsTrainingConfig) -> Dict[str, Any]:
        """Train the model."""

    @abstractmethod
    def save(self, save_path: str) -> str:
        """Save model weights."""

    def _predict_batch(self, cls_input: ClassificationInput) -> ClsPrediction:
        """Run inference on a batch of images (default: sequential)."""
        images = cls_input.image
        results = []
        image_paths = []
        total_time = 0.0

        for i, img in enumerate(images):
            single_input = ClassificationInput(
                image=img,
                device=cls_input.device,
                topk=cls_input.topk,
                imgsz=cls_input.imgsz,
            )
            start_time = time.time()
            prediction = self._predict_single(single_input)
            total_time += time.time() - start_time

            if prediction.result is not None:
                results.append(prediction.result)
            elif prediction.results:
                results.append(prediction.results[0])
            else:
                results.append(ClassificationResult())

            if isinstance(img, (str, Path)):
                image_paths.append(str(img))
            else:
                image_paths.append(f"image_{i}")

        return ClsPrediction.from_batch_results(
            results=results,
            inference_time=total_time,
            image_paths=image_paths,
            model_name=self.model_name,
        )

    def predict(self, cls_input: ClassificationInput) -> ClsPrediction:
        """Run inference on image(s)."""
        if not self.is_loaded:
            raise ModelNotLoadedError()

        if cls_input.is_batch:
            return self._predict_batch(cls_input)
        return self._predict_single(cls_input)

    def classify(
        self,
        image: Union[np.ndarray, str, Path],
        topk: int = 5,
    ) -> ClassificationResult:
        """Convenience method for single-image classification."""
        cls_input = ClassificationInput(image=image, topk=topk)
        prediction = self.predict(cls_input)
        if prediction.result is not None:
            return prediction.result
        if prediction.results:
            return prediction.results[0]
        return ClassificationResult()

    def classify_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        topk: int = 5,
    ) -> List[ClassificationResult]:
        """Convenience method for batch classification."""
        cls_input = ClassificationInput(image=images, topk=topk)
        prediction = self.predict(cls_input)
        if prediction.results:
            return prediction.results
        return [ClassificationResult() for _ in images]

    def draw_classification(
        self,
        image: np.ndarray,
        result: ClassificationResult,
        show_confidence: bool = True,
        topk: int = 3,
        text_scale: float = 0.6,
        thickness: int = 2,
    ) -> np.ndarray:
        """
        Overlay top-k class labels on the image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR).
        result : ClassificationResult
            Classification results.
        show_confidence : bool
            Include confidence scores.
        topk : int
            Number of labels to draw.
        text_scale : float
            OpenCV text scale.
        thickness : int
            Text thickness.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        try:
            import cv2
        except ImportError as e:
            raise ImportError("opencv is required for draw_classification") from e

        annotated = image.copy()
        y = 30
        for pred in result.predictions[:topk]:
            label = pred.class_name or f"class_{pred.class_id}"
            if show_confidence:
                label = f"{label}: {pred.confidence:.2f}"
            cv2.putText(
                annotated,
                label,
                (10, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                text_scale,
                (0, 255, 0),
                thickness,
                cv2.LINE_AA,
            )
            y += int(28 * text_scale) + 8
        return annotated

    def evaluate(self, config: ClsEvaluationConfig) -> ClsEvaluationMetrics:
        """Evaluate the model on a dataset."""
        from nectar.ai.classification.evaluation.evaluator import ClassificationEvaluator

        evaluator = ClassificationEvaluator(self, config)
        return evaluator.evaluate()

    @classmethod
    def from_pretrained(cls, model_name: str, **kwargs) -> "BaseClassificationModel":
        """Create model from pretrained weights."""
        model = cls(model_name, **kwargs)
        model.load_model()
        return model
