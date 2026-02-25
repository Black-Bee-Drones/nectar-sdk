"""Non-Maximum Merging strategy using supervision."""

from typing import List, Tuple

try:
    import supervision as sv
except ImportError:
    sv = None

from nectar.ai.detection.postprocess.base import BaseMergingStrategy


class NMMStrategy(BaseMergingStrategy):
    """
    Non-Maximum Merging.

    Merges overlapping boxes by averaging coordinates instead
    of suppressing lower-confidence detections.
    Uses supervision's optimized `with_nmm()`.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for merging. Defaults to 0.5.
    """

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        if sv is None:
            raise ImportError("supervision is required")
        if len(detections) == 0:
            return detections, [], 0

        original_count = len(detections)
        merged = detections.with_nmm(threshold=self.iou_threshold)
        return merged, [], original_count - len(merged)
