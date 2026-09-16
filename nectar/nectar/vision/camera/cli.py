"""Argparse helpers that fill CameraConfig dataclasses."""

from __future__ import annotations

import argparse
from dataclasses import fields
from typing import Optional, Sequence, Tuple

from nectar.utils.dataclass_cli import add_dataclass_fields
from nectar.vision.camera.config import CameraConfig, RealSenseConfig
from nectar.vision.camera.config_builder import ConfigBuilder
from nectar.vision.camera.factory import CameraFactory

_TUPLE_CLI = {
    RealSenseConfig: {
        "color_res": ("color_width", "color_height"),
        "depth_res": ("depth_width", "depth_height"),
    }
}


def add_camera_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_source: str = "webcam",
) -> None:
    """Add ``--source`` and per-driver flags generated from config dataclasses."""
    keys = CameraFactory.registered_keys()
    parser.add_argument(
        "--source",
        default=default_source,
        help=(
            "Camera source: a registered key "
            f"({', '.join(keys)}), a ROS topic (starts with '/'), or a file path"
        ),
    )

    added: set[str] = set()
    seen_cls: set[type] = set()
    for key in keys:
        config_cls = CameraFactory.config_class(key)
        if config_cls is None or config_cls is CameraConfig or config_cls in seen_cls:
            continue
        seen_cls.add(config_cls)
        aliases = [k for k in keys if CameraFactory.config_class(k) is config_cls]
        group = parser.add_argument_group(
            f"{'/'.join(aliases)} (when --source {'/'.join(aliases)})"
        )
        add_dataclass_fields(
            parser,
            config_cls,
            group=group,
            exclude=("name",),
            added=added,
        )
        _add_tuple_flags(group, config_cls, added)


def camera_config_from_args(args: argparse.Namespace) -> Tuple[str, CameraConfig]:
    """Return ``(source, config)`` from a parsed namespace."""
    source = str(getattr(args, "source", "webcam"))
    params = {k: v for k, v in vars(args).items() if k != "source"}
    return source, ConfigBuilder.build(source, params)


def parse_camera_args(
    parser: argparse.ArgumentParser,
    argv: Optional[Sequence[str]] = None,
) -> Tuple[argparse.Namespace, list[str], str, CameraConfig]:
    """``parse_known_args`` plus ``camera_config_from_args``."""
    args, rest = parser.parse_known_args(argv)
    source, config = camera_config_from_args(args)
    return args, rest, source, config


def _add_tuple_flags(
    group: argparse._ActionsContainer,
    config_cls: type,
    added: set[str],
) -> None:
    mapping = _TUPLE_CLI.get(config_cls)
    if not mapping:
        return
    defaults = {f.name: f.default for f in fields(config_cls)}
    for field_name, (width_key, height_key) in mapping.items():
        default = defaults.get(field_name, (0, 0))
        for scalar, index in ((width_key, 0), (height_key, 1)):
            if scalar in added:
                continue
            group.add_argument(
                f"--{scalar.replace('_', '-')}",
                dest=scalar,
                type=int,
                default=argparse.SUPPRESS,
                help=f"{config_cls.__name__}.{field_name}[{index}] (default: {default[index]})",
            )
            added.add(scalar)
