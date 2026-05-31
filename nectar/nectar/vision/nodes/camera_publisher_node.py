#!/usr/bin/env python3
import time
from typing import Any

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from nectar.vision.camera.config import CameraConfig
from nectar.vision.camera.config_builder import ConfigBuilder
from nectar.vision.camera.factory import CameraFactory
from nectar.vision.camera.handler import ImageHandler


class CameraPublisherNode(Node):
    """
    Generic camera image publisher node.

    Captures frames from any supported camera driver via CameraFactory and
    publishes them to ROS image topics.

    Parameters (ROS) — General
    --------------------------
    camera_source : str
        Camera source identifier (default: 'webcam'). Accepted values:
        'webcam', 'opencv', 'c920', 'imx219', 'realsense', 'oakd',
        'ros', 'ros_depth', 'file'.
    use_compression : bool
        Publish compressed JPEG images (default: True).
    jpeg_quality : int
        JPEG compression quality 0-100 (default: 80).
    log_fps_interval : float
        Interval in seconds to log FPS statistics (default: 5.0, 0 to disable).
    poll_interval : float
        Override frame-poll period in seconds (default: -1 = auto).
    frame_timeout : float
        Override new-frame wait timeout in seconds (default: -1 = auto).

    Parameters (ROS) — OpenCV / Webcam
    -----------------------------------
    device_index : int
        Webcam device index (default: 0).
    fps : int
        Target frames per second (default: 30).
    width : int
        Frame width in pixels (default: 640).
    height : int
        Frame height in pixels (default: 480).
    fourcc : str
        FourCC codec code (default: 'MJPG').
    buffer_size : int
        Camera buffer size 1-10 (default: 2).
    threaded : bool
        Use background thread for capture (default: True).

    Parameters (ROS) — C920
    -----------------------
    profile : int
        C920 resolution profile 0-2 (default: 1).
    fallback_device_index : int
        Fallback V4L2 device index (default: 0).

    Parameters (ROS) — IMX219
    -------------------------
    sensor_id : int
        CSI sensor id (default: 0).
    width : int
        Frame width in pixels (default: 1920)
    height : int
        Frame height in pixels (default: 1080)
    fps : int
        Target frames per second (default: 30).
    flip : int
        Image flip (default: 0).
    brightness : float
        Optional brightness setting (default: None, auto).

    Parameters (ROS) — RealSense
    ----------------------------
    color_width : int
        Color stream width (default: 640).
    color_height : int
        Color stream height (default: 480).
    depth_width : int
        Depth stream width (default: 640).
    depth_height : int
        Depth stream height (default: 480).
    fps : int
        Target frames per second (default: 30).
    align_to_color : bool
        Align depth to color frame (default: True).
    enable_depth : bool
        Enable depth stream (default: True).
    use_ros_topics : bool
        Subscribe to existing ROS topics instead of opening device (default: False).
    color_topic : str
        Color image ROS topic (default: '/camera/color/image_raw').
    depth_topic : str
        Depth image ROS topic (default: '/camera/depth/image_rect_raw').
    color_compressed : bool
        Color topic is compressed (default: True).
    depth_compressed : bool
        Depth topic is compressed (default: False).

    Parameters (ROS) — OAK-D
    -------------------------
    cam_num : int
        OAK-D camera selector 1-3 (default: 1).
        1: RGB, 2: left mono, 3: right mono.
    enable_depth : bool
        Enable depth stream (default: False).

    Parameters (ROS) — ROS camera
    -----------------------------
    topic : str
        Image topic to subscribe to (default: '/image_raw').
    compressed : bool
        Topic carries compressed images (default: False).
    reliability : str
        QoS reliability: 'best_effort' or 'reliable' (default: 'best_effort').
    durability : str
        QoS durability: 'volatile' or 'transient_local' (default: 'volatile').
    history_depth : int
        QoS history depth (default: 1).
    encoding : str
        Image encoding (default: 'bgr8').

    Parameters (ROS) — ROS Depth camera
    -----------------------------
    topic : str
        Image topic to subscribe to (default: '/image_raw').
    compressed : bool
        Topic carries compressed images (default: False).
    reliability : str
        QoS reliability: 'best_effort' or 'reliable' (default: 'best_effort').
    durability : str
        QoS durability: 'volatile' or 'transient_local' (default: 'volatile').
    history_depth : int
        QoS history depth (default: 1).
    encoding : str
        Image encoding (default: 'bgr8').
    depth_topic : str
        Depth image ROS topic (default: '/camera/depth/image_rect_raw').
    depth_compressed : bool
        Depth topic is compressed (default: False).
    depth_encoding : str
        Depth image encoding (default: 'passthrough').
    enable_depth : bool
        Enable depth stream (default: True).

    Parameters (ROS) — File
    -----------------------
    file_path : str
        Path to image file (default: '').

    Publishes
    ---------
    image_raw : Image
        Raw BGR image (if use_compression=False).
    """

    def __init__(self):
        super().__init__("camera_publisher")

        # General parameters
        self.declare_parameter("camera_source", "webcam")
        self.declare_parameter("use_compression", True)
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("log_fps_interval", 5.0)
        self.declare_parameter("poll_interval", -1.0)
        self.declare_parameter("frame_timeout", -1.0)

        # OpenCV / Webcam parameters
        self.declare_parameter("device_index", 0)
        self.declare_parameter("fps", 30)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fourcc", "MJPG")
        self.declare_parameter("autofocus", None)
        self.declare_parameter("focus", None)
        self.declare_parameter("buffer_size", 2)
        self.declare_parameter("threaded", True)

        # C920 parameters
        self.declare_parameter("profile", 1)
        self.declare_parameter("fallback_device_index", 0)

        # IMX219 parameters
        self.declare_parameter("sensor_id", 0)
        self.declare_parameter("flip", 0)

        # RealSense parameters
        self.declare_parameter("color_width", 640)
        self.declare_parameter("color_height", 480)
        self.declare_parameter("depth_width", 640)
        self.declare_parameter("depth_height", 480)
        self.declare_parameter("align_to_color", True)
        self.declare_parameter("enable_depth", True)
        self.declare_parameter("use_ros_topics", False)
        self.declare_parameter("color_topic", "/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/depth/image_rect_raw")
        self.declare_parameter("color_compressed", True)
        self.declare_parameter("depth_compressed", False)

        # OAK-D parameters
        self.declare_parameter("cam_num", 1)

        # ROS camera parameters
        self.declare_parameter("topic", "/image_raw")
        self.declare_parameter("compressed", False)
        self.declare_parameter("reliability", "best_effort")
        self.declare_parameter("durability", "volatile")
        self.declare_parameter("history_depth", 1)
        self.declare_parameter("encoding", "bgr8")
        self.declare_parameter("depth_encoding", "passthrough")

        # File parameters
        self.declare_parameter("file_path", "")

        # Read general values
        self.camera_source: str = self.get_parameter("camera_source").value
        self.use_compression: bool = self.get_parameter("use_compression").value
        self.jpeg_quality: int = self.get_parameter("jpeg_quality").value
        self.log_fps_interval: float = self.get_parameter("log_fps_interval").value
        self._poll_interval_override: float = self.get_parameter("poll_interval").value
        self._frame_timeout_override: float = self.get_parameter("frame_timeout").value

        self._is_shutdown = False

        # Publisher
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )

        if self.use_compression:
            self.publisher = self.create_publisher(
                CompressedImage, "image_raw/compressed", qos_profile
            )
        else:
            self.publisher = self.create_publisher(Image, "image_raw", qos_profile)

        self.bridge = CvBridge()
        self.jpeg_params = (cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality)

        # FPS tracking
        self._frame_count = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0

        # Build config & camera
        config = self._build_config()
        camera = CameraFactory.from_source(self.camera_source, config=config)
        camera.start()

        self._log_camera_info(camera)

        # Compute poll / timeout defaults
        poll_interval = self._resolve_poll_interval(camera)
        frame_timeout = self._resolve_frame_timeout(camera)

        self.image_handler = ImageHandler(
            image_source=self.camera_source,
            image_processing_callback=self._publish_frame,
            config=config,
            camera=camera,
            poll_interval=poll_interval,
            frame_timeout=frame_timeout,
        )

        self.image_handler.run()

        if self.log_fps_interval > 0:
            self.fps_timer = self.create_timer(self.log_fps_interval, self._log_fps_stats)

        self.get_logger().info(
            f"Camera publisher started — source: {self.camera_source}, "
            f"compression: {self.use_compression}"
        )

    def _build_config(self) -> CameraConfig:
        """Build the camera-specific config from ROS parameters."""
        if not ConfigBuilder.is_registered(self.camera_source):
            self.get_logger().info(
                f"Source '{self.camera_source}' not a known key — "
                "passing directly to CameraFactory for auto-detection."
            )

        return ConfigBuilder.build(self.camera_source, self)

    def _resolve_poll_interval(self, camera: Any) -> float:
        """Return poll interval, using override or a sensible default."""
        if self._poll_interval_override > 0:
            return self._poll_interval_override

        is_threaded = getattr(camera, "is_threaded", False)
        if is_threaded:
            return 0.001

        fps = self._get_effective_fps(camera)
        return 1.0 / max(fps, 1)

    def _resolve_frame_timeout(self, camera: Any) -> float:
        """Return frame timeout, using override or a sensible default."""
        if self._frame_timeout_override > 0:
            return self._frame_timeout_override

        fps = self._get_effective_fps(camera)
        return 2.0 / max(fps, 1)

    @staticmethod
    def _get_effective_fps(camera: Any) -> float:
        """Best-effort extraction of effective FPS from camera."""
        actual = getattr(camera, "actual_settings", None)
        if actual and "fps" in actual:
            return float(actual["fps"])

        cfg = getattr(camera, "_config", None)
        if cfg:
            fps = getattr(cfg, "fps", None)
            if fps is not None:
                return float(fps)
        return 30.0

    def _log_camera_info(self, camera: Any) -> None:
        """Log human-readable camera information after start."""
        actual = getattr(camera, "actual_settings", None)
        if actual:
            parts = [f"{k}={v}" for k, v in actual.items()]
            self.get_logger().info(f"Camera actual settings: {', '.join(parts)}")

            requested_fps = self.get_parameter("fps").value
            actual_fps = actual.get("fps")
            if actual_fps is not None and actual_fps < requested_fps:
                self.get_logger().warn(
                    f"Camera FPS ({actual_fps:.1f}) is lower than requested "
                    f"({requested_fps}). This is a hardware/driver limitation."
                )
        else:
            self.get_logger().info(f"Camera '{self.camera_source}' started successfully.")

    def _publish_frame(self, frame) -> None:
        """
        Process and publish a single frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR image frame from camera.
        """
        if frame is None:
            return

        timestamp = self.get_clock().now().to_msg()

        if self.use_compression:
            _, compressed = cv2.imencode(".jpg", frame, self.jpeg_params)
            msg = CompressedImage()
            msg.header.stamp = timestamp
            msg.header.frame_id = "camera"
            msg.format = "jpeg"
            msg.data = compressed.tobytes()
        else:
            msg = self.bridge.cv2_to_imgmsg(frame, "bgr8")
            msg.header.stamp = timestamp
            msg.header.frame_id = "camera"

        self.publisher.publish(msg)
        self._frame_count += 1

    def _log_fps_stats(self) -> None:
        """Log FPS statistics periodically."""
        elapsed = time.time() - self._fps_start_time
        if elapsed > 0:
            self._current_fps = self._frame_count / elapsed
            self.get_logger().info(
                f"FPS: {self._current_fps:.1f} "
                f"(frames: {self._frame_count}, elapsed: {elapsed:.1f}s)"
            )
        self._frame_count = 0
        self._fps_start_time = time.time()

    def cleanup(self) -> None:
        """Release camera resources."""
        if self._is_shutdown:
            return
        self._is_shutdown = True
        self.image_handler.cleanup()
        self.get_logger().info("Camera publisher stopped")


def main(args=None) -> None:
    """Entry point for camera publisher node."""
    import nectar

    rclpy.init(args=args)
    nectar.use_executor(rclpy.get_global_executor())

    node = CameraPublisherNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
