"""
Soft Non-Maximum Suppression strategy.
"""

from typing import List, Tuple

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None

from mirela_sdk.ai.detection.postprocess.base import BaseMergingStrategy


class SoftNMSStrategy(BaseMergingStrategy):
    """
    Soft Non-Maximum Suppression.

    Gradually reduces confidence of overlapping detections using
    a Gaussian decay function instead of hard suppression.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold to start decaying. Defaults to 0.5.
    sigma : float
        Gaussian sigma for decay. Defaults to 0.5.
    score_threshold : float
        Minimum score to keep. Defaults to 0.001.

    Examples
    --------
    >>> strategy = SoftNMSStrategy(iou_threshold=0.5, sigma=0.5)
    >>> merged, groups, count = strategy.merge_boxes(detections)
    """

    def __init__(
        self,
        iou_threshold: float = 0.5,
        sigma: float = 0.5,
        score_threshold: float = 0.001,
    ):
        """Initialize Soft-NMS strategy."""
        super().__init__(iou_threshold)
        self.sigma = sigma
        self.score_threshold = score_threshold

    def _compute_iou(self, box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
        """Compute IoU between one box and multiple boxes."""
        x1 = np.maximum(box[0], boxes[:, 0])
        y1 = np.maximum(box[1], boxes[:, 1])
        x2 = np.minimum(box[2], boxes[:, 2])
        y2 = np.minimum(box[3], boxes[:, 3])

        intersection = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)

        box_area = (box[2] - box[0]) * (box[3] - box[1])
        boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        union = box_area + boxes_area - intersection

        return intersection / np.maximum(union, 1e-6)

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """
        Apply Soft-NMS to detections.

        Parameters
        ----------
        detections : sv.Detections
            Input detections.

        Returns
        -------
        Tuple[sv.Detections, List[List[int]], int]
            Merged detections, merge groups, number removed.
        """
        if sv is None:
            raise ImportError("supervision is required")

        if len(detections) == 0:
            return detections, [], 0

        boxes = detections.xyxy.copy()
        scores = (
            detections.confidence.copy()
            if detections.confidence is not None
            else np.ones(len(boxes))
        )
        class_ids = (
            detections.class_id.copy() if detections.class_id is not None else np.zeros(len(boxes))
        )

        # Sort by score
        order = scores.argsort()[::-1]
        boxes = boxes[order]
        scores = scores[order]
        class_ids = class_ids[order]

        keep_indices = []
        for i in range(len(boxes)):
            if scores[i] < self.score_threshold:
                continue

            keep_indices.append(i)

            # Compute IoU with remaining boxes
            remaining_indices = list(range(i + 1, len(boxes)))
            if not remaining_indices:
                continue

            ious = self._compute_iou(boxes[i], boxes[remaining_indices])

            # Apply Gaussian decay
            for j, (idx, iou) in enumerate(zip(remaining_indices, ious)):
                if class_ids[i] == class_ids[idx]:  # Same class
                    if iou > self.iou_threshold:
                        scores[idx] *= np.exp(-(iou * iou) / self.sigma)

        # Build result
        keep_boxes = boxes[keep_indices]
        keep_scores = scores[keep_indices]
        keep_class_ids = class_ids[keep_indices]

        # Filter by score threshold
        mask = keep_scores >= self.score_threshold
        keep_boxes = keep_boxes[mask]
        keep_scores = keep_scores[mask]
        keep_class_ids = keep_class_ids[mask].astype(int)

        result = sv.Detections(
            xyxy=keep_boxes,
            confidence=keep_scores,
            class_id=keep_class_ids,
        )

        num_removed = len(detections) - len(result)
        return result, [], num_removed
