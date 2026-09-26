from __future__ import annotations

import os
from importlib import import_module
from typing import Callable, Dict, NamedTuple, Optional, Type, Union

from rclpy.node import Node

from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import (
    C920Config,
    CameraConfig,
    FileImageConfig,
    IMX219Config,
    OakDConfig,
    OpenCVConfig,
    RealSenseConfig,
    ROSConfig,
    ROSDepthConfig,
    T265Config,
)

_BuilderFunc = Callable[[Optional[CameraConfig], Optional[Node]], AbstractCam]
_ExternalBuilder = Union[Type[AbstractCam], _BuilderFunc]


class _Spec(NamedTuple):
    module: str
    class_name: str
    config_cls: Type[CameraConfig]
    pass_node: bool = False


_OPENCV = _Spec("nectar.vision.camera.drivers.opencv_cam", "OpenCVCam", OpenCVConfig)

_BUILTINS: Dict[str, _Spec] = {
    "webcam": _OPENCV,
    "opencv": _OPENCV,
    "c920": _Spec("nectar.vision.camera.drivers.c920_cam", "C920Cam", C920Config),
    "imx219": _Spec("nectar.vision.camera.drivers.imx219_cam", "IMX219Cam", IMX219Config),
    "realsense": _Spec(
        "nectar.vision.camera.drivers.realsense_cam",
        "RealsenseCam",
        RealSenseConfig,
        True,
    ),
    "t265": _Spec("nectar.vision.camera.drivers.t265_cam", "T265Cam", T265Config, True),
    "oakd": _Spec("nectar.vision.camera.drivers.oakd_cam", "OakdCam", OakDConfig),
    "ros": _Spec("nectar.vision.camera.drivers.ros_cam", "ROSCam", ROSConfig, True),
    "ros_depth": _Spec(
        "nectar.vision.camera.drivers.ros_depth_cam",
        "ROSDepthCam",
        ROSDepthConfig,
        True,
    ),
    "file": _Spec("nectar.vision.camera.drivers.file_cam", "FileImageCam", FileImageConfig),
}


def _instantiate(
    spec: _Spec,
    config: Optional[CameraConfig],
    node: Optional[Node],
    *,
    source: str,
) -> AbstractCam:
    if config is not None and not isinstance(config, spec.config_cls):
        raise ValueError(
            f"Source {source!r} requires {spec.config_cls.__name__}, got {type(config).__name__}"
        )
    cam_cls = getattr(import_module(spec.module), spec.class_name)
    cfg = spec.config_cls() if config is None else config
    if spec.pass_node:
        return cam_cls(cfg, node=node)
    return cam_cls(cfg)


class CameraFactory:
    """
    Factory for creating camera instances from source identifiers.

    Built-in drivers are loaded lazily on first use to keep the import
    cost of ``nectar.vision`` low (no eager pyrealsense2 / depthai /
    mediapipe loads).
    """

    _builders: Dict[str, _ExternalBuilder] = {}
    _config_classes: Dict[str, Type[CameraConfig]] = {}

    @classmethod
    def register(
        cls,
        key: str,
        builder: _ExternalBuilder,
        *,
        config_cls: Optional[Type[CameraConfig]] = None,
    ) -> None:
        """
        Register a camera builder under ``key``.

        Parameters
        ----------
        key : str
            Source identifier (case-insensitive).
        builder : Type[AbstractCam] or callable
            Either a camera class instantiated as ``builder(config)``,
            or a callable with signature ``(config, node) -> AbstractCam``.
        config_cls : type of CameraConfig, optional
            Dataclass used to build config for this key (CLI and ConfigBuilder).
        """
        cls._builders[key.lower()] = builder
        if config_cls is not None:
            cls._config_classes[key.lower()] = config_cls

    @classmethod
    def config_class(cls, source: str) -> Optional[Type[CameraConfig]]:
        """Return the CameraConfig subclass registered for ``source``, if any."""
        key = source.lower()
        if key in cls._config_classes:
            return cls._config_classes[key]
        builtin = _BUILTINS.get(key)
        return builtin.config_cls if builtin is not None else None

    @classmethod
    def registered_keys(cls) -> list[str]:
        """Driver keys in registration order (built-ins first)."""
        keys = list(_BUILTINS.keys())
        for key in cls._builders:
            if key not in _BUILTINS:
                keys.append(key)
        return keys

    @classmethod
    def is_registered(cls, source: str) -> bool:
        """True when ``source`` is a registered driver key."""
        key = source.lower()
        return key in _BUILTINS or key in cls._builders

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        config: Optional[CameraConfig] = None,
        node: Optional[Node] = None,
    ) -> AbstractCam:
        """
        Create camera instance from source identifier.

        Automatically detects source type:
        - File path: creates FileImageCam
        - ROS topic (starts with '/'): creates ROSCam
        - Registered key: creates corresponding camera

        Parameters
        ----------
        source : str
            Source identifier. Can be file path, ROS topic, or
            registered key ('webcam', 'realsense', 'c920', etc.).
        config : CameraConfig, optional
            Camera configuration. Auto-generated if not provided.
        node : Node, optional
            Forwarded to drivers that subscribe to ROS topics. Omitted, those
            drivers create an internal node.

        Returns
        -------
        AbstractCam
            Configured camera instance ready for start().

        Raises
        ------
        ValueError
            If source type is unknown or config type mismatches.
        """
        if os.path.isfile(source):
            cfg = config if isinstance(config, FileImageConfig) else FileImageConfig(path=source)
            return _instantiate(_BUILTINS["file"], cfg, node, source=source)

        if source.startswith("/"):
            cfg = ROSConfig(topic=source) if config is None else config
            return _instantiate(_BUILTINS["ros"], cfg, node, source=source)

        key = source.lower()

        external = cls._builders.get(key)
        if external is not None:
            if isinstance(external, type):
                return external(config or CameraConfig(name=key))
            return external(config, node)

        builtin = _BUILTINS.get(key)
        if builtin is None:
            raise ValueError(f"Unknown camera source type: {source}")

        return _instantiate(builtin, config, node, source=key)
