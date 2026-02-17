from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None

from .configs import EvaluationConfig, EvaluationMetrics, TrainingConfig, TrainingResult
from .types import DetectionResult


@runtime_checkable
class DetectorProtocol(Protocol):
    """
    Protocol for detection model inference.

    Any class implementing this protocol can be used for object detection.

    Attributes
    ----------
    is_loaded : bool
        Whether the model is loaded and ready for inference.
    class_names : Dict[int, str]
        Mapping from class ID to class name.

    Methods
    -------
    load() -> bool
        Load the model.
    detect(image, conf) -> DetectionResult
        Run detection on a single image.
    detect_batch(images, conf) -> List[DetectionResult]
        Run detection on a batch of images.
    draw_detections(image, result) -> np.ndarray
        Draw detection annotations on image.
    """

    @property
    def is_loaded(self) -> bool:
        """bool: Whether the model is loaded."""
        ...

    @property
    def class_names(self) -> Dict[int, str]:
        """Dict[int, str]: Class ID to name mapping."""
        ...

    def load(self) -> bool:
        """
        Load the model.

        Returns
        -------
        bool
            True if loaded successfully.
        """
        ...

    def detect(
        self,
        image: np.ndarray,
        conf: Optional[float] = None,
    ) -> DetectionResult:
        """
        Run detection on a single image.

        Parameters
        ----------
        image : np.ndarray
            Input image (BGR format).
        conf : Optional[float], optional
            Confidence threshold override.

        Returns
        -------
        DetectionResult
            Detection results.
        """
        ...

    def detect_batch(
        self,
        images: List[np.ndarray],
        conf: Optional[float] = None,
    ) -> List[DetectionResult]:
        """
        Run detection on a batch of images.

        Parameters
        ----------
        images : List[np.ndarray]
            List of input images (BGR format).
        conf : Optional[float], optional
            Confidence threshold override.

        Returns
        -------
        List[DetectionResult]
            List of detection results.
        """
        ...

    def draw_detections(
        self,
        image: np.ndarray,
        result: DetectionResult,
        show_labels: bool = True,
        show_confidence: bool = True,
    ) -> np.ndarray:
        """
        Draw detection annotations on image.

        Parameters
        ----------
        image : np.ndarray
            Input image.
        result : DetectionResult
            Detection results to draw.
        show_labels : bool, optional
            Whether to show labels. Defaults to True.
        show_confidence : bool, optional
            Whether to show confidence. Defaults to True.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        ...


@runtime_checkable
class TrainableProtocol(Protocol):
    """
    Protocol for trainable detection models.

    Classes implementing this protocol can be trained and evaluated.

    Methods
    -------
    train(config) -> TrainingResult
        Train the model.
    evaluate(config) -> EvaluationMetrics
        Evaluate the model.
    save(path) -> str
        Save model weights.
    """

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
            Training results and metrics.
        """
        ...

    def evaluate(self, config: EvaluationConfig) -> EvaluationMetrics:
        """
        Evaluate the model.

        Parameters
        ----------
        config : EvaluationConfig
            Evaluation configuration.

        Returns
        -------
        EvaluationMetrics
            Evaluation metrics.
        """
        ...

    def save(self, path: str) -> str:
        """
        Save model weights.

        Parameters
        ----------
        path : str
            Directory to save model.

        Returns
        -------
        str
            Path to saved model.
        """
        ...


@runtime_checkable
class MergingStrategy(Protocol):
    """
    Protocol for post-processing merging strategies.

    Strategies merge overlapping detections using various algorithms
    (NMS, Soft NMS, WBF, NMM, etc.).

    Attributes
    ----------
    name : str
        Strategy name.

    Methods
    -------
    merge_boxes(detections) -> Tuple[sv.Detections, List[List[int]], int]
        Merge overlapping detections.
    """

    @property
    def name(self) -> str:
        """str: Strategy name."""
        ...

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """
        Merge overlapping bounding boxes.

        Parameters
        ----------
        detections : sv.Detections
            Input detections to merge.

        Returns
        -------
        Tuple[sv.Detections, List[List[int]], int]
            Tuple of:
            - Merged detections
            - Merge groups (list of lists of original indices)
            - Number of boxes merged
        """
        ...


@runtime_checkable
class FilterStrategy(Protocol):
    """
    Protocol for detection filtering strategies.

    Filters remove detections based on various criteria
    (confidence, area, aspect ratio, etc.).

    Attributes
    ----------
    name : str
        Strategy name.

    Methods
    -------
    filter_detections(detections) -> sv.Detections
        Filter detections.
    """

    @property
    def name(self) -> str:
        """str: Strategy name."""
        ...

    def filter_detections(self, detections: "sv.Detections") -> "sv.Detections":
        """
        Filter detections.

        Parameters
        ----------
        detections : sv.Detections
            Input detections to filter.

        Returns
        -------
        sv.Detections
            Filtered detections.
        """
        ...


@runtime_checkable
class TrainingCallback(Protocol):
    """
    Protocol for training callbacks.

    Callbacks receive notifications at various points during training
    for logging, checkpointing, early stopping, etc.

    Attributes
    ----------
    name : str
        Callback name.

    Methods
    -------
    on_train_start(trainer)
        Called at training start.
    on_train_end(trainer, metrics)
        Called at training end.
    on_epoch_start(trainer, epoch)
        Called at epoch start.
    on_epoch_end(trainer, epoch, metrics)
        Called at epoch end.
    on_batch_start(trainer, batch)
        Called at batch start.
    on_batch_end(trainer, batch, loss)
        Called at batch end.
    """

    @property
    def name(self) -> str:
        """str: Callback name."""
        ...

    def on_train_start(self, trainer: Any) -> None:
        """Called at training start."""
        ...

    def on_train_end(self, trainer: Any, metrics: Dict[str, float]) -> None:
        """Called at training end."""
        ...

    def on_epoch_start(self, trainer: Any, epoch: int) -> None:
        """Called at epoch start."""
        ...

    def on_epoch_end(self, trainer: Any, epoch: int, metrics: Dict[str, float]) -> None:
        """Called at epoch end."""
        ...

    def on_batch_start(self, trainer: Any, batch: int) -> None:
        """Called at batch start."""
        ...

    def on_batch_end(self, trainer: Any, batch: int, loss: float) -> None:
        """Called at batch end."""
        ...

    def on_validation_start(self, trainer: Any) -> None:
        """Called at validation start."""
        ...

    def on_validation_end(self, trainer: Any, metrics: Dict[str, float]) -> None:
        """Called at validation end."""
        ...


@runtime_checkable
class SlicerProtocol(Protocol):
    """
    Protocol for image slicing strategies.

    Slicers divide images into smaller patches for inference
    on high-resolution images.

    Methods
    -------
    slice_image(image, detections) -> List[Dict]
        Slice image into patches.
    """

    def slice_image(
        self,
        image: np.ndarray,
        detections: Optional["sv.Detections"] = None,
    ) -> List[Dict[str, Any]]:
        """
        Slice image into patches.

        Parameters
        ----------
        image : np.ndarray
            Input image.
        detections : Optional[sv.Detections], optional
            Optional initial detections for adaptive slicing.

        Returns
        -------
        List[Dict[str, Any]]
            List of slice dictionaries with:
            - "image": Sliced image array
            - "offset": (x, y) offset in original image
            - "size": (width, height) of slice
            - "scale": Scale factor if resized
        """
        ...


@runtime_checkable
class DatasetProtocol(Protocol):
    """
    Protocol for detection datasets.

    Datasets provide access to images and annotations for
    training and evaluation.

    Attributes
    ----------
    classes : List[str]
        List of class names.

    Methods
    -------
    __len__() -> int
        Return number of samples.
    __getitem__(idx) -> Tuple
        Get sample by index.
    """

    @property
    def classes(self) -> List[str]:
        """List[str]: Class names."""
        ...

    def __len__(self) -> int:
        """Return number of samples."""
        ...

    def __getitem__(self, idx: int) -> Tuple[str, np.ndarray, "sv.Detections"]:
        """
        Get sample by index.

        Parameters
        ----------
        idx : int
            Sample index.

        Returns
        -------
        Tuple[str, np.ndarray, sv.Detections]
            Tuple of (image_path, image, annotations).
        """
        ...
