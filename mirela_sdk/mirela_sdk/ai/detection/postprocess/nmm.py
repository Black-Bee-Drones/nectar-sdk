"""
Non-Maximum Merging strategy.
"""

from typing import List, Tuple

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None

from mirela_sdk.ai.detection.postprocess.base import BaseMergingStrategy


class NMMStrategy(BaseMergingStrategy):
    """
    Non-Maximum Merging.

    Merges overlapping boxes by averaging coordinates instead
    of suppressing lower-confidence detections.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for merging. Defaults to 0.5.

    Examples
    --------
    >>> strategy = NMMStrategy(iou_threshold=0.5)
    >>> merged, groups, count = strategy.merge_boxes(detections)
    """

    def __init__(self, iou_threshold: float = 0.5):
        """Initialize NMM strategy."""
        super().__init__(iou_threshold)

    def _compute_iou(self, box1: np.ndarray, box2: np.ndarray) -> float:
        """Compute IoU between two boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 < x1 or y2 < y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """
        Apply Non-Maximum Merging.

        Parameters
        ----------
        detections : sv.Detections
            Input detections.

        Returns
        -------
        Tuple[sv.Detections, List[List[int]], int]
            Merged detections, merge groups, number merged.
        """
        if sv is None:
            raise ImportError("supervision is required")

        if len(detections) == 0:
            return detections, [], 0

        boxes = detections.xyxy
        scores = detections.confidence if detections.confidence is not None else np.ones(len(boxes))
        class_ids = detections.class_id if detections.class_id is not None else np.zeros(len(boxes))

        used = set()
        merged_groups = []

        for i in range(len(boxes)):
            if i in used:
                continue

            # Find overlapping boxes of same class
            group = [i]
            for j in range(i + 1, len(boxes)):
                if j in used:
                    continue

                if class_ids[i] == class_ids[j]:
                    iou = self._compute_iou(boxes[i], boxes[j])
                    if iou > self.iou_threshold:
                        group.append(j)
                        used.add(j)

            merged_groups.append(group)

        # Compute merged boxes
        merged_boxes = []
        merged_scores = []
        merged_class_ids = []

        for group in merged_groups:
            group_boxes = boxes[group]
            group_scores = scores[group]

            # Average coordinates
            merged_box = np.mean(group_boxes, axis=0)
            merged_score = np.mean(group_scores)

            merged_boxes.append(merged_box)
            merged_scores.append(merged_score)
            merged_class_ids.append(int(class_ids[group[0]]))

        result = sv.Detections(
            xyxy=np.array(merged_boxes),
            confidence=np.array(merged_scores),
            class_id=np.array(merged_class_ids),
        )

        num_merged = len(detections) - len(result)
        return result, merged_groups, num_merged
