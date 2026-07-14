"""Supported AI framework identifiers"""

from enum import Enum


class Framework(Enum):
    """Supported model frameworks for detection, segmentation, and classification."""

    ULTRALYTICS = "ultralytics"
    TRANSFORMERS = "transformers"
    RFDETR = "rfdetr"
