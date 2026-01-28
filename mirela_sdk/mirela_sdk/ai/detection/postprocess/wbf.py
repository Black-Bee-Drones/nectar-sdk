"""
Weighted Boxes Fusion strategy.
"""

from typing import List, Tuple

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None

from mirela_sdk.ai.detection.postprocess.base import BaseMergingStrategy


class WBFStrategy(BaseMergingStrategy):
    """
    Weighted Boxes Fusion.

    Fuses overlapping boxes by computing weighted average of
    coordinates based on confidence scores.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for fusion. Defaults to 0.5.
    skip_box_threshold : float
        Minimum confidence to consider. Defaults to 0.0001.

    Examples
    --------
    >>> strategy = WBFStrategy(iou_threshold=0.5)
    >>> merged, groups, count = strategy.merge_boxes(detections)
    """

    def __init__(
        self,
        iou_threshold: float = 0.5,
        skip_box_threshold: float = 0.0001,
    ):
        """Initialize WBF strategy."""
        super().__init__(iou_threshold)
        self.skip_box_threshold = skip_box_threshold

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
        Apply Weighted Boxes Fusion.

        Parameters
        ----------
        detections : sv.Detections
            Input detections.

        Returns
        -------
        Tuple[sv.Detections, List[List[int]], int]
            Fused detections, fusion groups, number fused.
        """
        if sv is None:
            raise ImportError("supervision is required")

        if len(detections) == 0:
            return detections, [], 0

        boxes = detections.xyxy
        scores = (
            detections.confidence
            if detections.confidence is not None
            else np.ones(len(boxes))
        )
        class_ids = (
            detections.class_id
            if detections.class_id is not None
            else np.zeros(len(boxes))
        )

        # Filter low confidence
        mask = scores >= self.skip_box_threshold
        boxes = boxes[mask]
        scores = scores[mask]
        class_ids = class_ids[mask]

        if len(boxes) == 0:
            return sv.Detections.empty(), [], len(detections)

        # Sort by score
        order = scores.argsort()[::-1]
        boxes = boxes[order]
        scores = scores[order]
        class_ids = class_ids[order]

        # Group boxes by class
        unique_classes = np.unique(class_ids)
        fused_boxes = []
        fused_scores = []
        fused_class_ids = []
        all_groups = []

        for cls in unique_classes:
            cls_mask = class_ids == cls
            cls_boxes = boxes[cls_mask]
            cls_scores = scores[cls_mask]
            cls_indices = np.where(cls_mask)[0]

            used = set()
            for i in range(len(cls_boxes)):
                if i in used:
                    continue

                # Find matching boxes
                matches = [i]
                for j in range(i + 1, len(cls_boxes)):
                    if j in used:
                        continue
                    iou = self._compute_iou(cls_boxes[i], cls_boxes[j])
                    if iou > self.iou_threshold:
                        matches.append(j)
                        used.add(j)

                # Weighted fusion
                match_boxes = cls_boxes[matches]
                match_scores = cls_scores[matches]

                weights = match_scores
                total_weight = weights.sum()

                if total_weight > 0:
                    fused_box = (match_boxes * weights[:, np.newaxis]).sum(
                        axis=0
                    ) / total_weight
                    fused_score = match_scores.mean()
                else:
                    fused_box = match_boxes[0]
                    fused_score = match_scores[0]

                fused_boxes.append(fused_box)
                fused_scores.append(fused_score)
                fused_class_ids.append(cls)
                all_groups.append([int(cls_indices[m]) for m in matches])

        if not fused_boxes:
            return sv.Detections.empty(), [], len(detections)

        result = sv.Detections(
            xyxy=np.array(fused_boxes),
            confidence=np.array(fused_scores),
            class_id=np.array(fused_class_ids, dtype=int),
        )

        num_fused = len(detections) - len(result)
        return result, all_groups, num_fused
