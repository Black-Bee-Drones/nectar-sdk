"""Weighted Boxes Fusion strategy.

Reference: https://arxiv.org/abs/1910.13302
"""

from typing import List, Tuple

import numpy as np

try:
    import supervision as sv
except ImportError:
    sv = None

from nectar.ai.detection.postprocess.base import BaseMergingStrategy


class WBFStrategy(BaseMergingStrategy):
    """
    Weighted Boxes Fusion.

    Fuses overlapping boxes by weighted coordinate averaging.
    Uses cluster-based matching: a new box joins a cluster if it
    overlaps with *any* box already in the cluster.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for fusion. Defaults to 0.5.
    skip_box_threshold : float
        Minimum confidence to consider. Defaults to 0.0.
    conf_type : str
        Score fusion method: "avg" or "max". Defaults to "avg".
    """

    def __init__(
        self,
        iou_threshold: float = 0.5,
        skip_box_threshold: float = 0.0,
        conf_type: str = "avg",
    ):
        super().__init__(iou_threshold)
        self.skip_box_threshold = skip_box_threshold
        self.conf_type = conf_type

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
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
        classes = (
            detections.class_id.copy()
            if detections.class_id is not None
            else np.zeros(len(boxes), dtype=int)
        )

        mask = scores > self.skip_box_threshold
        if not mask.any():
            return sv.Detections.empty(), [], len(detections)

        boxes, scores, classes = boxes[mask], scores[mask], classes[mask]
        original_indices = np.where(mask)[0]

        fused_boxes, fused_scores, fused_classes, merge_groups = [], [], [], []

        for cls_id in np.unique(classes):
            cls_mask = classes == cls_id
            cls_boxes = boxes[cls_mask]
            cls_scores = scores[cls_mask]
            cls_indices = original_indices[cls_mask]

            fb, fs, groups = self._fuse_class(cls_boxes, cls_scores, cls_indices)
            fused_boxes.extend(fb)
            fused_scores.extend(fs)
            fused_classes.extend([cls_id] * len(fb))
            merge_groups.extend(groups)

        if not fused_boxes:
            return sv.Detections.empty(), [], len(detections)

        result = sv.Detections(
            xyxy=np.array(fused_boxes),
            confidence=np.array(fused_scores),
            class_id=np.array(fused_classes, dtype=int),
        )
        return result, merge_groups, len(detections) - len(result)

    def _fuse_class(
        self, boxes: np.ndarray, scores: np.ndarray, indices: np.ndarray
    ) -> Tuple[List[np.ndarray], List[float], List[List[int]]]:
        if len(boxes) == 0:
            return [], [], []

        order = scores.argsort()[::-1]
        boxes, scores, indices = boxes[order], scores[order], indices[order]

        fused_boxes, fused_scores, merge_groups = [], [], []
        used = np.zeros(len(boxes), dtype=bool)

        for i in range(len(boxes)):
            if used[i]:
                continue

            cluster_boxes = [boxes[i]]
            cluster_scores = [float(scores[i])]
            cluster_indices = [int(indices[i])]
            used[i] = True

            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                if self._matches_cluster(boxes[j], cluster_boxes):
                    cluster_boxes.append(boxes[j])
                    cluster_scores.append(float(scores[j]))
                    cluster_indices.append(int(indices[j]))
                    used[j] = True

            fused_boxes.append(self._fuse_coordinates(cluster_boxes, cluster_scores))
            fused_scores.append(self._fuse_score(cluster_scores))
            merge_groups.append(cluster_indices)

        return fused_boxes, fused_scores, merge_groups

    def _matches_cluster(self, box: np.ndarray, cluster: List[np.ndarray]) -> bool:
        for cluster_box in cluster:
            if self._compute_iou_pair(box, cluster_box) > self.iou_threshold:
                return True
        return False

    @staticmethod
    def _fuse_coordinates(boxes: List[np.ndarray], scores: List[float]) -> np.ndarray:
        boxes_arr = np.array(boxes)
        weights = np.array(scores)
        total = weights.sum()
        if total == 0:
            return boxes_arr[0]
        return (boxes_arr * weights[:, np.newaxis]).sum(axis=0) / total

    def _fuse_score(self, scores: List[float]) -> float:
        if self.conf_type == "max":
            return max(scores)
        return float(np.mean(scores))
