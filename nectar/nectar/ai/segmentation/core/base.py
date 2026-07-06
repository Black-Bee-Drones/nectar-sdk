"""Abstract base class for all segmentation models."""

import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Union

import numpy as np

if TYPE_CHECKING:
    pass

from nectar.ai.detection.core.configs import TrainingResult
from nectar.ai.segmentation.core.configs import (
    SegEvaluationConfig,
    SegEvaluationMetrics,
    SegTrainingConfig,
)
from nectar.ai.segmentation.core.exceptions import ModelNotLoadedError
from nectar.ai.segmentation.core.types import (
    SegmentationInput,
    SegmentationResult,
    SegPrediction,
)


class BaseSegmentationModel(ABC):
    """
    Abstract base class for all segmentation models.

    Parameters
    ----------
    model_name : str
        Name or path of the model.
    framework : str
        Framework identifier ('ultralytics', 'transformers', 'rfdetr').
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
        pass

    @abstractmethod
    def _predict_single(self, seg_input: SegmentationInput) -> SegPrediction:
        """Run inference on a single image."""
        pass

    @abstractmethod
    def train(self, config: SegTrainingConfig) -> TrainingResult:
        """Train the model."""
        pass

    @abstractmethod
    def save(self, save_path: str) -> str:
        """Save model weights."""
        pass

    def _predict_batch(self, seg_input: SegmentationInput) -> SegPrediction:
        """Run inference on a batch of images (default: sequential)."""
        try:
            import supervision as sv
        except ImportError:
            sv = None

        images = seg_input.image
        batch_detections = []
        image_paths = []
        total_time = 0.0

        for i, img in enumerate(images):
            single_input = SegmentationInput(
                image=img,
                conf_threshold=seg_input.conf_threshold,
                iou_threshold=seg_input.iou_threshold,
                device=seg_input.device,
                imgsz=seg_input.imgsz,
            )
            start_time = time.time()
            result = self._predict_single(single_input)
            total_time += time.time() - start_time

            if result.detections is not None:
                batch_detections.append(result.detections)
            else:
                batch_detections.append(sv.Detections.empty() if sv else None)

            if isinstance(img, (str, Path)):
                image_paths.append(str(img))
            else:
                image_paths.append(f"image_{i}")

        return SegPrediction.from_batch_detections(
            batch_detections=batch_detections,
            class_names=self.class_names,
            inference_time=total_time,
            image_paths=image_paths,
            model_name=self.model_name,
        )

    def predict(self, seg_input: SegmentationInput) -> SegPrediction:
        """
        Run inference on image(s).

        Parameters
        ----------
        seg_input : SegmentationInput
            Segmentation input with image(s) and parameters.

        Returns
        -------
        SegPrediction
            Prediction results.
        """
        if not self.is_loaded:
            raise ModelNotLoadedError()

        if seg_input.is_batch:
            return self._predict_batch(seg_input)
        return self._predict_single(seg_input)

    def segment(
        self,
        image: Union[np.ndarray, str, Path],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> SegmentationResult:
        """
        Convenience method for single image segmentation.

        Parameters
        ----------
        image : Union[np.ndarray, str, Path]
            Input image.
        conf : Optional[float]
            Confidence threshold.
        iou : Optional[float]
            IoU threshold.

        Returns
        -------
        SegmentationResult
            Segmentation results.
        """
        seg_input = SegmentationInput(
            image=image,
            conf_threshold=conf or 0.5,
            iou_threshold=iou or 0.5,
        )
        prediction = self.predict(seg_input)
        if prediction.results:
            return prediction.results[0]
        return SegmentationResult()

    def segment_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> List[SegmentationResult]:
        """Convenience method for batch segmentation."""
        seg_input = SegmentationInput(
            image=images,
            conf_threshold=conf or 0.5,
            iou_threshold=iou or 0.5,
        )
        prediction = self.predict(seg_input)
        if prediction.results:
            return prediction.results
        return [SegmentationResult() for _ in images]

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
        """
        Draw segmentation annotations on image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR format).
        result : SegmentationResult
            Segmentation results.
        show_labels : bool
            Show labels.
        show_confidence : bool
            Show confidence scores.
        show_masks : bool
            Show mask overlays.
        show_boxes : bool
            Show bounding boxes.
        opacity : float
            Mask overlay opacity.
        text_scale : float
            Text scale.
        thickness : int
            Line thickness.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        try:
            import supervision as sv
        except ImportError as e:
            raise ImportError(
                "supervision is required. Install with: pip install supervision"
            ) from e

        if not result.segmentations:
            return image.copy()

        detections = result.to_supervision()
        annotated = image.copy()

        if show_masks:
            mask_annotator = sv.MaskAnnotator(opacity=opacity)
            annotated = mask_annotator.annotate(scene=annotated, detections=detections)

        if show_boxes:
            box_annotator = sv.BoxAnnotator(thickness=thickness)
            annotated = box_annotator.annotate(scene=annotated, detections=detections)

        if show_labels:
            labels = []
            for seg in result.segmentations:
                parts = []
                if seg.class_name:
                    parts.append(seg.class_name)
                if show_confidence:
                    parts.append(f"{seg.confidence:.2f}")
                labels.append(" ".join(parts) if parts else "")

            if any(labels):
                label_annotator = sv.LabelAnnotator(
                    text_scale=text_scale,
                    text_thickness=max(1, int(thickness * 0.5)),
                )
                annotated = label_annotator.annotate(
                    scene=annotated,
                    detections=detections,
                    labels=labels,
                )

        return annotated

    def evaluate(self, config: SegEvaluationConfig) -> SegEvaluationMetrics:
        """Evaluate the model on a dataset."""
        from nectar.ai.segmentation.evaluation.evaluator import SegmentationEvaluator

        evaluator = SegmentationEvaluator(self, config)
        return evaluator.evaluate()

    @classmethod
    def from_pretrained(cls, model_name: str, **kwargs) -> "BaseSegmentationModel":
        """Create model from pretrained weights."""
        model = cls(model_name, **kwargs)
        model.load_model()
        return model
