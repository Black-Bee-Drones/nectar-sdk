"""
Core data types for object detection.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import numpy as np

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
except ImportError:
    sv = None

try:
    from PIL import Image
except ImportError:
    Image = None


ImageType = Union[str, Path, np.ndarray, "torch.Tensor", "Image.Image"]
BatchImageType = Union[
    List[str],
    List[Path],
    List[np.ndarray],
    List["torch.Tensor"],
    List["Image.Image"],
    "torch.Tensor",
]


@dataclass
class Detection:
    """
    Single object detection result.

    Represents a detected object with bounding box, confidence score,
    class identification, and computed geometric properties.

    Parameters
    ----------
    xyxy : np.ndarray
        Bounding box coordinates as [x1, y1, x2, y2] in pixel coordinates.
    confidence : float
        Detection confidence score in range [0.0, 1.0].
    class_id : int
        Class identifier (zero-indexed).
    class_name : str, optional
        Human-readable class name. Defaults to empty string.

    Attributes
    ----------
    center : Tuple[float, float]
        Center point (x, y) of the bounding box.
    width : int
        Width of bounding box in pixels.
    height : int
        Height of bounding box in pixels.
    area : int
        Area of bounding box in square pixels.

    Examples
    --------
    >>> det = Detection(
    ...     xyxy=np.array([100, 100, 200, 200]),
    ...     confidence=0.95,
    ...     class_id=0,
    ...     class_name="person"
    ... )
    >>> det.center
    (150.0, 150.0)
    >>> det.area
    10000
    """

    xyxy: np.ndarray
    confidence: float
    class_id: int
    class_name: str = ""

    @property
    def center(self) -> Tuple[float, float]:
        """Tuple[float, float]: Center point (x, y) of the bounding box."""
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def width(self) -> int:
        """int: Width of bounding box in pixels."""
        return int(self.xyxy[2] - self.xyxy[0])

    @property
    def height(self) -> int:
        """int: Height of bounding box in pixels."""
        return int(self.xyxy[3] - self.xyxy[1])

    @property
    def area(self) -> int:
        """int: Area of bounding box in square pixels."""
        return self.width * self.height

    @property
    def bbox(self) -> List[int]:
        """List[int]: Bounding box as [x1, y1, x2, y2] integers."""
        return [int(x) for x in self.xyxy]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert detection to dictionary format.

        Returns
        -------
        Dict[str, Any]
            Dictionary with xyxy, confidence, class_id, and class_name.
        """
        return {
            "xyxy": (self.xyxy.tolist() if hasattr(self.xyxy, "tolist") else list(self.xyxy)),
            "confidence": float(self.confidence),
            "class_id": int(self.class_id),
            "class_name": self.class_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Detection":
        """
        Create Detection from dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Dictionary with xyxy, confidence, class_id, and optionally class_name.

        Returns
        -------
        Detection
            New Detection instance.
        """
        return cls(
            xyxy=np.array(data["xyxy"]),
            confidence=data["confidence"],
            class_id=data["class_id"],
            class_name=data.get("class_name", ""),
        )


@dataclass
class DetectionResult:
    """
    Container for detection results from a single image.

    Iteration, filtering, and conversion methods

    Parameters
    ----------
    detections : List[Detection]
        List of Detection objects.
    image : Optional[np.ndarray], optional
        Original image (BGR format). Defaults to None.
    inference_time : float, optional
        Inference time in seconds. Defaults to 0.0.
    image_path : Optional[str], optional
        Path to source image. Defaults to None.
    model_name : Optional[str], optional
        Name of the model used. Defaults to None.

    Examples
    --------
    >>> result = detector.detect(image)
    >>> len(result)  # Number of detections
    5
    >>> for det in result:
    ...     print(det.class_name, det.confidence)
    >>> persons = result.filter_by_class(["person"])
    >>> high_conf = result.filter_by_confidence(0.8)
    """

    detections: List[Detection] = field(default_factory=list)
    image: Optional[np.ndarray] = None
    inference_time: float = 0.0
    image_path: Optional[str] = None
    model_name: Optional[str] = None

    def __len__(self) -> int:
        """Return number of detections."""
        return len(self.detections)

    def __getitem__(self, idx: int) -> Detection:
        """Get detection by index."""
        return self.detections[idx]

    def __iter__(self) -> Iterator[Detection]:
        """Iterate over detections."""
        return iter(self.detections)

    def __bool__(self) -> bool:
        """Return True if there are any detections."""
        return len(self.detections) > 0

    def filter_by_class(self, class_names: List[str]) -> "DetectionResult":
        """
        Filter detections by class names.

        Parameters
        ----------
        class_names : List[str]
            List of class names to keep.

        Returns
        -------
        DetectionResult
            New DetectionResult with filtered detections.
        """
        filtered = [d for d in self.detections if d.class_name in class_names]
        return DetectionResult(
            detections=filtered,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def filter_by_confidence(self, threshold: float) -> "DetectionResult":
        """
        Filter detections by confidence threshold.

        Parameters
        ----------
        threshold : float
            Minimum confidence threshold.

        Returns
        -------
        DetectionResult
            New DetectionResult with filtered detections.
        """
        filtered = [d for d in self.detections if d.confidence >= threshold]
        return DetectionResult(
            detections=filtered,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def filter_by_class_id(self, class_ids: List[int]) -> "DetectionResult":
        """
        Filter detections by class IDs.

        Parameters
        ----------
        class_ids : List[int]
            List of class IDs to keep.

        Returns
        -------
        DetectionResult
            New DetectionResult with filtered detections.
        """
        filtered = [d for d in self.detections if d.class_id in class_ids]
        return DetectionResult(
            detections=filtered,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def to_supervision(self) -> "sv.Detections":
        """
        Convert to supervision Detections object.

        Returns
        -------
        sv.Detections
            Supervision Detections object.

        Raises
        ------
        ImportError
            If supervision is not installed.
        """
        if sv is None:
            raise ImportError("supervision is required. Install with: pip install supervision")

        if not self.detections:
            return sv.Detections.empty()

        return sv.Detections(
            xyxy=np.array([d.xyxy for d in self.detections]),
            confidence=np.array([d.confidence for d in self.detections]),
            class_id=np.array([d.class_id for d in self.detections]),
        )

    @classmethod
    def from_supervision(
        cls,
        detections: "sv.Detections",
        class_names: Dict[int, str],
        inference_time: float = 0.0,
        image_path: Optional[str] = None,
        model_name: Optional[str] = None,
        image: Optional[np.ndarray] = None,
    ) -> "DetectionResult":
        """
        Create DetectionResult from supervision Detections.

        Parameters
        ----------
        detections : sv.Detections
            Supervision Detections object.
        class_names : Dict[int, str]
            Mapping from class ID to class name.
        inference_time : float, optional
            Inference time in seconds.
        image_path : Optional[str], optional
            Path to source image.
        model_name : Optional[str], optional
            Name of the model used.
        image : Optional[np.ndarray], optional
            Original image.

        Returns
        -------
        DetectionResult
            New DetectionResult instance.
        """
        detection_list = []
        if detections is not None and len(detections) > 0:
            for i in range(len(detections)):
                xyxy = detections.xyxy[i]
                confidence = (
                    float(detections.confidence[i]) if detections.confidence is not None else 1.0
                )
                class_id = int(detections.class_id[i])
                class_name = class_names.get(class_id, f"class_{class_id}")

                detection_list.append(
                    Detection(
                        xyxy=xyxy,
                        confidence=confidence,
                        class_id=class_id,
                        class_name=class_name,
                    )
                )

        return cls(
            detections=detection_list,
            image=image,
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.

        Returns
        -------
        Dict[str, Any]
            Dictionary representation.
        """
        return {
            "detections": [d.to_dict() for d in self.detections],
            "inference_time": self.inference_time,
            "image_path": self.image_path,
            "model_name": self.model_name,
            "num_detections": len(self.detections),
        }


@dataclass
class DetectionInput:
    """
    Input for detection models, supporting single images and batches.

    Parameters
    ----------
    image : Union[ImageType, BatchImageType]
        Input image(s). Can be path, numpy array, tensor, PIL Image, or list.
    conf_threshold : float, optional
        Confidence threshold. Defaults to 0.5.
    iou_threshold : float, optional
        IoU threshold for NMS. Defaults to 0.5.
    device : Optional[str], optional
        Device to run inference on. Defaults to None (auto-detect).

    Attributes
    ----------
    is_batch : bool
        True if input contains multiple images.
    """

    image: Union[ImageType, BatchImageType]
    conf_threshold: float = 0.5
    iou_threshold: float = 0.5
    device: Optional[str] = None
    imgsz: Optional[int] = None

    @property
    def is_batch(self) -> bool:
        """bool: Check if input contains a batch of images."""
        if isinstance(self.image, (list, tuple)):
            return True
        if torch is not None and isinstance(self.image, torch.Tensor):
            return self.image.dim() == 4
        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.

        Returns
        -------
        Dict[str, Any]
            Dictionary with configuration values.
        """
        return {
            "conf_threshold": self.conf_threshold,
            "iou_threshold": self.iou_threshold,
            "device": self.device,
            "is_batch": self.is_batch,
        }


@dataclass
class Prediction:
    """
    Model prediction output for single image or batch.

    Unified prediction container supporting both supervision Detections
    and converted DetectionResult formats.

    Parameters
    ----------
    detections : Optional[sv.Detections], optional
        Single image detections (supervision format).
    batch_detections : Optional[List[sv.Detections]], optional
        Batch detections (supervision format).
    results : Optional[List[DetectionResult]], optional
        Converted detection results.
    inference_time : float, optional
        Total inference time in seconds.
    image_path : Optional[Union[str, List[str]]], optional
        Source image path(s).
    model_name : Optional[str], optional
        Name of the model used.
    """

    detections: Optional["sv.Detections"] = None
    batch_detections: Optional[List["sv.Detections"]] = None
    results: Optional[List[DetectionResult]] = None
    inference_time: float = 0.0
    image_path: Optional[Union[str, List[str]]] = None
    model_name: Optional[str] = None

    @property
    def is_batch(self) -> bool:
        """bool: Check if prediction is for a batch of images."""
        return self.batch_detections is not None

    @property
    def num_detections(self) -> int:
        """int: Total number of detections across all images."""
        if self.batch_detections is not None:
            return sum(len(d) for d in self.batch_detections)
        elif self.detections is not None:
            return len(self.detections)
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format.

        Returns
        -------
        Dict[str, Any]
            Dictionary representation.
        """
        result = {
            "inference_time": self.inference_time,
            "model_name": self.model_name,
            "is_batch": self.is_batch,
            "num_detections": self.num_detections,
        }

        if self.is_batch:
            result["image_paths"] = (
                self.image_path if isinstance(self.image_path, list) else [self.image_path]
            )
            if self.results:
                result["results"] = [r.to_dict() for r in self.results]
        else:
            result["image_path"] = self.image_path
            if self.results:
                result["results"] = self.results[0].to_dict() if self.results else None

        return result

    @classmethod
    def from_detections(
        cls,
        detections: "sv.Detections",
        class_names: Dict[int, str],
        inference_time: float,
        image_path: str,
        model_name: Optional[str] = None,
    ) -> "Prediction":
        """
        Create Prediction from supervision Detections.

        Parameters
        ----------
        detections : sv.Detections
            Supervision Detections object.
        class_names : Dict[int, str]
            Mapping from class ID to class name.
        inference_time : float
            Inference time in seconds.
        image_path : str
            Path to source image.
        model_name : Optional[str], optional
            Name of the model used.

        Returns
        -------
        Prediction
            New Prediction instance.
        """
        result = DetectionResult.from_supervision(
            detections=detections,
            class_names=class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )

        return cls(
            detections=detections,
            results=[result],
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )

    @classmethod
    def from_batch_detections(
        cls,
        batch_detections: List["sv.Detections"],
        class_names: Dict[int, str],
        inference_time: float,
        image_paths: List[str],
        model_name: Optional[str] = None,
    ) -> "Prediction":
        """
        Create Prediction from batch of supervision Detections.

        Parameters
        ----------
        batch_detections : List[sv.Detections]
            List of supervision Detections objects.
        class_names : Dict[int, str]
            Mapping from class ID to class name.
        inference_time : float
            Total inference time in seconds.
        image_paths : List[str]
            Paths to source images.
        model_name : Optional[str], optional
            Name of the model used.

        Returns
        -------
        Prediction
            New Prediction instance.
        """
        results = []
        for i, (dets, path) in enumerate(zip(batch_detections, image_paths)):
            result = DetectionResult.from_supervision(
                detections=dets,
                class_names=class_names,
                inference_time=inference_time / len(batch_detections),
                image_path=path,
                model_name=model_name,
            )
            results.append(result)

        return cls(
            batch_detections=batch_detections,
            results=results,
            inference_time=inference_time,
            image_path=image_paths,
            model_name=model_name,
        )
