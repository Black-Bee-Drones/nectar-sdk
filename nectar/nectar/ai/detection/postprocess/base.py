from abc import ABC, abstractmethod
from typing import List, Tuple

try:
    import supervision as sv
except ImportError:
    sv = None


class BaseMergingStrategy(ABC):
    """
    Abstract base class for merging strategies.

    Parameters
    ----------
    iou_threshold : float
        IoU threshold for considering boxes as overlapping.

    Examples
    --------
    >>> class MyStrategy(BaseMergingStrategy):
    ...     def merge_boxes(self, detections):
    ...         # Custom merging logic
    ...         return detections, [], 0
    """

    def __init__(self, iou_threshold: float = 0.5):
        """Initialize merging strategy."""
        self.iou_threshold = iou_threshold

    @property
    def name(self) -> str:
        """str: Strategy name."""
        return self.__class__.__name__

    @abstractmethod
    def merge_boxes(
        self, detections: "sv.Detections"
    ) -> Tuple["sv.Detections", List[List[int]], int]:
        """
        Merge overlapping bounding boxes.

        Parameters
        ----------
        detections : sv.Detections
            Input detections to merge.

        Returns
        -------
        Tuple[sv.Detections, List[List[int]], int]
            Tuple of:
            - Merged detections
            - Merge groups (list of lists of original indices)
            - Number of boxes merged
        """
        pass
