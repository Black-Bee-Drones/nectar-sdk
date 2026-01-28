"""
Slicing-based inference module.

Slicing strategies for detecting small objects in high-resolution images
(SAHI-like functionality).
"""

from mirela_sdk.ai.detection.slicing.config import SlicingConfig, SlicingStrategy
from mirela_sdk.ai.detection.slicing.slicer import ImageSlicer, SliceInfo
from mirela_sdk.ai.detection.slicing.inference import SlicingInference

__all__ = [
    "SlicingConfig",
    "SlicingStrategy",
    "ImageSlicer",
    "SliceInfo",
    "SlicingInference",
]
