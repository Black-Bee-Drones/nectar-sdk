"""Core data types for image segmentation."""

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

try:
    import cv2
except ImportError:
    cv2 = None

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
class Segmentation:
    """
    Single instance segmentation result.

    Parameters
    ----------
    xyxy : np.ndarray
        Bounding box coordinates as [x1, y1, x2, y2] in pixel coordinates.
    confidence : float
        Detection confidence score in range [0.0, 1.0].
    class_id : int
        Class identifier (zero-indexed).
    class_name : str, optional
        Human-readable class name.
    mask : Optional[np.ndarray]
        Binary mask of shape (H, W) with dtype bool or uint8.
    """

    xyxy: np.ndarray
    confidence: float
    class_id: int
    class_name: str = ""
    mask: Optional[np.ndarray] = None

    @property
    def center(self) -> Tuple[float, float]:
        """Center point (x, y) of the bounding box."""
        x1, y1, x2, y2 = self.xyxy
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def width(self) -> int:
        """Width of bounding box in pixels."""
        return int(self.xyxy[2] - self.xyxy[0])

    @property
    def height(self) -> int:
        """Height of bounding box in pixels."""
        return int(self.xyxy[3] - self.xyxy[1])

    @property
    def area(self) -> int:
        """Area of bounding box in square pixels."""
        return self.width * self.height

    @property
    def mask_area(self) -> int:
        """Area of the mask in pixels (number of True pixels)."""
        if self.mask is None:
            return 0
        return int(np.sum(self.mask > 0))

    @property
    def bbox(self) -> List[int]:
        """Bounding box as [x1, y1, x2, y2] integers."""
        return [int(x) for x in self.xyxy]

    @property
    def polygon(self) -> Optional[List[List[int]]]:
        """Extract polygon contour from binary mask."""
        if self.mask is None or cv2 is None:
            return None
        mask_uint8 = (self.mask > 0).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        return largest.squeeze(1).tolist()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (mask excluded for serialization)."""
        return {
            "xyxy": self.xyxy.tolist() if hasattr(self.xyxy, "tolist") else list(self.xyxy),
            "confidence": float(self.confidence),
            "class_id": int(self.class_id),
            "class_name": self.class_name,
            "mask_area": self.mask_area,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segmentation":
        """Create Segmentation from dictionary (without mask)."""
        return cls(
            xyxy=np.array(data["xyxy"]),
            confidence=data["confidence"],
            class_id=data["class_id"],
            class_name=data.get("class_name", ""),
        )


@dataclass
class SegmentationResult:
    """
    Container for segmentation results from a single image.

    Parameters
    ----------
    segmentations : List[Segmentation]
        List of instance segmentation results.
    semantic_map : Optional[np.ndarray]
        Pixel-level class map of shape (H, W) for semantic segmentation.
    image : Optional[np.ndarray]
        Original image (BGR format).
    inference_time : float
        Inference time in seconds.
    image_path : Optional[str]
        Path to source image.
    model_name : Optional[str]
        Name of the model used.
    """

    segmentations: List[Segmentation] = field(default_factory=list)
    semantic_map: Optional[np.ndarray] = None
    image: Optional[np.ndarray] = None
    inference_time: float = 0.0
    image_path: Optional[str] = None
    model_name: Optional[str] = None

    def __len__(self) -> int:
        return len(self.segmentations)

    def __getitem__(self, idx: int) -> Segmentation:
        return self.segmentations[idx]

    def __iter__(self) -> Iterator[Segmentation]:
        return iter(self.segmentations)

    def __bool__(self) -> bool:
        return len(self.segmentations) > 0 or self.semantic_map is not None

    @property
    def is_semantic(self) -> bool:
        """True if this result contains a semantic segmentation map."""
        return self.semantic_map is not None

    def filter_by_class(self, class_names: List[str]) -> "SegmentationResult":
        """Filter instance segmentations by class names."""
        filtered = [s for s in self.segmentations if s.class_name in class_names]
        return SegmentationResult(
            segmentations=filtered,
            semantic_map=self.semantic_map,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def filter_by_confidence(self, threshold: float) -> "SegmentationResult":
        """Filter instance segmentations by confidence threshold."""
        filtered = [s for s in self.segmentations if s.confidence >= threshold]
        return SegmentationResult(
            segmentations=filtered,
            semantic_map=self.semantic_map,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def to_supervision(self) -> "sv.Detections":
        """Convert instance segmentations to supervision Detections with masks."""
        if sv is None:
            raise ImportError("supervision is required. Install with: pip install supervision")
        if not self.segmentations:
            return sv.Detections.empty()

        xyxy = np.array([s.xyxy for s in self.segmentations])
        confidence = np.array([s.confidence for s in self.segmentations])
        class_id = np.array([s.class_id for s in self.segmentations])

        masks = None
        if any(s.mask is not None for s in self.segmentations):
            masks = np.array([
                s.mask if s.mask is not None else np.zeros_like(self.segmentations[0].mask)
                for s in self.segmentations
            ])

        return sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
            mask=masks,
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
    ) -> "SegmentationResult":
        """Create SegmentationResult from supervision Detections."""
        seg_list = []
        if detections is not None and len(detections) > 0:
            has_masks = detections.mask is not None and len(detections.mask) > 0
            for i in range(len(detections)):
                xyxy = detections.xyxy[i]
                confidence = (
                    float(detections.confidence[i]) if detections.confidence is not None else 1.0
                )
                cid = int(detections.class_id[i])
                cname = class_names.get(cid, f"class_{cid}")
                mask = detections.mask[i] if has_masks else None

                seg_list.append(
                    Segmentation(
                        xyxy=xyxy,
                        confidence=confidence,
                        class_id=cid,
                        class_name=cname,
                        mask=mask,
                    )
                )

        return cls(
            segmentations=seg_list,
            image=image,
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "segmentations": [s.to_dict() for s in self.segmentations],
            "is_semantic": self.is_semantic,
            "inference_time": self.inference_time,
            "image_path": self.image_path,
            "model_name": self.model_name,
            "num_segmentations": len(self.segmentations),
        }


@dataclass
class SegmentationInput:
    """
    Input for segmentation models.

    Parameters
    ----------
    image : Union[ImageType, BatchImageType]
        Input image(s).
    conf_threshold : float
        Confidence threshold.
    iou_threshold : float
        IoU threshold for NMS.
    device : Optional[str]
        Device to run inference on.
    imgsz : Optional[int]
        Image size for inference.
    """

    image: Union[ImageType, BatchImageType]
    conf_threshold: float = 0.5
    iou_threshold: float = 0.5
    device: Optional[str] = None
    imgsz: Optional[int] = None

    @property
    def is_batch(self) -> bool:
        """Check if input contains a batch of images."""
        if isinstance(self.image, (list, tuple)):
            return True
        if torch is not None and isinstance(self.image, torch.Tensor):
            return self.image.dim() == 4
        return False


@dataclass
class SegPrediction:
    """
    Model prediction output for segmentation.

    Parameters
    ----------
    detections : Optional[sv.Detections]
        Single image detections with masks (supervision format).
    batch_detections : Optional[List[sv.Detections]]
        Batch detections with masks.
    results : Optional[List[SegmentationResult]]
        Converted segmentation results.
    inference_time : float
        Total inference time in seconds.
    image_path : Optional[Union[str, List[str]]]
        Source image path(s).
    model_name : Optional[str]
        Name of the model used.
    """

    detections: Optional["sv.Detections"] = None
    batch_detections: Optional[List["sv.Detections"]] = None
    results: Optional[List[SegmentationResult]] = None
    inference_time: float = 0.0
    image_path: Optional[Union[str, List[str]]] = None
    model_name: Optional[str] = None

    @property
    def is_batch(self) -> bool:
        return self.batch_detections is not None

    @property
    def num_detections(self) -> int:
        if self.batch_detections is not None:
            return sum(len(d) for d in self.batch_detections)
        elif self.detections is not None:
            return len(self.detections)
        return 0

    @classmethod
    def from_detections(
        cls,
        detections: "sv.Detections",
        class_names: Dict[int, str],
        inference_time: float,
        image_path: str,
        model_name: Optional[str] = None,
    ) -> "SegPrediction":
        """Create SegPrediction from supervision Detections (with masks)."""
        result = SegmentationResult.from_supervision(
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
    ) -> "SegPrediction":
        """Create SegPrediction from batch of supervision Detections."""
        results = []
        per_image_time = inference_time / max(len(batch_detections), 1)
        for dets, path in zip(batch_detections, image_paths):
            result = SegmentationResult.from_supervision(
                detections=dets,
                class_names=class_names,
                inference_time=per_image_time,
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

    @classmethod
    def from_semantic(
        cls,
        semantic_map: np.ndarray,
        class_names: Dict[int, str],
        inference_time: float,
        image_path: str,
        model_name: Optional[str] = None,
    ) -> "SegPrediction":
        """Create SegPrediction from a semantic segmentation map."""
        result = SegmentationResult(
            semantic_map=semantic_map,
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )
        return cls(
            results=[result],
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )
