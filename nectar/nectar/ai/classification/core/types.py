"""Core data types for image classification."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Union

import numpy as np

if TYPE_CHECKING:
    import torch
    from PIL import Image


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
class Classification:
    """
    Single class prediction entry.

    Parameters
    ----------
    class_id : int
        Class identifier (zero-indexed).
    class_name : str
        Human-readable class name.
    confidence : float
        Prediction confidence in range [0.0, 1.0].
    """

    class_id: int
    class_name: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": int(self.class_id),
            "class_name": self.class_name,
            "confidence": float(self.confidence),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Classification":
        return cls(
            class_id=int(data["class_id"]),
            class_name=data.get("class_name", ""),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass
class ClassificationResult:
    """
    Classification result for a single image.

    Parameters
    ----------
    predictions : List[Classification]
        Top-k predictions sorted by confidence descending.
    probs : Optional[np.ndarray]
        Full class probability vector of shape (C,).
    image : Optional[np.ndarray]
        Original image (BGR).
    inference_time : float
        Inference time in seconds.
    image_path : Optional[str]
        Path to source image.
    model_name : Optional[str]
        Name of the model used.
    """

    predictions: List[Classification] = field(default_factory=list)
    probs: Optional[np.ndarray] = None
    image: Optional[np.ndarray] = None
    inference_time: float = 0.0
    image_path: Optional[str] = None
    model_name: Optional[str] = None

    def __len__(self) -> int:
        return len(self.predictions)

    def __getitem__(self, idx: int) -> Classification:
        return self.predictions[idx]

    def __iter__(self) -> Iterator[Classification]:
        return iter(self.predictions)

    def __bool__(self) -> bool:
        return len(self.predictions) > 0

    @property
    def top1(self) -> Optional[Classification]:
        return self.predictions[0] if self.predictions else None

    @property
    def top1_id(self) -> Optional[int]:
        return self.predictions[0].class_id if self.predictions else None

    @property
    def top1_name(self) -> Optional[str]:
        return self.predictions[0].class_name if self.predictions else None

    @property
    def top1_confidence(self) -> Optional[float]:
        return self.predictions[0].confidence if self.predictions else None

    def topk(self, k: int = 5) -> "ClassificationResult":
        """Return a result limited to the top-k predictions."""
        return ClassificationResult(
            predictions=self.predictions[:k],
            probs=self.probs,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def filter_by_confidence(self, threshold: float) -> "ClassificationResult":
        filtered = [p for p in self.predictions if p.confidence >= threshold]
        return ClassificationResult(
            predictions=filtered,
            probs=self.probs,
            image=self.image,
            inference_time=self.inference_time,
            image_path=self.image_path,
            model_name=self.model_name,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictions": [p.to_dict() for p in self.predictions],
            "top1_id": self.top1_id,
            "top1_name": self.top1_name,
            "top1_confidence": self.top1_confidence,
            "inference_time": self.inference_time,
            "image_path": self.image_path,
            "model_name": self.model_name,
        }

    @classmethod
    def from_probs(
        cls,
        probs: np.ndarray,
        class_names: Dict[int, str],
        topk: int = 5,
        inference_time: float = 0.0,
        image_path: Optional[str] = None,
        model_name: Optional[str] = None,
        image: Optional[np.ndarray] = None,
    ) -> "ClassificationResult":
        """Build a result from a full probability vector."""
        probs = np.asarray(probs, dtype=np.float32).ravel()
        k = min(topk, len(probs))
        top_ids = np.argsort(probs)[::-1][:k]
        predictions = [
            Classification(
                class_id=int(cid),
                class_name=class_names.get(int(cid), f"class_{cid}"),
                confidence=float(probs[cid]),
            )
            for cid in top_ids
        ]
        return cls(
            predictions=predictions,
            probs=probs,
            image=image,
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )


@dataclass
class ClassificationInput:
    """
    Input for classification models.

    Parameters
    ----------
    image : Union[ImageType, BatchImageType]
        Input image(s).
    device : Optional[str]
        Device to run inference on.
    topk : int
        Number of top predictions to return.
    imgsz : Optional[int]
        Image size for inference.
    """

    image: Union[ImageType, BatchImageType]
    device: Optional[str] = None
    topk: int = 5
    imgsz: Optional[int] = None

    @property
    def is_batch(self) -> bool:
        if isinstance(self.image, (list, tuple)):
            return True
        try:
            import torch
        except ImportError:
            return False
        if isinstance(self.image, torch.Tensor):
            return self.image.dim() == 4
        return False


@dataclass
class ClsPrediction:
    """
    Model prediction output for classification.

    Parameters
    ----------
    result : Optional[ClassificationResult]
        Single-image result.
    results : Optional[List[ClassificationResult]]
        Batch results.
    inference_time : float
        Total inference time in seconds.
    image_path : Optional[Union[str, List[str]]]
        Source image path(s).
    model_name : Optional[str]
        Name of the model used.
    """

    result: Optional[ClassificationResult] = None
    results: Optional[List[ClassificationResult]] = None
    inference_time: float = 0.0
    image_path: Optional[Union[str, List[str]]] = None
    model_name: Optional[str] = None

    @property
    def is_batch(self) -> bool:
        return self.results is not None and len(self.results) > 1

    @classmethod
    def from_result(
        cls,
        result: ClassificationResult,
        inference_time: float,
        image_path: str,
        model_name: Optional[str] = None,
    ) -> "ClsPrediction":
        return cls(
            result=result,
            results=[result],
            inference_time=inference_time,
            image_path=image_path,
            model_name=model_name,
        )

    @classmethod
    def from_batch_results(
        cls,
        results: List[ClassificationResult],
        inference_time: float,
        image_paths: List[str],
        model_name: Optional[str] = None,
    ) -> "ClsPrediction":
        return cls(
            results=results,
            inference_time=inference_time,
            image_path=image_paths,
            model_name=model_name,
        )
