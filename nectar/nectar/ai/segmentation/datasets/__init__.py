"""Dataset management utilities for image segmentation."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.segmentation.datasets.format import SegFormatConverter
from nectar.ai.segmentation.datasets.handlers import (
    BaseDatasetHandler,
    HuggingFaceSegHandler,
    RoboflowSegHandler,
    SegDatasetHandlerRegistry,
    UltralyticsSegHandler,
)

_LAZY_ATTRS = {
    "SegDatasetAnalyzer": "nectar.ai.segmentation.datasets.analyze",
    "RoboflowUploader": "nectar.ai.detection.datasets.upload",
    "HuggingFaceDatasetUploader": "nectar.ai.detection.datasets.upload",
    # Segmentation HuggingFace dataset support (pull huggingface_hub / datasets)
    "HuggingFaceSegDatasetUploader": "nectar.ai.segmentation.datasets.upload",
    "seg_coco_to_hf": "nectar.ai.segmentation.datasets.hf_converter",
    "seg_yolo_to_hf": "nectar.ai.segmentation.datasets.hf_converter",
    "hf_to_coco_seg": "nectar.ai.segmentation.datasets.hf_converter",
    "hf_to_yolo_seg": "nectar.ai.segmentation.datasets.hf_converter",
    "generate_seg_dataset_card": "nectar.ai.segmentation.datasets.hf_converter",
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
    from nectar.ai.segmentation.datasets.hf_converter import (
        generate_seg_dataset_card,
        hf_to_coco_seg,
        hf_to_yolo_seg,
        seg_coco_to_hf,
        seg_yolo_to_hf,
    )
    from nectar.ai.segmentation.datasets.upload import HuggingFaceSegDatasetUploader


__all__ = [
    "SegFormatConverter",
    "SegDatasetAnalyzer",
    "SegDatasetHandlerRegistry",
    "BaseDatasetHandler",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
    "HuggingFaceSegHandler",
    # Segmentation HuggingFace dataset conversion + upload
    "HuggingFaceSegDatasetUploader",
    "seg_coco_to_hf",
    "seg_yolo_to_hf",
    "hf_to_coco_seg",
    "hf_to_yolo_seg",
    "generate_seg_dataset_card",
    # Re-exported from detection (format-agnostic utilities)
    "SubsetCreator",
    "RoboflowUploader",
    "HuggingFaceDatasetUploader",
]
