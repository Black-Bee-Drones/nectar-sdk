"""Dataset download handlers."""

from nectar.ai.core.registry import HandlerRegistry
from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.detection.datasets.handlers.huggingface import HuggingFaceHandler
from nectar.ai.detection.datasets.handlers.roboflow import RoboflowHandler
from nectar.ai.detection.datasets.handlers.visdrone import VisDroneHandler


class DatasetHandlerRegistry(HandlerRegistry):
    """Registry for dataset download handlers."""

    _handlers: dict = {}


def register_builtin_handlers():
    """Register built-in dataset handlers."""
    DatasetHandlerRegistry.register("visdrone", VisDroneHandler)
    DatasetHandlerRegistry.register("roboflow", RoboflowHandler)
    DatasetHandlerRegistry.register("huggingface", HuggingFaceHandler)
    DatasetHandlerRegistry.register("hf", HuggingFaceHandler)


register_builtin_handlers()

__all__ = [
    "BaseDatasetHandler",
    "RoboflowHandler",
    "VisDroneHandler",
    "HuggingFaceHandler",
    "DatasetHandlerRegistry",
]
