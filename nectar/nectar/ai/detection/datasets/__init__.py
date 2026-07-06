"""Dataset management utilities for object detection."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.ai.detection.datasets.augment import (
    AUG_AERIAL,
    AUG_AGGRESSIVE,
    AUG_CONSERVATIVE,
    AUG_INDUSTRIAL,
    AugmentationBuilder,
)
from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector
from nectar.ai.detection.datasets.handlers import (
    BaseDatasetHandler,
    DatasetHandlerRegistry,
    HuggingFaceHandler,
    RoboflowHandler,
    VisDroneHandler,
)
from nectar.ai.detection.datasets.subset import SubsetCreator

_LAZY_ATTRS = {
    # Pulls matplotlib for plots
    "DatasetAnalyzer": "nectar.ai.detection.datasets.analyze",
    "DatasetMerger": "nectar.ai.detection.datasets.merge",
    "Stratifier": "nectar.ai.detection.datasets.stratify",
    # Pull huggingface_hub / datasets / roboflow
    "RoboflowUploader": "nectar.ai.detection.datasets.upload",
    "HuggingFaceDatasetUploader": "nectar.ai.detection.datasets.upload",
    "coco_to_hf": "nectar.ai.detection.datasets.hf_converter",
    "yolo_to_hf": "nectar.ai.detection.datasets.hf_converter",
    "hf_to_coco": "nectar.ai.detection.datasets.hf_converter",
    "hf_to_yolo": "nectar.ai.detection.datasets.hf_converter",
    "generate_dataset_card": "nectar.ai.detection.datasets.hf_converter",
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
    from nectar.ai.detection.datasets.analyze import DatasetAnalyzer
    from nectar.ai.detection.datasets.hf_converter import (
        coco_to_hf,
        generate_dataset_card,
        hf_to_coco,
        hf_to_yolo,
        yolo_to_hf,
    )
    from nectar.ai.detection.datasets.merge import DatasetMerger
    from nectar.ai.detection.datasets.stratify import Stratifier
    from nectar.ai.detection.datasets.upload import (
        HuggingFaceDatasetUploader,
        RoboflowUploader,
    )


__all__ = [
    "FormatDetector",
    "FormatConverter",
    "SubsetCreator",
    "Stratifier",
    "AugmentationBuilder",
    "DatasetAnalyzer",
    "DatasetHandlerRegistry",
    "BaseDatasetHandler",
    "RoboflowHandler",
    "VisDroneHandler",
    "HuggingFaceHandler",
    "DatasetMerger",
    "RoboflowUploader",
    "HuggingFaceDatasetUploader",
    "coco_to_hf",
    "yolo_to_hf",
    "hf_to_coco",
    "hf_to_yolo",
    "generate_dataset_card",
    "AUG_CONSERVATIVE",
    "AUG_AGGRESSIVE",
    "AUG_AERIAL",
    "AUG_INDUSTRIAL",
]
