from __future__ import annotations

import os
from typing import Callable, Dict, Optional

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

# Builder signature: (config, node) -> AbstractCam.
# Each built-in builder lazily imports its driver module so that the
# factory module itself does not pull pyrealsense2, depthai, etc.
_BuilderFunc = Callable[[Optional[CameraConfig], Optional[Node]], AbstractCam]


def _build_opencv(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.opencv_cam import OpenCVCam

    return OpenCVCam(config or OpenCVConfig())


def _build_c920(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.c920_cam import C920Cam

    return C920Cam(config or C920Config())


def _build_imx219(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.imx219_cam import IMX219Cam

    return IMX219Cam(config or IMX219Config())


def _build_realsense(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.realsense_cam import RealsenseCam

    cfg = config or RealSenseConfig()
    if isinstance(cfg, RealSenseConfig) and cfg.use_ros_topics:
        if node is None:
            raise ValueError(
                "RealsenseCam with use_ros_topics=True requires a ROS node. "
                "Consider using ROSDepthCam instead."
            )
        return RealsenseCam(cfg, node)
    return RealsenseCam(cfg)


def _build_t265(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.t265_cam import T265Cam

    cfg = config or T265Config()
    if isinstance(cfg, T265Config) and cfg.use_ros_topics:
        if node is None:
            raise ValueError("T265Cam with use_ros_topics=True requires a ROS node.")
        return T265Cam(cfg, node)
    return T265Cam(cfg)


def _build_oakd(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.oakd_cam import OakdCam

    return OakdCam(config or OakDConfig())


def _build_ros(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.ros_cam import ROSCam

    cfg = config or ROSConfig()
    if not isinstance(cfg, ROSConfig):
        raise ValueError("ROSCam requires a ROSConfig.")
    return ROSCam(node, cfg)


def _build_ros_depth(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.ros_depth_cam import ROSDepthCam

    cfg = config or ROSDepthConfig()
    if not isinstance(cfg, ROSDepthConfig):
        raise ValueError("ROSDepthCam requires a ROSDepthConfig.")
    if node is None:
        raise ValueError("ROSDepthCam requires a ROS node.")
    return ROSDepthCam(node, cfg)


def _build_file(config: Optional[CameraConfig], node: Optional[Node]) -> AbstractCam:
    from nectar.vision.camera.drivers.file_cam import FileImageCam

    return FileImageCam(config or FileImageConfig())


_BUILTINS: Dict[str, _BuilderFunc] = {
    "webcam": _build_opencv,
    "opencv": _build_opencv,
    "c920": _build_c920,
    "imx219": _build_imx219,
    "realsense": _build_realsense,
    "t265": _build_t265,
    "oakd": _build_oakd,
    "ros": _build_ros,
    "ros_depth": _build_ros_depth,
    "file": _build_file,
}


class CameraFactory:
    """
    Factory for creating camera instances from source identifiers.

    Built-in drivers are loaded lazily on first use to keep the import
    cost of ``nectar.vision`` low (no eager pyrealsense2 / depthai /
    mediapipe loads).

    Attributes
    ----------
    _builders : dict
        Registry mapping source keys to builder callables or camera
        classes registered via :meth:`register`. Built-in drivers live
        in a separate internal registry.
    """

    _builders: Dict[str, _BuilderFunc] = {}

    @classmethod
    def register(cls, key: str, builder) -> None:
        """
        Register a camera builder under ``key``.

        Parameters
        ----------
        key : str
            Source identifier (case-insensitive).
        builder : Type[AbstractCam] or callable
            Either a camera class instantiated as ``builder(config)``,
            or a callable with signature ``(config, node) -> AbstractCam``.
        """
        cls._builders[key.lower()] = builder

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
            ROS2 node required for ROSCam and RealsenseCam with ROS topics.

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
            from nectar.vision.camera.drivers.file_cam import FileImageCam

            return FileImageCam(config or FileImageConfig(path=source))

        if source.startswith("/"):
            from nectar.vision.camera.drivers.ros_cam import ROSCam

            return ROSCam(node, config or ROSConfig(topic=source))

        key = source.lower()

        # User-registered builders take precedence over built-ins.
        external = cls._builders.get(key)
        if external is not None:
            if isinstance(external, type):
                return external(config or CameraConfig(name=key))
            return external(config, node)

        builtin = _BUILTINS.get(key)
        if builtin is None:
            raise ValueError(f"Unknown camera source type: {source}")

        return builtin(config, node)
