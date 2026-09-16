"""Build argparse flags from dataclass fields and the reverse mapping."""

from __future__ import annotations

import argparse
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from typing import Any, Optional, Sequence, Union, get_args, get_origin, get_type_hints


def unwrap_optional(annotation: Any) -> Any:
    """Return ``T`` from ``Optional[T]`` / ``T | None``, else ``annotation``."""
    origin = get_origin(annotation)
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def is_tuple_type(annotation: Any) -> bool:
    """True when the annotation is a tuple type (after unwrapping Optional)."""
    return get_origin(unwrap_optional(annotation)) is tuple


def convert_value(value: Any, annotation: Any) -> Any:
    """Coerce a CLI/dict value to the dataclass field type."""
    inner = unwrap_optional(annotation)
    if value is None:
        return None
    if isinstance(inner, type) and issubclass(inner, Enum):
        if isinstance(value, inner):
            return value
        return inner(value)
    origin = get_origin(inner)
    if origin is tuple:
        return tuple(value) if not isinstance(value, tuple) else value
    return value


def dataclass_from_mapping(cls: type, params: dict[str, Any]) -> Any:
    """Construct ``cls`` using only declared fields present in ``params``."""
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for field in fields(cls):
        if field.name not in params:
            continue
        kwargs[field.name] = convert_value(params[field.name], hints.get(field.name, field.type))
    return cls(**kwargs)


def mapping_from_namespace(args: argparse.Namespace) -> dict[str, Any]:
    """Namespace to dict, dropping argparse internals."""
    return dict(vars(args))


def add_dataclass_fields(
    parser: argparse.ArgumentParser,
    cls: type,
    *,
    group: Optional[argparse._ActionsContainer] = None,
    exclude: Sequence[str] = (),
    added: Optional[set[str]] = None,
    suppress_defaults: bool = True,
) -> set[str]:
    """
    Add one flag per dataclass field.

    Tuple fields are skipped (callers add scalar stand-ins). Dest names already
    in ``added`` are skipped so shared fields are declared once.
    """
    if added is None:
        added = set()
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    target = group if group is not None else parser
    exclude_set = set(exclude)
    hints = get_type_hints(cls)

    for field in fields(cls):
        if field.name in exclude_set or field.name in added:
            continue
        annotation = hints.get(field.name, field.type)
        if is_tuple_type(annotation):
            continue

        inner = unwrap_optional(annotation)
        flag = f"--{field.name.replace('_', '-')}"
        default = field.default if field.default is not MISSING else None
        help_text = f"{cls.__name__}.{field.name} (default: {_help_default(default)})"
        kwargs: dict[str, Any] = {"dest": field.name, "help": help_text}
        if suppress_defaults:
            kwargs["default"] = argparse.SUPPRESS

        if isinstance(inner, type) and issubclass(inner, Enum):
            kwargs["type"] = str
            kwargs["choices"] = [item.value for item in inner]
        elif inner is bool:
            kwargs["action"] = argparse.BooleanOptionalAction
        elif inner is int:
            kwargs["type"] = int
        elif inner is float:
            kwargs["type"] = float
        elif inner is str:
            kwargs["type"] = str
        else:
            continue

        target.add_argument(flag, **kwargs)
        added.add(field.name)

    return added


def _help_default(default: Any) -> Any:
    if isinstance(default, Enum):
        return default.value
    return default
