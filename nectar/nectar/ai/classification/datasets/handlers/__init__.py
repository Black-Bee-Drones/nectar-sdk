"""Classification dataset download handlers."""

from nectar.ai.classification.datasets.handlers.huggingface import HuggingFaceClsHandler
from nectar.ai.classification.datasets.handlers.roboflow import RoboflowClsHandler
from nectar.ai.classification.datasets.handlers.ultralytics_cls import UltralyticsClsHandler
from nectar.ai.core.registry import HandlerRegistry
from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler


class ClsDatasetHandlerRegistry(HandlerRegistry):
    """Registry for classification dataset download handlers."""

    _handlers: dict = {}


def _register_builtin():
    ClsDatasetHandlerRegistry.register("ultralytics", UltralyticsClsHandler)
    ClsDatasetHandlerRegistry.register("roboflow", RoboflowClsHandler)
    ClsDatasetHandlerRegistry.register("huggingface", HuggingFaceClsHandler)
    ClsDatasetHandlerRegistry.register("hf", HuggingFaceClsHandler)


_register_builtin()

__all__ = [
    "BaseDatasetHandler",
    "UltralyticsClsHandler",
    "RoboflowClsHandler",
    "HuggingFaceClsHandler",
    "ClsDatasetHandlerRegistry",
]
