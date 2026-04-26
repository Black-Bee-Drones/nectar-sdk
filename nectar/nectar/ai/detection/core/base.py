import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import numpy as np

if TYPE_CHECKING:
    pass

from nectar.ai.detection.core.configs import (
    EvaluationConfig,
    EvaluationMetrics,
    TrainingConfig,
    TrainingResult,
)
from nectar.ai.detection.core.exceptions import ModelNotLoadedError
from nectar.ai.detection.core.types import (
    DetectionInput,
    DetectionResult,
    Prediction,
)


class BaseDetectionModel(ABC):
    """
    Abstract base class for all detection models.

    Parameters
    ----------
    model_name : str
        Name or path of the model.
    framework : str
        Framework identifier ('ultralytics', 'transformers', 'rfdetr').

    Attributes
    ----------
    model_name : str
        Model name or path.
    framework : str
        Framework identifier.
    model : Any
        Underlying model instance (set after load_model()).
    class_names : Dict[int, str]
        Mapping from class ID to class name.
    slicing_config : Optional[SlicingConfig]
        Slicing configuration if enabled.

    Examples
    --------
    >>> class MyModel(BaseDetectionModel):
    ...     def load_model(self, path=None):
    ...         self.model = load_my_model(path or self.model_name)
    ...         self.class_names = {0: "object"}
    ...
    ...     def _predict_single(self, input):
    ...         # Run inference
    ...         pass
    ...
    ...     def train(self, config):
    ...         # Train model
    ...         pass
    ...
    ...     def save(self, path):
    ...         # Save model
    ...         pass
    """

    def __init__(self, model_name: str, framework: str = ""):
        """
        Initialize the detection model.

        Parameters
        ----------
        model_name : str
            Name or path of the model.
        framework : str, optional
            Framework identifier. Defaults to empty string.
        """
        self.model_name = model_name
        self.framework = framework
        self.model = None
        self.class_names: Dict[int, str] = {0: "object"}
        self.logger = logging.getLogger(self.__class__.__name__)

        # Slicing support
        self.slicing_config = None
        self._slicing_inference = None

    @property
    def is_loaded(self) -> bool:
        """bool: Check if model is loaded and ready for inference."""
        return self.model is not None

    @abstractmethod
    def load_model(self, model_path: Optional[str] = None) -> None:
        """
        Load model weights.

        Parameters
        ----------
        model_path : Optional[str], optional
            Path to model weights. Uses model_name if not provided.

        Raises
        ------
        FileNotFoundError
            If model file doesn't exist.
        RuntimeError
            If model loading fails.
        """
        pass

    @abstractmethod
    def _predict_single(self, detection_input: DetectionInput) -> Prediction:
        """
        Run inference on a single image.

        Parameters
        ----------
        detection_input : DetectionInput
            Detection input with single image.

        Returns
        -------
        Prediction
            Prediction results.
        """
        pass

    @abstractmethod
    def train(self, config: TrainingConfig) -> TrainingResult:
        """
        Train the model.

        Parameters
        ----------
        config : TrainingConfig
            Training configuration.

        Returns
        -------
        TrainingResult
            Training results including model path and metrics.
        """
        pass

    @abstractmethod
    def save(self, save_path: str) -> str:
        """
        Save model weights.

        Parameters
        ----------
        save_path : str
            Directory to save model.

        Returns
        -------
        str
            Path to saved model.
        """
        pass

    def _predict_batch(self, detection_input: DetectionInput) -> Prediction:
        """
        Run inference on a batch of images.

        Default implementation processes images sequentially.
        Override for framework-specific batch processing.

        Parameters
        ----------
        detection_input : DetectionInput
            Detection input with batch of images.

        Returns
        -------
        Prediction
            Batch prediction results.
        """
        try:
            import supervision as sv
        except ImportError:
            sv = None

        images = detection_input.image
        batch_detections = []
        image_paths = []
        total_time = 0.0

        for i, img in enumerate(images):
            single_input = DetectionInput(
                image=img,
                conf_threshold=detection_input.conf_threshold,
                iou_threshold=detection_input.iou_threshold,
                device=detection_input.device,
                imgsz=detection_input.imgsz,
            )

            start_time = time.time()
            result = self._predict_single(single_input)
            total_time += time.time() - start_time

            if result.detections is not None:
                batch_detections.append(result.detections)
            else:
                batch_detections.append(sv.Detections.empty() if sv else None)

            # Track image path
            if isinstance(img, (str, Path)):
                image_paths.append(str(img))
            else:
                image_paths.append(f"image_{i}")

        return Prediction.from_batch_detections(
            batch_detections=batch_detections,
            class_names=self.class_names,
            inference_time=total_time,
            image_paths=image_paths,
            model_name=self.model_name,
        )

    def predict(self, detection_input: DetectionInput) -> Prediction:
        """
        Run inference on image(s).

        Parameters
        ----------
        detection_input : DetectionInput
            Detection input with image(s) and parameters.

        Returns
        -------
        Prediction
            Prediction results.

        Raises
        ------
        ModelNotLoadedError
            If model is not loaded.

        Examples
        --------
        >>> # Single image
        >>> result = model.predict(DetectionInput(image=image, conf_threshold=0.5))
        >>> for det in result.results[0]:
        ...     print(det.class_name, det.confidence)

        >>> # Batch
        >>> result = model.predict(DetectionInput(image=[img1, img2]))
        >>> print(f"Batch inference time: {result.inference_time:.3f}s")
        """
        if not self.is_loaded:
            raise ModelNotLoadedError()

        # Check if slicing is enabled
        if self.slicing_config is not None and self._slicing_inference is not None:
            return self._predict_with_slicing(detection_input)

        if detection_input.is_batch:
            return self._predict_batch(detection_input)
        else:
            return self._predict_single(detection_input)

    def detect(
        self,
        image: Union[np.ndarray, str, Path],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> DetectionResult:
        """
        Convenience for single image detection.

        Parameters
        ----------
        image : Union[np.ndarray, str, Path]
            Input image (BGR format, path, or file path).
        conf : Optional[float], optional
            Confidence threshold. Defaults to 0.5.
        iou : Optional[float], optional
            IoU threshold. Defaults to 0.5.

        Returns
        -------
        DetectionResult
            Detection results.

        Examples
        --------
        >>> result = model.detect(image, conf=0.5)
        >>> for det in result:
        ...     print(f"{det.class_name}: {det.confidence:.2f}")
        """
        detection_input = DetectionInput(
            image=image,
            conf_threshold=conf or 0.5,
            iou_threshold=iou or 0.5,
        )
        prediction = self.predict(detection_input)

        if prediction.results:
            return prediction.results[0]
        return DetectionResult()

    def detect_batch(
        self,
        images: List[Union[np.ndarray, str, Path]],
        conf: Optional[float] = None,
        iou: Optional[float] = None,
    ) -> List[DetectionResult]:
        """
        Convenience method for batch detection.

        Parameters
        ----------
        images : List[Union[np.ndarray, str, Path]]
            List of input images.
        conf : Optional[float], optional
            Confidence threshold. Defaults to 0.5.
        iou : Optional[float], optional
            IoU threshold. Defaults to 0.5.

        Returns
        -------
        List[DetectionResult]
            List of detection results.
        """
        detection_input = DetectionInput(
            image=images,
            conf_threshold=conf or 0.5,
            iou_threshold=iou or 0.5,
        )
        prediction = self.predict(detection_input)

        if prediction.results:
            return prediction.results
        return [DetectionResult() for _ in images]

    def enable_slicing(
        self,
        slicing_config: Optional[Union[Dict[str, Any], Any]] = None,
    ) -> None:
        """
        Enable slicing-based inference.

        Parameters
        ----------
        slicing_config : Optional[Union[Dict, SlicingConfig]], optional
            Slicing configuration. Uses defaults if not provided.

        Examples
        --------
        >>> model.enable_slicing({
        ...     "strategy": "grid",
        ...     "slice_size": (640, 640),
        ...     "overlap_ratio": 0.2,
        ... })
        """
        from ..slicing import SlicingConfig, SlicingInference, SlicingStrategy

        if slicing_config is None:
            self.slicing_config = SlicingConfig(strategy=SlicingStrategy.GRID)
        elif isinstance(slicing_config, dict):
            self.slicing_config = SlicingConfig.from_dict(slicing_config)
        else:
            self.slicing_config = slicing_config

        self._slicing_inference = SlicingInference(self.slicing_config)
        self.logger.info(f"Slicing enabled with strategy: {self.slicing_config.strategy.value}")

    def disable_slicing(self) -> None:
        """Disable slicing-based inference."""
        self.slicing_config = None
        self._slicing_inference = None
        self.logger.info("Slicing disabled")

    def _predict_with_slicing(self, detection_input: DetectionInput) -> Prediction:
        """
        Run prediction with slicing enabled.

        Parameters
        ----------
        detection_input : DetectionInput
            Detection input.

        Returns
        -------
        Prediction
            Merged prediction from all slices.
        """
        if self._slicing_inference is None:
            raise RuntimeError("Slicing not enabled. Call enable_slicing() first.")

        import supervision as sv

        def inference_callback(image):
            """Callback for slice inference."""
            slice_input = DetectionInput(
                image=image,
                conf_threshold=detection_input.conf_threshold,
                iou_threshold=detection_input.iou_threshold,
                device=detection_input.device,
            )
            # Temporarily disable slicing for the callback
            temp_config = self.slicing_config
            temp_inference = self._slicing_inference
            self.slicing_config = None
            self._slicing_inference = None

            result = self.predict(slice_input)

            self.slicing_config = temp_config
            self._slicing_inference = temp_inference

            if result.is_batch:
                return (
                    result.batch_detections[0] if result.batch_detections else sv.Detections.empty()
                )
            return result.detections

        # Handle batch vs single
        if detection_input.is_batch:
            batch_detections = []
            image_paths = []
            total_time = 0.0

            for i, img in enumerate(detection_input.image):
                start_time = time.time()

                # Get initial detections for adaptive strategies
                initial_result = self._predict_single(
                    DetectionInput(
                        image=img,
                        conf_threshold=detection_input.conf_threshold,
                        iou_threshold=detection_input.iou_threshold,
                        device=detection_input.device,
                    )
                )

                merged = self._slicing_inference.run_sliced_inference(
                    img, inference_callback, initial_result.detections
                )
                total_time += time.time() - start_time

                batch_detections.append(merged)
                if isinstance(img, (str, Path)):
                    image_paths.append(str(img))
                else:
                    image_paths.append(f"image_{i}")

            return Prediction.from_batch_detections(
                batch_detections=batch_detections,
                class_names=self.class_names,
                inference_time=total_time,
                image_paths=image_paths,
                model_name=self.model_name,
            )
        else:
            start_time = time.time()

            initial_result = self._predict_single(detection_input)

            merged = self._slicing_inference.run_sliced_inference(
                detection_input.image,
                inference_callback,
                initial_result.detections,
            )
            inference_time = time.time() - start_time

            image_path = (
                str(detection_input.image)
                if isinstance(detection_input.image, (str, Path))
                else "image"
            )

            return Prediction.from_detections(
                detections=merged,
                class_names=self.class_names,
                inference_time=inference_time,
                image_path=image_path,
                model_name=self.model_name,
            )

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
            Input image (BGR format).
        result : DetectionResult
            Detection results to draw.
        show_labels : bool, optional
            Whether to show labels. Defaults to True.
        show_confidence : bool, optional
            Whether to show confidence. Defaults to True.
        show_class : bool, optional
            Whether to show class names. Defaults to True.
        annotator_type : str, optional
            Annotator type ('box', 'round_box', 'color'). Defaults to 'box'.
        thickness : int, optional
            Line thickness. Defaults to 2.
        text_scale : float, optional
            Text scale. Defaults to 0.5.

        Returns
        -------
        np.ndarray
            Annotated image.

        Examples
        --------
        >>> result = model.detect(image)
        >>> annotated = model.draw_detections(image, result)
        >>> cv2.imshow("Detections", annotated)
        """
        try:
            import supervision as sv
        except ImportError as e:
            raise ImportError(
                "supervision is required. Install with: pip install supervision"
            ) from e

        if not result.detections:
            return image.copy()

        detections = result.to_supervision()

        annotated = image.copy()

        if annotator_type == "round_box":
            box_annotator = sv.RoundBoxAnnotator(
                thickness=thickness,
                color=sv.ColorPalette.DEFAULT,
            )
        elif annotator_type == "color":
            box_annotator = sv.ColorAnnotator(
                color=sv.ColorPalette.DEFAULT,
                opacity=0.3,
            )
        else:
            box_annotator = sv.BoxAnnotator(
                thickness=thickness,
                color=sv.ColorPalette.DEFAULT,
            )

        annotated = box_annotator.annotate(scene=annotated, detections=detections)

        # Add labels
        if show_labels:
            labels = []
            for det in result.detections:
                label_parts = []
                if show_class and det.class_name:
                    label_parts.append(det.class_name)
                if show_confidence:
                    label_parts.append(f"{det.confidence:.2f}")
                labels.append(" ".join(label_parts) if label_parts else "")

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

    def evaluate(self, config: EvaluationConfig) -> EvaluationMetrics:
        """
        Evaluate the model on a dataset.

        Parameters
        ----------
        config : EvaluationConfig
            Evaluation configuration.

        Returns
        -------
        EvaluationMetrics
            Evaluation metrics.
        """
        from ..evaluation import ObjectDetectionEvaluator

        evaluator = ObjectDetectionEvaluator(self, config)
        return evaluator.evaluate()

    @classmethod
    def from_pretrained(
        cls,
        model_name: str,
        **kwargs,
    ) -> "BaseDetectionModel":
        """
        Create model from pretrained weights.

        Parameters
        ----------
        model_name : str
            Model name or path.
        **kwargs
            Additional configuration.

        Returns
        -------
        BaseDetectionModel
            Loaded model instance.
        """
        model = cls(model_name, **kwargs)
        model.load_model()
        return model
