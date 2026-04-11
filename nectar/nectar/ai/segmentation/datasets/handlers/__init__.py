"""Segmentation dataset download handlers."""

import logging
from typing import Dict, Optional, Type

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.segmentation.datasets.handlers.roboflow import RoboflowSegHandler
from nectar.ai.segmentation.datasets.handlers.ultralytics_seg import UltralyticsSegHandler

logger = logging.getLogger(__name__)


class SegDatasetHandlerRegistry:
    """Registry for segmentation dataset download handlers."""

    _handlers: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, handler_class: Type) -> None:
        cls._handlers[name.lower()] = handler_class
        logger.debug("Registered seg dataset handler: %s", name)

    @classmethod
    def get(cls, name: str) -> Optional[Type]:
        return cls._handlers.get(name.lower())

    @classmethod
    def list_handlers(cls) -> list:
        return list(cls._handlers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name.lower() in cls._handlers


def _register_builtin():
    SegDatasetHandlerRegistry.register("ultralytics", UltralyticsSegHandler)
    SegDatasetHandlerRegistry.register("roboflow", RoboflowSegHandler)


_register_builtin()

__all__ = [
    "BaseDatasetHandler",
    "UltralyticsSegHandler",
    "RoboflowSegHandler",
    "SegDatasetHandlerRegistry",
]
