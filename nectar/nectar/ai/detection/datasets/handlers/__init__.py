"""Dataset download handlers."""

import logging
from typing import Dict, Optional, Type

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.detection.datasets.handlers.roboflow import RoboflowHandler
from nectar.ai.detection.datasets.handlers.visdrone import VisDroneHandler

logger = logging.getLogger(__name__)


class DatasetHandlerRegistry:
    """
    Registry for dataset download handlers.

    Handlers can be registered and retrieved by name.
    """

    _handlers: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, handler_class: Type) -> None:
        """
        Register a dataset handler.

        Parameters
        ----------
        name : str
            Handler name (e.g., "visdrone", "roboflow").
        handler_class : Type
            Handler class.
        """
        cls._handlers[name.lower()] = handler_class
        logger.debug("Registered dataset handler: %s", name)

    @classmethod
    def get(cls, name: str) -> Optional[Type]:
        """
        Get a handler by name.

        Parameters
        ----------
        name : str
            Handler name.

        Returns
        -------
        Type or None
            Handler class if found, None otherwise.
        """
        return cls._handlers.get(name.lower())

    @classmethod
    def list_handlers(cls) -> list:
        """
        List all registered handlers.

        Returns
        -------
        list
            List of handler names.
        """
        return list(cls._handlers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a handler is registered.

        Parameters
        ----------
        name : str
            Handler name.

        Returns
        -------
        bool
            True if registered, False otherwise.
        """
        return name.lower() in cls._handlers


def register_builtin_handlers():
    """Register built-in dataset handlers."""
    DatasetHandlerRegistry.register("visdrone", VisDroneHandler)
    DatasetHandlerRegistry.register("roboflow", RoboflowHandler)


register_builtin_handlers()

__all__ = [
    "BaseDatasetHandler",
    "RoboflowHandler",
    "VisDroneHandler",
    "DatasetHandlerRegistry",
]
