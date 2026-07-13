"""Segmentation dataset download handlers."""

from nectar.ai.core.registry import HandlerRegistry
from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.segmentation.datasets.handlers.huggingface import HuggingFaceSegHandler
from nectar.ai.segmentation.datasets.handlers.roboflow import RoboflowSegHandler
from nectar.ai.segmentation.datasets.handlers.ultralytics_seg import UltralyticsSegHandler


class SegDatasetHandlerRegistry(HandlerRegistry):
    """Registry for segmentation dataset download handlers."""

    _handlers: dict = {}


def _register_builtin():
    SegDatasetHandlerRegistry.register("ultralytics", UltralyticsSegHandler)
    SegDatasetHandlerRegistry.register("roboflow", RoboflowSegHandler)
    SegDatasetHandlerRegistry.register("huggingface", HuggingFaceSegHandler)
    SegDatasetHandlerRegistry.register("hf", HuggingFaceSegHandler)


_register_builtin()

__all__ = [
    "BaseDatasetHandler",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
    "HuggingFaceSegHandler",
    "SegDatasetHandlerRegistry",
]
