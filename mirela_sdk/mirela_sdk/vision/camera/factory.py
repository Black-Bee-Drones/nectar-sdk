from __future__ import annotations

import os
from typing import Dict, Optional, Type

from rclpy.node import Node

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.drivers import (
    ROSCam,
    ROSDepthCam,
    FileImageCam,
    OpenCVCam,
    C920Cam,
    IMX219Cam,
    RealsenseCam,
    OakdCam,
)
from mirela_sdk.vision.camera.config import (
    CameraConfig,
    ROSConfig,
    ROSDepthConfig,
    FileImageConfig,
    OpenCVConfig,
    C920Config,
    IMX219Config,
    RealSenseConfig,
    OakDConfig,
)


class CameraFactory:
    """
    Factory for creating camera instances from source identifiers.

    Attributes
    ----------
    _builders : dict
        Registry mapping source keys to camera classes.
    """

    _builders: Dict[str, Type[AbstractCam]] = {}

    @classmethod
    def register(cls, key: str, builder: Type[AbstractCam]) -> None:
        """
        Register a camera class with a source key.

        Parameters
        ----------
        key : str
            Source identifier (case-insensitive).
        builder : Type[AbstractCam]
            Camera class to instantiate for this key.
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
            return FileImageCam(config or FileImageConfig(path=source))

        if source.startswith("/"):
            return ROSCam(node, config or ROSConfig(topic=source))

        key = source.lower()
        builder = cls._builders.get(key)

        if not builder:
            raise ValueError(f"Unknown camera source type: {source}")

        if config is None:
            if key == "realsense":
                config = RealSenseConfig()
            elif key == "webcam":
                config = OpenCVConfig()
            elif key == "c920":
                config = C920Config()
            elif key == "imx219":
                config = IMX219Config()
            elif key == "oakd":
                config = OakDConfig()
            else:
                config = CameraConfig(name=key)

        if builder is ROSCam:
            if not isinstance(config, ROSConfig):
                raise ValueError("ROSCam requires a ROSConfig.")
            return builder(node, config)

        if builder is ROSDepthCam:
            if not isinstance(config, ROSDepthConfig):
                raise ValueError("ROSDepthCam requires a ROSDepthConfig.")
            if node is None:
                raise ValueError("ROSDepthCam requires a ROS node.")
            return builder(node, config)

        if builder is OakdCam:
            if not isinstance(config, OakDConfig):
                raise ValueError("OakdCam requires an OakDConfig.")
            return builder(config)

        if builder is RealsenseCam:
            if isinstance(config, RealSenseConfig) and config.use_ros_topics:
                if node is None:
                    raise ValueError(
                        "RealsenseCam with use_ros_topics=True requires a ROS node. "
                        "Consider using ROSDepthCam instead."
                    )
                return builder(config, node)
            return builder(config)

        return builder(config)


CameraFactory.register("realsense", RealsenseCam)
CameraFactory.register("webcam", OpenCVCam)
CameraFactory.register("opencv", OpenCVCam)
CameraFactory.register("c920", C920Cam)
CameraFactory.register("imx219", IMX219Cam)
CameraFactory.register("oakd", OakdCam)
CameraFactory.register("ros", ROSCam)
CameraFactory.register("ros_depth", ROSDepthCam)
CameraFactory.register("file", FileImageCam)
