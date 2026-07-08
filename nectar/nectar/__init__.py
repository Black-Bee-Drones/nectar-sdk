"""Nectar SDK top-level package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "init",
    "shutdown",
    "use_executor",
    "get_executor",
    "add_node",
    "remove_node",
    "is_initialized",
    "owns_executor",
    "spin",
]

if TYPE_CHECKING:
    from nectar.runtime import (
        add_node,
        get_executor,
        init,
        is_initialized,
        owns_executor,
        remove_node,
        shutdown,
        spin,
        use_executor,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        from nectar import runtime

        return getattr(runtime, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
