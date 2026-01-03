from __future__ import annotations

import os
from typing import Dict, Optional, Type

from rclpy.node import Node

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.drivers import (
    ROSCam,
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
    FileImageConfig,
    OpenCVConfig,
    C920Config,
    IMX219Config,
    RealSenseConfig,
    OakDConfig,
)


class CameraFactory:
    _builders: Dict[str, Type[AbstractCam]] = {}

    @classmethod
    def register(cls, key: str, builder: Type[AbstractCam]) -> None:
        cls._builders[key.lower()] = builder

    @classmethod
    def from_source(
        cls,
        source: str,
        *,
        config: Optional[CameraConfig] = None,
        node: Optional[Node] = None,
    ) -> AbstractCam:
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

        if builder is OakdCam:
            if not isinstance(config, OakDConfig):
                raise ValueError("OakdCam requires an OakDConfig.")
            return builder(config)

        if builder is RealsenseCam:
            if isinstance(config, RealSenseConfig) and config.use_ros_topics:
                if node is None:
                    raise ValueError(
                        "RealsenseCam with use_ros_topics=True requires a ROS node."
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
CameraFactory.register("file", FileImageCam)
