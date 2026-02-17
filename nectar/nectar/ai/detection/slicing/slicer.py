"""
Image slicing strategies.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import supervision as sv
except ImportError:
    sv = None

from nectar.ai.detection.slicing.config import SlicingConfig, SlicingStrategy

logger = logging.getLogger(__name__)


@dataclass
class SliceInfo:
    """
    Information about a single slice.

    Parameters
    ----------
    image : np.ndarray
        Sliced image array.
    offset : tuple
        (x, y) offset in original image.
    size : tuple
        (width, height) of slice.
    scale : float
        Scale factor if resized. Defaults to 1.0.
    """

    image: np.ndarray
    offset: tuple  # (x, y)
    size: tuple  # (width, height)
    scale: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "offset": self.offset,
            "size": self.size,
            "scale": self.scale,
        }


class ImageSlicer:
    """
    Handles image slicing with different strategies.

    Parameters
    ----------
    config : SlicingConfig
        Slicing configuration.

    Examples
    --------
    >>> config = SlicingConfig(strategy=SlicingStrategy.GRID)
    >>> slicer = ImageSlicer(config)
    >>> slices = slicer.slice_image(image)
    >>> for slice_info in slices:
    ...     print(f"Slice at {slice_info.offset}, size {slice_info.size}")
    """

    def __init__(self, config: SlicingConfig):
        """Initialize image slicer."""
        self.config = config
        self.logger = logging.getLogger(__name__)

    def slice_image(
        self,
        image: Union[np.ndarray, "Image.Image", str, Path],
        detections: Optional["sv.Detections"] = None,
    ) -> List[SliceInfo]:
        """
        Slice image based on configured strategy.

        Parameters
        ----------
        image : Union[np.ndarray, PIL.Image, str, Path]
            Input image.
        detections : Optional[sv.Detections], optional
            Initial detections for adaptive/clustering strategies.

        Returns
        -------
        List[SliceInfo]
            List of slice information objects.
        """
        # Convert to numpy array
        if isinstance(image, (str, Path)):
            if Image is None:
                raise ImportError("PIL is required. Install with: pip install Pillow")
            image = np.array(Image.open(image).convert("RGB"))
        elif Image is not None and isinstance(image, Image.Image):
            image = np.array(image.convert("RGB"))

        # Route to strategy
        if self.config.strategy == SlicingStrategy.NONE:
            return self._no_slice(image)
        elif self.config.strategy == SlicingStrategy.GRID:
            return self._grid_slice(image)
        elif self.config.strategy == SlicingStrategy.ADAPTIVE:
            return self._adaptive_slice(image, detections)
        elif self.config.strategy == SlicingStrategy.CLUSTERING:
            return self._clustering_slice(image, detections)
        elif self.config.strategy == SlicingStrategy.SUPERVISION:
            return self._grid_slice(image)  # Use grid for Supervision
        else:
            raise ValueError(f"Unsupported slicing strategy: {self.config.strategy}")

    def _no_slice(self, image: np.ndarray) -> List[SliceInfo]:
        """Return full image without slicing."""
        h, w = image.shape[:2]
        return [SliceInfo(image=image, offset=(0, 0), size=(w, h), scale=1.0)]

    def _grid_slice(self, image: np.ndarray) -> List[SliceInfo]:
        """
        Grid-based slicing (SAHI-style).

        Divides image into fixed-size overlapping patches.
        """
        h, w = image.shape[:2]
        slice_h, slice_w = self.config.slice_size

        # Calculate stride with overlap
        stride_h = int(slice_h * (1 - self.config.overlap_ratio))
        stride_w = int(slice_w * (1 - self.config.overlap_ratio))

        slices = []
        for y in range(0, h, stride_h):
            for x in range(0, w, stride_w):
                # Calculate slice bounds
                y_end = min(y + slice_h, h)
                x_end = min(x + slice_w, w)

                slice_img = image[y:y_end, x:x_end]

                # Skip very small slices
                slice_area = slice_img.shape[0] * slice_img.shape[1]
                min_area = self.config.min_slice_area_ratio * h * w
                if slice_area < min_area:
                    continue

                slices.append(
                    SliceInfo(
                        image=slice_img,
                        offset=(x, y),
                        size=(x_end - x, y_end - y),
                        scale=1.0,
                    )
                )

                if len(slices) >= self.config.max_slices:
                    self.logger.warning(f"Reached maximum slices ({self.config.max_slices})")
                    break
            if len(slices) >= self.config.max_slices:
                break

        # Include full image if configured
        if self.config.include_full_image and len(slices) > 1:
            slices.append(
                SliceInfo(
                    image=image,
                    offset=(0, 0),
                    size=(w, h),
                    scale=1.0,
                )
            )

        return slices

    def _adaptive_slice(
        self,
        image: np.ndarray,
        detections: Optional["sv.Detections"],
    ) -> List[SliceInfo]:
        """
        Adaptive slicing based on content density.

        Creates slices focused on high-density detection regions.
        """
        h, w = image.shape[:2]

        # Fall back to grid if no detections
        if detections is None or len(detections) == 0:
            return self._grid_slice(image)

        try:
            from scipy.ndimage import gaussian_filter, label
        except ImportError:
            self.logger.warning("scipy required for adaptive slicing, falling back to grid")
            return self._grid_slice(image)

        # Create density map
        density_map = np.zeros((h, w), dtype=np.float32)
        for box in detections.xyxy:
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            density_map[y1:y2, x1:x2] += 1

        # Smooth density
        density_map = gaussian_filter(density_map, sigma=20)

        # Find high-density regions
        threshold = np.percentile(
            density_map[density_map > 0],
            100 * self.config.adaptive_threshold,
        )
        high_density = density_map > threshold
        labeled_array, num_features = label(high_density)

        slices = []
        slice_h, slice_w = self.config.slice_size

        for i in range(1, num_features + 1):
            region_mask = labeled_array == i
            y_indices, x_indices = np.where(region_mask)

            if len(y_indices) == 0:
                continue

            # Get region bounds with margin
            margin = int(min(slice_h, slice_w) * 0.1)
            y_min = max(0, y_indices.min() - margin)
            y_max = min(h, y_indices.max() + margin)
            x_min = max(0, x_indices.min() - margin)
            x_max = min(w, x_indices.max() + margin)

            # Ensure minimum size
            if (y_max - y_min) < slice_h:
                pad = (slice_h - (y_max - y_min)) // 2
                y_min = max(0, y_min - pad)
                y_max = min(h, y_max + pad)

            if (x_max - x_min) < slice_w:
                pad = (slice_w - (x_max - x_min)) // 2
                x_min = max(0, x_min - pad)
                x_max = min(w, x_max + pad)

            slice_img = image[y_min:y_max, x_min:x_max]
            slices.append(
                SliceInfo(
                    image=slice_img,
                    offset=(x_min, y_min),
                    size=(x_max - x_min, y_max - y_min),
                    scale=1.0,
                )
            )

            if len(slices) >= self.config.max_slices:
                break

        # Add full image
        if self.config.include_full_image and slices:
            slices.append(
                SliceInfo(
                    image=image,
                    offset=(0, 0),
                    size=(w, h),
                    scale=1.0,
                )
            )
        elif not slices:
            return self._grid_slice(image)

        return slices

    def _clustering_slice(
        self,
        image: np.ndarray,
        detections: Optional["sv.Detections"],
    ) -> List[SliceInfo]:
        """
        Clustering-based slicing to avoid cutting through elements.

        Groups detections into clusters and creates slices around them.
        """
        h, w = image.shape[:2]

        if detections is None or len(detections) == 0:
            return self._grid_slice(image)

        try:
            from sklearn.cluster import DBSCAN
        except ImportError:
            self.logger.warning("sklearn required for clustering, falling back to grid")
            return self._grid_slice(image)

        # Get detection centers
        centers = []
        for box in detections.xyxy:
            x1, y1, x2, y2 = box
            centers.append([(x1 + x2) / 2, (y1 + y2) / 2])
        centers = np.array(centers)

        # Cluster centers
        clustering = DBSCAN(
            eps=self.config.clustering_eps,
            min_samples=self.config.clustering_min_samples,
        )
        labels = clustering.fit_predict(centers)

        slices = []
        slice_h, slice_w = self.config.slice_size

        # Create slices for each cluster
        for cluster_id in set(labels):
            if cluster_id == -1:  # Skip noise
                continue

            cluster_mask = labels == cluster_id
            cluster_boxes = detections.xyxy[cluster_mask]

            # Get cluster bounds
            x_min = int(cluster_boxes[:, 0].min())
            y_min = int(cluster_boxes[:, 1].min())
            x_max = int(cluster_boxes[:, 2].max())
            y_max = int(cluster_boxes[:, 3].max())

            # Add margin
            margin = int(min(slice_h, slice_w) * 0.15)
            x_min = max(0, x_min - margin)
            y_min = max(0, y_min - margin)
            x_max = min(w, x_max + margin)
            y_max = min(h, y_max + margin)

            slice_img = image[y_min:y_max, x_min:x_max]
            slices.append(
                SliceInfo(
                    image=slice_img,
                    offset=(x_min, y_min),
                    size=(x_max - x_min, y_max - y_min),
                    scale=1.0,
                )
            )

            if len(slices) >= self.config.max_slices:
                break

        # Add full image
        if self.config.include_full_image and slices:
            slices.append(
                SliceInfo(
                    image=image,
                    offset=(0, 0),
                    size=(w, h),
                    scale=1.0,
                )
            )
        elif not slices:
            return self._grid_slice(image)

        return slices
