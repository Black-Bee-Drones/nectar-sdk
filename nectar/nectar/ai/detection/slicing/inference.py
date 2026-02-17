"""
Slicing inference handler.
"""

import logging
from pathlib import Path
from typing import Callable, Optional, Union

import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import supervision as sv
    from supervision.detection.tools.inference_slicer import InferenceSlicer
except ImportError:
    sv = None
    InferenceSlicer = None

from nectar.ai.detection.slicing.config import SlicingConfig, SlicingStrategy
from nectar.ai.detection.slicing.slicer import ImageSlicer

logger = logging.getLogger(__name__)


class SlicingInference:
    """
    Handler for slicing-based inference.

    Manages slicing, inference, and merging of detection results
    across image slices using configurable post-processing strategies.

    Parameters
    ----------
    config : SlicingConfig
        Slicing configuration.

    Examples
    --------
    >>> config = SlicingConfig(strategy=SlicingStrategy.GRID)
    >>> slicer = SlicingInference(config)
    >>> detections = slicer.run_sliced_inference(
    ...     image, model.predict_callback
    ... )
    """

    def __init__(self, config: SlicingConfig):
        """Initialize slicing inference handler."""
        self.config = config
        self.slicer = ImageSlicer(config)
        self._merge_strategy = self._create_merge_strategy(config.merge_strategy)

    def _create_merge_strategy(self, strategy_name: str):
        """
        Create merge strategy instance from name.

        Parameters
        ----------
        strategy_name : str
            Strategy name ('nms', 'soft_nms', 'nmm', 'wbf').

        Returns
        -------
        BaseMergingStrategy
            Strategy instance.
        """
        from nectar.ai.detection.postprocess import (
            NMMStrategy,
            NMSStrategy,
            SoftNMSStrategy,
            WBFStrategy,
        )

        strategies = {
            "nms": lambda: NMSStrategy(iou_threshold=self.config.iou_threshold),
            "soft_nms": lambda: SoftNMSStrategy(iou_threshold=self.config.iou_threshold),
            "nmm": lambda: NMMStrategy(iou_threshold=self.config.iou_threshold),
            "wbf": lambda: WBFStrategy(iou_threshold=self.config.iou_threshold),
        }

        if strategy_name not in strategies:
            logger.warning("Unknown merge strategy '%s', falling back to 'nms'", strategy_name)
            strategy_name = "nms"

        return strategies[strategy_name]()

    def run_sliced_inference(
        self,
        image: Union[np.ndarray, "Image.Image", str, Path],
        inference_callback: Callable[[np.ndarray], "sv.Detections"],
        initial_detections: Optional["sv.Detections"] = None,
    ) -> "sv.Detections":
        """
        Run inference on sliced image and merge results.

        Parameters
        ----------
        image : Union[np.ndarray, PIL.Image, str, Path]
            Input image.
        inference_callback : Callable
            Function that takes image array and returns sv.Detections.
        initial_detections : Optional[sv.Detections], optional
            Initial detections for adaptive/clustering strategies.

        Returns
        -------
        sv.Detections
            Merged detections from all slices.

        Examples
        --------
        >>> def predict(img):
        ...     return model.predict(img).detections
        >>> merged = slicer.run_sliced_inference(image, predict)
        """
        if sv is None:
            raise ImportError("supervision is required. Install with: pip install supervision")

        # Use Supervision's InferenceSlicer if configured
        if self.config.strategy == SlicingStrategy.SUPERVISION:
            return self._run_supervision_slicer(image, inference_callback)

        # Convert image to numpy
        if isinstance(image, (str, Path)):
            if Image is None:
                raise ImportError("PIL is required. Install with: pip install Pillow")
            image = np.array(Image.open(image).convert("RGB"))
        elif Image is not None and isinstance(image, Image.Image):
            image = np.array(image.convert("RGB"))

        # Get slices
        slices = self.slicer.slice_image(image, initial_detections)

        if len(slices) == 0:
            logger.warning("No slices generated, running on full image")
            return inference_callback(image)

        logger.info(
            "Running inference on %d slices (%s strategy)",
            len(slices),
            self.config.strategy.value,
        )

        # Run inference on each slice
        all_detections = []
        for slice_info in slices:
            slice_img = slice_info.image
            offset_x, offset_y = slice_info.offset

            # Run inference
            slice_detections = inference_callback(slice_img)

            if slice_detections is not None and len(slice_detections) > 0:
                # Adjust coordinates to original image space
                slice_detections.xyxy[:, [0, 2]] += offset_x
                slice_detections.xyxy[:, [1, 3]] += offset_y
                all_detections.append(slice_detections)

        # Merge detections
        if len(all_detections) == 0:
            return sv.Detections.empty()

        merged = sv.Detections.merge(all_detections)

        # Apply merging strategy
        if len(merged) > 0:
            merged, _, num_merged = self._merge_strategy.merge_boxes(merged)
            if num_merged > 0:
                logger.debug(
                    "Merged %d overlapping detections using %s",
                    num_merged,
                    self._merge_strategy.name,
                )

        return merged

    def _run_supervision_slicer(
        self,
        image: Union[np.ndarray, "Image.Image", str, Path],
        inference_callback: Callable,
    ) -> "sv.Detections":
        """
        Use Supervision's built-in InferenceSlicer.

        Parameters
        ----------
        image : Union[np.ndarray, PIL.Image, str, Path]
            Input image.
        inference_callback : Callable
            Inference callback function.

        Returns
        -------
        sv.Detections
            Merged detections.
        """
        if InferenceSlicer is None:
            raise ImportError("supervision is required. Install with: pip install supervision")

        # Convert to numpy
        if isinstance(image, (str, Path)):
            image = np.array(Image.open(image).convert("RGB"))
        elif Image is not None and isinstance(image, Image.Image):
            image = np.array(image.convert("RGB"))

        # Create Supervision slicer
        slicer = InferenceSlicer(
            callback=inference_callback,
            slice_wh=self.config.slice_size[::-1],  # Supervision uses (w, h)
            overlap_ratio_wh=(
                self.config.overlap_ratio,
                self.config.overlap_ratio,
            ),
            iou_threshold=self.config.iou_threshold,
            thread_workers=1,
        )

        return slicer(image)
