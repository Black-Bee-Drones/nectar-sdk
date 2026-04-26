"""Dataset management utilities for object detection."""

from nectar.ai.detection.datasets.analyze import DatasetAnalyzer
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
from nectar.ai.detection.datasets.hf_converter import (
    coco_to_hf,
    generate_dataset_card,
    hf_to_coco,
    hf_to_yolo,
    yolo_to_hf,
)
from nectar.ai.detection.datasets.merge import DatasetMerger
from nectar.ai.detection.datasets.stratify import Stratifier
from nectar.ai.detection.datasets.subset import SubsetCreator
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
