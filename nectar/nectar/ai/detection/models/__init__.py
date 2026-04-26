"""
Detection model implementations.
"""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "ModelLoader": "nectar.ai.detection.models.model_loader",
    "UltralyticsModel": "nectar.ai.detection.models.ultralytics",
    "TransformersModel": "nectar.ai.detection.models.transformers",
    "RFDETRModel": "nectar.ai.detection.models.rfdetr",
    "CocoDetectionDataset": "nectar.ai.detection.models.dataset",
    "DetectionDataset": "nectar.ai.detection.models.dataset",
    "load_detection_dataset": "nectar.ai.detection.models.dataset",
    "collate_fn": "nectar.ai.detection.models.dataset",
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
    from nectar.ai.detection.models.dataset import (
        CocoDetectionDataset,
        DetectionDataset,
        collate_fn,
        load_detection_dataset,
    )
    from nectar.ai.detection.models.model_loader import ModelLoader
    from nectar.ai.detection.models.rfdetr import RFDETRModel
    from nectar.ai.detection.models.transformers import TransformersModel
    from nectar.ai.detection.models.ultralytics import UltralyticsModel


__all__ = [
    "ModelLoader",
    "UltralyticsModel",
    "TransformersModel",
    "RFDETRModel",
    "CocoDetectionDataset",
    "DetectionDataset",
    "load_detection_dataset",
    "collate_fn",
]
