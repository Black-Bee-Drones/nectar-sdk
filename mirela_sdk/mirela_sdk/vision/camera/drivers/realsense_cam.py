import warnings
from typing import Optional

import numpy as np

from mirela_sdk.vision.camera.abstract import DepthCam
from mirela_sdk.vision.camera.config import RealSenseConfig

try:
    import pyrealsense2 as rs

    REALSENSE_AVAILABLE = True
except ImportError:
    rs = None
    REALSENSE_AVAILABLE = False


class RealsenseCam(DepthCam):
    """
    Camera driver for Intel RealSense depth cameras via pyrealsense2 SDK.

    For direct hardware access when camera is not shared with other nodes.
    Use ROSDepthCam for ROS topic mode (e.g., when sharing with VSLAM).

    Parameters
    ----------
    config : RealSenseConfig
        Configuration with resolution, FPS, and depth settings.

    Raises
    ------
    RuntimeError
        If pyrealsense2 is not installed.

    Notes
    -----
    Depth frames are returned in meters (float32). The align_to_color option
    registers depth to color frame for pixel-accurate RGB-D correspondence.

    Examples
    --------
    >>> from mirela_sdk.vision.camera import RealsenseCam, RealSenseConfig
    >>>
    >>> config = RealSenseConfig(
    ...     color_res=(1280, 720),
    ...     depth_res=(1280, 720),
    ...     fps=30,
    ...     align_to_color=True,
    ... )
    >>> cam = RealsenseCam(config)
    >>> cam.start()
    >>> rgb = cam.get_frame()
    >>> depth = cam.get_depth_frame()

    See Also
    --------
    ROSDepthCam : For accessing RealSense via ROS topics.
    """

    def __init__(self, config: RealSenseConfig, node=None) -> None:
        if not REALSENSE_AVAILABLE:
            raise ImportError(
                "pyrealsense2 is required for RealsenseCam. Install with: pip install pyrealsense2"
            )

        super().__init__(name=config.name)
        self._config = config
        self._enable_depth = config.enable_depth

        if config.use_ros_topics:
            warnings.warn(
                "RealsenseCam use_ros_topics is deprecated. Use ROSDepthCam instead:\n"
                "  from mirela_sdk.vision.camera import ROSDepthCam, ROSDepthConfig\n"
                "  config = ROSDepthConfig(\n"
                "      topic='/camera/color/image_raw/compressed',\n"
                "      compressed=True,\n"
                "      depth_topic='/camera/depth/image_rect_raw',\n"
                "      depth_compressed=False,\n"
                "  )\n"
                "  cam = ROSDepthCam(node, config)",
                DeprecationWarning,
                stacklevel=2,
            )
            from mirela_sdk.vision.camera.config import ROSDepthConfig
            from mirela_sdk.vision.camera.drivers.ros_depth_cam import ROSDepthCam

            ros_config = ROSDepthConfig(
                topic=config.color_topic,
                compressed=config.color_compressed,
                depth_topic=config.depth_topic,
                depth_compressed=config.depth_compressed,
                enable_depth=config.enable_depth,
            )
            self._ros_delegate = ROSDepthCam(node, ros_config)
            self._use_ros_delegate = True
        else:
            self._ros_delegate = None
            self._use_ros_delegate = False

        self._pipeline = None
        self._align = None
        self._depth_scale: Optional[float] = None
        self._rgb: Optional[np.ndarray] = None
        self._depth: Optional[np.ndarray] = None

    def start(self) -> None:
        """
        Initialize and start the pyrealsense2 pipeline.

        Raises
        ------
        RuntimeError
            If pyrealsense2 is not installed.
        """
        if self._use_ros_delegate:
            self._ros_delegate.start()
            self._is_running = True
            return

        if rs is None:
            raise RuntimeError(
                "pyrealsense2 is not installed. Please install librealsense and pyrealsense2."
            )

        config = rs.config()
        config.enable_stream(
            rs.stream.color,
            self._config.color_res[0],
            self._config.color_res[1],
            rs.format.bgr8,
            self._config.fps,
        )

        if self._enable_depth:
            config.enable_stream(
                rs.stream.depth,
                self._config.depth_res[0],
                self._config.depth_res[1],
                rs.format.z16,
                self._config.fps,
            )

        self._pipeline = rs.pipeline()
        profile = self._pipeline.start(config)

        if self._enable_depth:
            depth_sensor = profile.get_device().first_depth_sensor()
            self._depth_scale = float(depth_sensor.get_depth_scale())

            if self._config.align_to_color:
                self._align = rs.align(rs.stream.color)
            else:
                self._align = None
        else:
            self._depth_scale = None
            self._align = None

        self._is_running = True

    def _wait_for_frames(self):
        """Wait for and return aligned frameset from pipeline."""
        if not self._pipeline:
            return None
        frames = self._pipeline.wait_for_frames()
        if self._align is not None:
            frames = self._align.process(frames)
        return frames

    def get_frame(self, wait_for_new: bool = True, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Capture color frame from camera.

        Parameters
        ----------
        wait_for_new : bool, optional
            Ignored for SDK mode (always captures fresh frame).
        timeout : float, optional
            Ignored for SDK mode.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if capture failed.
        """
        if self._use_ros_delegate:
            return self._ros_delegate.get_frame(wait_for_new, timeout)

        frames = self._wait_for_frames()
        if frames is None:
            return None
        color_frame = frames.get_color_frame()
        if not color_frame:
            return None
        self._rgb = np.asanyarray(color_frame.get_data())
        return self._rgb

    def get_depth_frame(
        self, wait_for_new: bool = True, timeout: float = 0.1
    ) -> Optional[np.ndarray]:
        """
        Capture depth frame from camera.

        Parameters
        ----------
        wait_for_new : bool, optional
            Ignored for SDK mode (always captures fresh frame).
        timeout : float, optional
            Ignored for SDK mode.

        Returns
        -------
        np.ndarray or None
            Depth image in meters (float32), or None if depth disabled
            or capture failed.
        """
        if not self._enable_depth:
            return None

        if self._use_ros_delegate:
            return self._ros_delegate.get_depth_frame(wait_for_new, timeout)

        frames = self._wait_for_frames()
        if frames is None:
            return None
        depth_frame = frames.get_depth_frame()
        if not depth_frame:
            return None
        depth_image = np.asanyarray(depth_frame.get_data())
        if self._depth_scale is None:
            return None
        self._depth = depth_image.astype(np.float32) * self._depth_scale
        return self._depth

    def get_distance(self, u: int, v: int) -> Optional[float]:
        """
        Get distance at pixel coordinates.

        Parameters
        ----------
        u : int
            Horizontal pixel coordinate (column).
        v : int
            Vertical pixel coordinate (row).

        Returns
        -------
        float or None
            Distance in meters, or None if depth disabled, coordinates
            out of bounds, or no valid depth at that pixel.
        """
        if not self._enable_depth:
            return None

        if self._use_ros_delegate:
            return self._ros_delegate.get_distance(u, v)

        frames = self._wait_for_frames()
        if frames is None:
            return None
        depth_frame = frames.get_depth_frame()
        if not depth_frame:
            return None
        try:
            distance_m = float(depth_frame.get_distance(int(u), int(v)))
        except Exception:
            return None
        return distance_m

    def close(self) -> None:
        """Release camera resources."""
        if self._use_ros_delegate:
            self._ros_delegate.close()
        elif self._pipeline:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
        self._is_running = False
