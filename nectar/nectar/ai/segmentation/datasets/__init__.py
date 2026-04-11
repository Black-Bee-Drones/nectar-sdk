"""Dataset management utilities for image segmentation."""

from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.detection.datasets.upload import (
    HuggingFaceDatasetUploader,
    RoboflowUploader,
)
from nectar.ai.segmentation.datasets.analyze import SegDatasetAnalyzer
from nectar.ai.segmentation.datasets.format import SegFormatConverter
from nectar.ai.segmentation.datasets.handlers import (
    BaseDatasetHandler,
    RoboflowSegHandler,
    SegDatasetHandlerRegistry,
    UltralyticsSegHandler,
)

__all__ = [
    "SegFormatConverter",
    "SegDatasetAnalyzer",
    "SegDatasetHandlerRegistry",
    "BaseDatasetHandler",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
    # Re-exported from detection (format-agnostic utilities)
    "SubsetCreator",
    "RoboflowUploader",
    "HuggingFaceDatasetUploader",
]
