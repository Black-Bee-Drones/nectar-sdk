"""
Slicing configuration.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Tuple


class SlicingStrategy(Enum):
    """Available slicing strategies."""

    NONE = "none"
    GRID = "grid"
    ADAPTIVE = "adaptive"
    CLUSTERING = "clustering"
    SUPERVISION = "supervision"


@dataclass
class SlicingConfig:
    """
    Configuration for slicing-based inference.

    Parameters
    ----------
    strategy : SlicingStrategy
        Slicing strategy to use. Defaults to NONE.
    slice_size : Tuple[int, int]
        Size of each slice (height, width). Defaults to (640, 640).
    overlap_ratio : float
        Overlap between slices (0.0 to 1.0). Defaults to 0.2.
    iou_threshold : float
        IoU threshold for merging overlapping detections. Defaults to 0.5.
    conf_threshold : float
        Confidence threshold for detections. Defaults to 0.25.
    min_slice_area_ratio : float
        Minimum slice area as ratio of original. Defaults to 0.01.
    max_slices : int
        Maximum number of slices to prevent memory issues. Defaults to 64.
    adaptive_threshold : float
        Threshold for adaptive slicing density. Defaults to 0.3.
    clustering_eps : float
        DBSCAN epsilon for clustering strategy. Defaults to 50.
    clustering_min_samples : int
        DBSCAN min samples for clustering. Defaults to 2.
    merge_strategy : str
        How to merge overlapping detections ('nms', 'nmm'). Defaults to 'nms'.
    include_full_image : bool
        Include full image as final slice for context. Defaults to True.

    Examples
    --------
    >>> config = SlicingConfig(
    ...     strategy=SlicingStrategy.GRID,
    ...     slice_size=(640, 640),
    ...     overlap_ratio=0.2,
    ... )
    """

    strategy: SlicingStrategy = SlicingStrategy.NONE
    slice_size: Tuple[int, int] = (640, 640)
    overlap_ratio: float = 0.2
    iou_threshold: float = 0.5
    conf_threshold: float = 0.25
    min_slice_area_ratio: float = 0.01
    max_slices: int = 64
    adaptive_threshold: float = 0.3
    clustering_eps: float = 50
    clustering_min_samples: int = 2
    merge_strategy: str = "nms"  # "nms", "soft_nms", "nmm", "wbf"
    include_full_image: bool = True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "SlicingConfig":
        """
        Create SlicingConfig from dictionary.

        Parameters
        ----------
        config_dict : Dict[str, Any]
            Configuration dictionary.

        Returns
        -------
        SlicingConfig
            New SlicingConfig instance.
        """
        # Handle strategy conversion
        if "strategy" in config_dict:
            strategy = config_dict["strategy"]
            if isinstance(strategy, str):
                config_dict["strategy"] = SlicingStrategy(strategy)

        # Handle slice_size conversion
        if "slice_size" in config_dict:
            size = config_dict["slice_size"]
            if isinstance(size, int):
                config_dict["slice_size"] = (size, size)
            elif isinstance(size, (list, tuple)):
                config_dict["slice_size"] = tuple(size)

        # Filter to valid fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_dict.items() if k in valid_fields}

        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns
        -------
        Dict[str, Any]
            Configuration dictionary.
        """
        return {
            "strategy": self.strategy.value,
            "slice_size": list(self.slice_size),
            "overlap_ratio": self.overlap_ratio,
            "iou_threshold": self.iou_threshold,
            "conf_threshold": self.conf_threshold,
            "min_slice_area_ratio": self.min_slice_area_ratio,
            "max_slices": self.max_slices,
            "adaptive_threshold": self.adaptive_threshold,
            "clustering_eps": self.clustering_eps,
            "clustering_min_samples": self.clustering_min_samples,
            "merge_strategy": self.merge_strategy,
            "include_full_image": self.include_full_image,
        }

    @classmethod
    def grid(
        cls,
        slice_size: Tuple[int, int] = (640, 640),
        overlap_ratio: float = 0.2,
    ) -> "SlicingConfig":
        """
        Create grid slicing configuration.

        Parameters
        ----------
        slice_size : Tuple[int, int]
            Size of each slice. Defaults to (640, 640).
        overlap_ratio : float
            Overlap between slices. Defaults to 0.2.

        Returns
        -------
        SlicingConfig
            Grid slicing configuration.
        """
        return cls(
            strategy=SlicingStrategy.GRID,
            slice_size=slice_size,
            overlap_ratio=overlap_ratio,
        )

    @classmethod
    def adaptive(
        cls,
        slice_size: Tuple[int, int] = (640, 640),
        threshold: float = 0.3,
    ) -> "SlicingConfig":
        """
        Create adaptive slicing configuration.

        Parameters
        ----------
        slice_size : Tuple[int, int]
            Size of each slice. Defaults to (640, 640).
        threshold : float
            Adaptive threshold. Defaults to 0.3.

        Returns
        -------
        SlicingConfig
            Adaptive slicing configuration.
        """
        return cls(
            strategy=SlicingStrategy.ADAPTIVE,
            slice_size=slice_size,
            adaptive_threshold=threshold,
        )
