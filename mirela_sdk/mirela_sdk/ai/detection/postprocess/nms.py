"""
Standard Non-Maximum Suppression strategy.
"""

from typing import List, Tuple

try:
    import supervision as sv
except ImportError:
    sv = None

from mirela_sdk.ai.detection.postprocess.base import BaseMergingStrategy


class NMSStrategy(BaseMergingStrategy):
    """
    Standard Non-Maximum Suppression.

    Removes overlapping detections by keeping the highest confidence
    detection and suppressing overlapping ones.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for suppression. Defaults to 0.5.
    class_agnostic : bool
        If True, apply NMS across all classes. Defaults to False.

    Examples
    --------
    >>> strategy = NMSStrategy(iou_threshold=0.5)
    >>> merged, groups, count = strategy.merge_boxes(detections)
    """

    def __init__(
        self,
        iou_threshold: float = 0.5,
        class_agnostic: bool = False,
    ):
        """Initialize NMS strategy."""
        super().__init__(iou_threshold)
        self.class_agnostic = class_agnostic

    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """
        Apply NMS to detections.

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

        original_count = len(detections)
        merged = detections.with_nms(
            threshold=self.iou_threshold,
            class_agnostic=self.class_agnostic,
        )

        num_merged = original_count - len(merged)
        return merged, [], num_merged
