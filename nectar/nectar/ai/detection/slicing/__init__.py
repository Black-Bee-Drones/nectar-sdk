"""
Slicing-based inference module.

Slicing strategies for detecting small objects in high-resolution images
(SAHI-like functionality).
"""

from nectar.ai.detection.slicing.config import SlicingConfig, SlicingStrategy
from nectar.ai.detection.slicing.inference import SlicingInference
from nectar.ai.detection.slicing.slicer import ImageSlicer, SliceInfo

__all__ = [
    "SlicingConfig",
    "SlicingStrategy",
    "ImageSlicer",
    "SliceInfo",
    "SlicingInference",
]
