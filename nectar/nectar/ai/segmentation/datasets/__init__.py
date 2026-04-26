"""Dataset management utilities for image segmentation."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.segmentation.datasets.format import SegFormatConverter
from nectar.ai.segmentation.datasets.handlers import (
    BaseDatasetHandler,
    RoboflowSegHandler,
    SegDatasetHandlerRegistry,
    UltralyticsSegHandler,
)

_LAZY_ATTRS = {
    "SegDatasetAnalyzer": "nectar.ai.segmentation.datasets.analyze",
    "RoboflowUploader": "nectar.ai.detection.datasets.upload",
    "HuggingFaceDatasetUploader": "nectar.ai.detection.datasets.upload",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from nectar.ai.detection.datasets.upload import (
        HuggingFaceDatasetUploader,
        RoboflowUploader,
    )
    from nectar.ai.segmentation.datasets.analyze import SegDatasetAnalyzer


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
