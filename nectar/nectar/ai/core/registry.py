"""Generic name → class registry for dataset handlers and similar factories."""

import logging
from typing import Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """
    Simple registry mapping lowercase names to handler classes.

    Task packages typically subclass or wrap this with a dedicated name
    (e.g. ``ClsDatasetHandlerRegistry``) and register built-in handlers.
    """

    _handlers: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, handler_class: Type) -> None:
        cls._handlers[name.lower()] = handler_class
        logger.debug("Registered handler: %s", name)

    @classmethod
    def get(cls, name: str) -> Optional[Type]:
        return cls._handlers.get(name.lower())

    @classmethod
    def list_handlers(cls) -> List[str]:
        return list(cls._handlers.keys())

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name.lower() in cls._handlers
