"""Segmentation model implementations.

Each model class is loaded lazily. Importing this package does
not pull torch / ultralytics / transformers / rfdetr.
"""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "RFDETRSegModel": "nectar.ai.segmentation.models.rfdetr",
    "TransformersSegModel": "nectar.ai.segmentation.models.transformers",
    "UltralyticsSegModel": "nectar.ai.segmentation.models.ultralytics",
    "SegmentationDataset": "nectar.ai.segmentation.models.dataset",
    "load_segmentation_dataset": "nectar.ai.segmentation.models.dataset",
    "CocoInstanceSegDataset": "nectar.ai.segmentation.models.dataset",
    "instance_seg_collate_fn": "nectar.ai.segmentation.models.dataset",
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
    from nectar.ai.segmentation.models.dataset import (
        CocoInstanceSegDataset,
        SegmentationDataset,
        instance_seg_collate_fn,
        load_segmentation_dataset,
    )
    from nectar.ai.segmentation.models.rfdetr import RFDETRSegModel
    from nectar.ai.segmentation.models.transformers import TransformersSegModel
    from nectar.ai.segmentation.models.ultralytics import UltralyticsSegModel


__all__ = [
    "UltralyticsSegModel",
    "TransformersSegModel",
    "RFDETRSegModel",
    "SegmentationDataset",
    "load_segmentation_dataset",
    "CocoInstanceSegDataset",
    "instance_seg_collate_fn",
]
