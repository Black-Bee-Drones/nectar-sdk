from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CameraConfig:
    name: str = "camera"


@dataclass(frozen=True)
class ROSConfig(CameraConfig):
    topic: str = "/image_raw"
    compressed: bool = False


@dataclass(frozen=True)
class FileImageConfig(CameraConfig):
    path: str = ""


@dataclass(frozen=True)
class OpenCVConfig(CameraConfig):
    device_index: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = 30
    fourcc: Optional[str] = "MJPG"
    autofocus: Optional[bool] = None
    focus: Optional[int] = None


@dataclass(frozen=True)
class C920Config(CameraConfig):
    profile: int = 1  # 0: 640x480, 1:1280x720, 2:1920x1080
    fallback_device_index: int = 0


@dataclass(frozen=True)
class IMX219Config(CameraConfig):
    sensor_id: int = 0
    width: int = 1920
    height: int = 1080
    fps: int = 30
    flip: int = 0
    name: str = "imx219_cam"


@dataclass(frozen=True)
class RealSenseConfig(CameraConfig):
    color_res: Tuple[int, int] = (640, 480)
    depth_res: Tuple[int, int] = (640, 480)
    fps: int = 30
    align_to_color: bool = True
    name: str = "realsense_cam"
    enable_depth: bool = True
    # ROS topic mode (when camera is already used by another node like Isaac ROS VSLAM)
    use_ros_topics: bool = False
    color_topic: str = "/camera/color/image_raw"
    depth_topic: str = "/camera/depth/image_rect_raw"
    color_compressed: bool = True
    depth_compressed: bool = False


@dataclass(frozen=True)
class OakDConfig(CameraConfig):
    cam_num: int = 1  # 1: rgb, 2: left mono, 3: right mono
    enable_depth: bool = False
    name: str = "oakd_cam"
