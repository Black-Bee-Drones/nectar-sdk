"""Base class for merging strategies."""

from abc import ABC, abstractmethod
from typing import List, Tuple

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None


class BaseMergingStrategy(ABC):
    """
    Abstract base class for detection merging strategies.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for considering boxes as overlapping.
    """

    def __init__(self, iou_threshold: float = 0.5):
        self.iou_threshold = iou_threshold

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """Merge overlapping bounding boxes.

        Returns (merged detections, merge groups, number merged).
        """
        ...

    @staticmethod
    def _compute_iou_pair(box1: np.ndarray, box2: np.ndarray) -> float:
        """IoU between two single boxes (xyxy)."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        if x2 < x1 or y2 < y1:
            return 0.0
        inter = (x2 - x1) * (y2 - y1)
        a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _compute_iou_batch(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """IoU between one box and multiple boxes (xyxy)."""
        x1 = np.maximum(box[0], boxes[:, 0])
        y1 = np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[2], boxes[:, 2])
        y2 = np.minimum(box[3], boxes[:, 3])
        inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        box_area = (box[2] - box[0]) * (box[3] - box[1])
        boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        union = box_area + boxes_area - inter
        return inter / np.maximum(union, 1e-6)
