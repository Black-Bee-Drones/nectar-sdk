import threading
from typing import Optional

import numpy as np
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage as RosCompressedImage
from sensor_msgs.msg import Image as RosImage

from mirela_sdk.vision.camera.abstract import DepthCam
from mirela_sdk.vision.camera.config import (
    QoSDurability,
    QoSReliability,
    ROSDepthConfig,
)
from mirela_sdk.vision.camera.drivers.ros_cam import ROSCam


class ROSDepthCam(DepthCam):
    """
    Depth camera driver for ROS image topics.

    Composes ROSCam for color stream and adds depth subscription with the same
    thread-safe pattern.

    Parameters
    ----------
    node : Node
        ROS2 node for subscription creation.
    config : ROSDepthConfig
        Configuration with color and depth topic settings.

    Examples
    --------
    Raw topics:

    >>> config = ROSDepthConfig(
    ...     topic="/camera/color/image_raw",
    ...     compressed=False,
    ...     depth_topic="/camera/depth/image_rect_raw",
    ...     depth_compressed=False,
    ... )
    >>> cam = ROSDepthCam(node, config)

    Compressed topics:

    >>> config = ROSDepthConfig(
    ...     topic="/camera/color/image_raw/compressed",
    ...     compressed=True,
    ...     depth_topic="/camera/depth/image_rect_raw/compressedDepth",
    ...     depth_compressed=True,
    ... )
    >>> cam = ROSDepthCam(node, config)
    >>> cam.start()
    >>> rgb = cam.get_frame()
    >>> depth = cam.get_depth_frame()
    >>> distance = cam.get_distance(320, 240)

    Notes
    -----
    - Thread-safe: all get_* methods return copies.
    - Depth frames are returned in meters (float32).
    - Topic paths must be explicit (include /compressed or /compressedDepth).
    """

    def __init__(self, node: Node, config: ROSDepthConfig) -> None:
        super().__init__(name=config.name)
        self._node = node
        self._config = config
        self._bridge = CvBridge()

        self._color_cam = ROSCam(node, config)

        self._depth: Optional[np.ndarray] = None
        self._depth_sub = None
        self._depth_lock = threading.Lock()
        self._depth_event = threading.Event()
        self._depth_count = 0
        self._last_depth_count = -1

        self._depth_qos = self._build_qos_profile()

    def _build_qos_profile(self) -> QoSProfile:
        """Build QoS profile from configuration."""
        if self._config.reliability == QoSReliability.RELIABLE:
            reliability = ReliabilityPolicy.RELIABLE
        else:
            reliability = ReliabilityPolicy.BEST_EFFORT

        if self._config.durability == QoSDurability.TRANSIENT_LOCAL:
            durability = DurabilityPolicy.TRANSIENT_LOCAL
        else:
            durability = DurabilityPolicy.VOLATILE

        return QoSProfile(
            reliability=reliability,
            history=HistoryPolicy.KEEP_LAST,
            depth=self._config.history_depth,
            durability=durability,
        )

    def _depth_callback(self, msg) -> None:
        """Subscription callback for depth image messages."""
        try:
            if self._config.depth_compressed:
                depth_raw = self._decode_compressed_depth(msg)
            else:
                depth_raw = self._bridge.imgmsg_to_cv2(
                    msg, desired_encoding=self._config.depth_encoding
                )

            if depth_raw is None:
                return

            if depth_raw.dtype == np.uint16:
                depth_m = depth_raw.astype(np.float32) / 1000.0
            else:
                depth_m = depth_raw.astype(np.float32)

            with self._depth_lock:
                self._depth = depth_m
                self._depth_count += 1
            self._depth_event.set()

        except Exception as e:
            self._node.get_logger().error(f"ROSDepthCam: failed to convert depth image: {e}")

    def _decode_compressed_depth(self, msg) -> Optional[np.ndarray]:
        """
        Decode compressedDepth message (16-bit PNG with RVL header).

        ROS compressedDepth format: 12-byte header + PNG/RVL compressed data.
        """
        import cv2

        data = np.frombuffer(msg.data, dtype=np.uint8)

        if msg.format.endswith("compressedDepth"):
            if len(data) < 12:
                return None
            raw_data = data[12:]
        else:
            raw_data = data

        depth_raw = cv2.imdecode(raw_data, cv2.IMREAD_UNCHANGED)
        return depth_raw

    def start(self) -> None:
        """
        Create subscriptions to color and depth topics.

        Subscribes to color topic via composed ROSCam and depth topic directly.
        """
        self._color_cam.start()

        if self._config.enable_depth:
            if self._config.depth_compressed:
                self._depth_sub = self._node.create_subscription(
                    RosCompressedImage,
                    self._config.depth_topic,
                    self._depth_callback,
                    self._depth_qos,
                )
            else:
                self._depth_sub = self._node.create_subscription(
                    RosImage,
                    self._config.depth_topic,
                    self._depth_callback,
                    self._depth_qos,
                )

            self._node.get_logger().info(
                f"ROSDepthCam: Subscribed to depth topic {self._config.depth_topic}"
            )

        self._is_running = True

    def get_frame(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Return the most recently received color frame.

        Delegates to composed ROSCam for thread-safe color frame access.

        Parameters
        ----------
        wait_for_new : bool, optional
            If True, blocks until a new frame arrives or timeout.
        timeout : float, optional
            Maximum time to wait for new frame (seconds).

        Returns
        -------
        np.ndarray or None
            BGR image (copy), or None if no frame received yet.
        """
        return self._color_cam.get_frame(wait_for_new, timeout)

    def get_depth_frame(
        self, wait_for_new: bool = False, timeout: float = 1.0
    ) -> Optional[np.ndarray]:
        """
        Return the most recently received depth frame.

        Parameters
        ----------
        wait_for_new : bool, optional
            If True, blocks until a new frame arrives or timeout.
        timeout : float, optional
            Maximum time to wait for new frame (seconds).

        Returns
        -------
        np.ndarray or None
            Depth image in meters (float32 copy), or None if depth disabled
            or no frame received yet.
        """
        if not self._config.enable_depth:
            return None

        if wait_for_new:
            with self._depth_lock:
                if self._depth_count > self._last_depth_count and self._depth is not None:
                    self._last_depth_count = self._depth_count
                    return self._depth.copy()

            self._depth_event.clear()
            if not self._depth_event.wait(timeout=timeout):
                return None

        with self._depth_lock:
            if self._depth is None:
                return None

            if wait_for_new and self._depth_count == self._last_depth_count:
                return None

            self._last_depth_count = self._depth_count
            return self._depth.copy()

    def get_distance(self, u: int, v: int, color_shape: Optional[tuple] = None) -> Optional[float]:
        """
        Get distance at pixel coordinates.

        Coordinates are automatically scaled when color and depth frames have
        different resolutions (common with RealSense ROS node).

        Parameters
        ----------
        u : int
            Horizontal pixel coordinate (column) in color frame.
        v : int
            Vertical pixel coordinate (row) in color frame.
        color_shape : tuple, optional
            Shape of color frame (h, w) for coordinate scaling.
            If None, coordinates are used directly without scaling.

        Returns
        -------
        float or None
            Distance in meters, or None if depth disabled, coordinates
            out of bounds, or no valid depth at that pixel.
        """
        if not self._config.enable_depth:
            return None

        with self._depth_lock:
            if self._depth is None:
                return None

            depth_h, depth_w = self._depth.shape[:2]

            if color_shape is not None:
                color_h, color_w = color_shape[:2]
                if color_w > 0 and color_h > 0:
                    u = int(u * depth_w / color_w)
                    v = int(v * depth_h / color_h)

            if not (0 <= v < depth_h and 0 <= u < depth_w):
                return None

            dist = float(self._depth[int(v), int(u)])
            return dist if dist > 0 else None

    @property
    def color_topic(self) -> str:
        """Return the subscribed color topic name."""
        return self._config.topic

    @property
    def depth_topic(self) -> str:
        """Return the subscribed depth topic name."""
        return self._config.depth_topic

    @property
    def is_compressed(self) -> bool:
        """Return whether color topic uses compressed transport."""
        return self._config.compressed

    @property
    def depth_enabled(self) -> bool:
        """Return whether depth is enabled."""
        return self._config.enable_depth

    def close(self) -> None:
        """Destroy subscriptions and release resources."""
        self._color_cam.close()

        if self._depth_sub is not None:
            try:
                self._node.destroy_subscription(self._depth_sub)
            except Exception:
                pass
            self._depth_sub = None

        self._is_running = False
        self._depth_event.set()
