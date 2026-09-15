from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from subprocess import run as run_shell
import shlex
import traceback


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

    @classmethod
    def config_by_name(
        cls,
        name: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[int] = 30,
        fourcc: Optional[str] = "MJPG",
        autofocus: Optional[bool] = None,
        focus: Optional[int] = None,
        buffer_size: Optional[int] = 2,
        threaded: bool = True
        ) -> 'OpenCVConfig':
        """
        Retrieves the V4L2 video device index for a specified camera name and
        returns a new OpenCVConfig instance.

        This function executes system shell commands to parse the output of
        'v4l2-ctl --list-devices' and extracts the first matching video
        node index (e.g., uses 0 for '/dev/video0').

        Parameters
        ----------
        name : str
            The name or partial name of the camera to search for.
        width : int, optional
            Width of the camera frame.
        height : int, optional
            Height of the camera frame.
        fps : int, optional
            Frames per second.
        fourcc : str, optional
            FourCC code for the video codec.
        autofocus : bool, optional
            Enable or disable autofocus.
        focus : int, optional
            Manual focus value.
        buffer_size : int, optional
            OpenCV internal buffer size.
        threaded : bool
            Enable threaded camera reading.

        Returns
        -------
        OpenCVConfig
            An instance of OpenCVConfig configured with the found device index.
            If the camera is not found, or command fails, the device_index
            defaults to -1.

        Notes
        -----
        This function is Linux-specific and requires the 'v4l2-utils' package
        to be installed on the system to run the 'v4l2-ctl' command.

        WARNING - MULTIPLE IDENTICAL CAMERAS:
        -------------------------------------
        If using multiple cameras of the exact same model (e.g., front and back),
        the OS USB initialization order is non-deterministic. This means `instance=0`
        might swap between the physical front and back cameras upon reboot.

        To guarantee deterministic mapping, do not use this factory method based on
        camera names. Instead, create UDEV rules (e.g., `/dev/video_front`) in the OS
        and use the default constructor directly, or pass the hardware USB path
        (e.g., "14.0-1") as the 'name' parameter.
        """

        kwargs = locals().copy()
        kwargs.pop('cls')

        safe_name = shlex.quote(name)

        cmd = f'v4l2-ctl --list-devices | grep -i {safe_name} -A 4 | grep -o "video[0-9]\\+" | head -n 1 | grep -o "[0-9]\\+"'

        try:
            result = run_shell(cmd, shell=True, capture_output=True, text=True)
            idx = result.stdout.strip()

            if not idx:
                print(f"Warning: Camera '{name}' not found. Defaulting to index -1.")
                idx = -1

            kwargs['device_index'] = int(idx)
            return cls(**kwargs)

        except Exception as e:
            print(f"Error executing v4l2-ctl (is v4l2-utils installed?): {e}")
            traceback.print_exc()
            kwargs["device_index"] = -1
            return cls(**kwargs)


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
    # StereoSGBM parameters
    num_disparities: int = 96
    block_size: int = 16
    uniqueness_ratio: int = 10
    speckle_window_size: int = 100
    speckle_range: int = 32
    smoothness_window: int = 5
    max_depth_m: float = 3.0
    # Access mode
    use_ros_topics: bool = False
    fisheye1_topic: str = "/camera/fisheye1/image_raw"
    fisheye2_topic: str = "/camera/fisheye2/image_raw"
    pose_topic: str = "/camera/pose/sample"

def main():
    cam_config = OpenCVConfig()
