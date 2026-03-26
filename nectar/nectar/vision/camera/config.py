from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class QoSReliability(Enum):
    BEST_EFFORT = "best_effort"
    RELIABLE = "reliable"


class QoSDurability(Enum):
    VOLATILE = "volatile"
    TRANSIENT_LOCAL = "transient_local"


@dataclass(frozen=True)
class CameraConfig:
    name: str = "camera"


@dataclass(frozen=True)
class ROSConfig(CameraConfig):
    topic: str = "/image_raw"
    compressed: bool = False
    reliability: QoSReliability = QoSReliability.BEST_EFFORT
    durability: QoSDurability = QoSDurability.VOLATILE
    history_depth: int = 1
    encoding: str = "bgr8"


@dataclass(frozen=True)
class ROSDepthConfig(ROSConfig):
    depth_topic: str = "/camera/depth/image_rect_raw"
    depth_compressed: bool = False
    depth_encoding: str = "passthrough"
    enable_depth: bool = True


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
    buffer_size: Optional[int] = 2
    threaded: bool = True


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
    brightness: Optional[float] = None


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


@dataclass(frozen=True)
class T265Config(CameraConfig):
    name: str = "t265_cam"
    enable_pose: bool = True
    enable_depth: bool = True
    stereo_fov_deg: float = 90.0
    stereo_height_px: int = 300
    num_disparities: int = 96
    block_size: int = 16
    use_ros_topics: bool = False
    fisheye1_topic: str = "/camera/fisheye1/image_raw"
    fisheye2_topic: str = "/camera/fisheye2/image_raw"
    pose_topic: str = "/camera/pose/sample"
