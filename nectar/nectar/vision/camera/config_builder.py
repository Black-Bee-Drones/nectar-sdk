"""Build CameraConfig dataclasses from a field-name mapping."""

from __future__ import annotations

import os
from dataclasses import fields
from typing import Any, Callable, Dict, Optional, Type

from nectar.utils.dataclass_cli import dataclass_from_mapping
from nectar.vision.camera.config import (
    CameraConfig,
    FileImageConfig,
    RealSenseConfig,
    ROSConfig,
)
from nectar.vision.camera.factory import CameraFactory

ConfigBuilderFunc = Callable[[Dict[str, Any]], CameraConfig]

# CLI scalars for dataclass tuple fields. Not aliases of --width/--height.
_TUPLE_FIELDS: Dict[Type[CameraConfig], Dict[str, tuple[str, str]]] = {
    RealSenseConfig: {
        "color_res": ("color_width", "color_height"),
        "depth_res": ("depth_width", "depth_height"),
    }
}


def apply_tuple_fields(cls: Type[CameraConfig], params: Dict[str, Any]) -> Dict[str, Any]:
    """Fill tuple dataclass fields from ``*_width`` / ``*_height`` scalars when present."""
    mapping = _TUPLE_FIELDS.get(cls)
    if not mapping:
        return params
    out = dict(params)
    defaults = {f.name: f.default for f in fields(cls)}
    for field_name, (width_key, height_key) in mapping.items():
        if field_name in out:
            continue
        if width_key not in params and height_key not in params:
            continue
        current = defaults.get(field_name, (0, 0))
        width = int(params[width_key]) if width_key in params else int(current[0])
        height = int(params[height_key]) if height_key in params else int(current[1])
        out[field_name] = (width, height)
    return out


class ConfigBuilder:
    """Build a CameraConfig from a source key and a field mapping."""

    _builders: Dict[str, ConfigBuilderFunc] = {}

    @classmethod
    def register(cls, key: str, builder: ConfigBuilderFunc) -> None:
        """Register a custom builder that takes a dict and returns a CameraConfig."""
        cls._builders[key.lower()] = builder

    @classmethod
    def is_registered(cls, source: str) -> bool:
        """True when ``source`` has a custom builder or a factory config class."""
        key = source.lower()
        return key in cls._builders or CameraFactory.config_class(source) is not None

    @classmethod
    def build(cls, source: str, params: Optional[Dict[str, Any]] = None) -> CameraConfig:
        """
        Build config from source key and a dict of field names.

        Extra keys are ignored. A path that exists on disk or a string starting
        with ``/`` follows the same auto-detect rules as ``CameraFactory``.
        """
        params = dict(params or {})

        if os.path.isfile(source):
            if "path" not in params:
                params["path"] = source
            return dataclass_from_mapping(FileImageConfig, params)

        if source.startswith("/"):
            params = _infer_compressed(params, source)
            if "topic" not in params:
                params["topic"] = source
            return dataclass_from_mapping(ROSConfig, params)

        key = source.lower()
        custom = cls._builders.get(key)
        if custom is not None:
            return custom(params)

        config_cls = CameraFactory.config_class(source)
        if config_cls is None:
            return CameraConfig(name=source)

        if issubclass(config_cls, ROSConfig):
            params = _infer_compressed(params, source)
        params = apply_tuple_fields(config_cls, params)
        return dataclass_from_mapping(config_cls, params)


def _infer_compressed(params: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Set compressed=True when the topic name ends with /compressed."""
    if "compressed" in params:
        return params
    topic = params.get("topic")
    if topic is None and source.startswith("/"):
        topic = source
    if isinstance(topic, str) and topic.rstrip("/").endswith("/compressed"):
        out = dict(params)
        out["compressed"] = True
        return out
    return params
