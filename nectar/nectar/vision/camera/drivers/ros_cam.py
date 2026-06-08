import threading
import uuid
from typing import Optional

import numpy as np
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage as RosCompressedImage
from sensor_msgs.msg import Image as RosImage

from nectar import runtime as nectar_runtime
from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import QoSDurability, QoSReliability, ROSConfig


class ROSCam(AbstractCam):
    """
    Camera driver for ROS image topics.

    Subscribes to sensor_msgs/Image or sensor_msgs/CompressedImage topics.
    When ``node`` is omitted, an internal node is created and registered with
    :mod:`nectar.runtime`; otherwise the provided node is used (this is the
    path taken when wrapped by :class:`ImageHandler`).
    """

    def __init__(self, node: Optional[Node] = None, config: Optional[ROSConfig] = None) -> None:
        if config is None:
            raise ValueError("ROSCam requires a ROSConfig")
        super().__init__(name=config.name)
        self._owns_node = node is None
        if node is None:
            nectar_runtime.ensure_context()
            self._node = Node(
                f"nectar_ros_cam_{uuid.uuid4().hex[:8]}",
                start_parameter_services=False,
            )
            nectar_runtime.add_node(self._node)
        else:
            self._node = node
        self._config = config
        self._bridge = CvBridge()
        self._frame: Optional[np.ndarray] = None
        self._sub = None
        self._frame_event = threading.Event()
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_frame_count = -1

        self._qos = self._build_qos_profile()

    def _build_qos_profile(self) -> QoSProfile:
        """
        Build QoS profile from configuration.

        Returns
        -------
        QoSProfile
            Configured QoS profile for subscription.
        """
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

    def _cb(self, msg) -> None:
        """Subscription callback for image messages."""
        try:
            if self._config.compressed:
                frame = self._bridge.compressed_imgmsg_to_cv2(
                    msg, desired_encoding=self._config.encoding
                )
            else:
                frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding=self._config.encoding)

            with self._lock:
                self._frame = frame
                self._frame_count += 1
            self._frame_event.set()

        except Exception as e:
            self._node.get_logger().error(f"ROSCam: failed to convert image: {e}")

    def start(self) -> None:
        """
        Create subscription to configured topic.

        Subscribes to either sensor_msgs/Image or sensor_msgs/CompressedImage
        based on the compressed configuration option.
        """
        reliability_str = self._config.reliability.value
        self._node.get_logger().info(
            f"ROSCam: Subscribing to {self._config.topic} "
            f"(compressed={self._config.compressed}, qos={reliability_str})"
        )

        if self._config.compressed:
            self._sub = self._node.create_subscription(
                RosCompressedImage, self._config.topic, self._cb, self._qos
            )
        else:
            self._sub = self._node.create_subscription(
                RosImage, self._config.topic, self._cb, self._qos
            )
        self._is_running = True

    def get_frame(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Return the most recently received frame.

        Parameters
        ----------
        wait_for_new : bool, optional
            If True, blocks until a new frame arrives or timeout.
            If False, returns the current frame immediately.
        timeout : float, optional
            Maximum time to wait for new frame (seconds).

        Returns
        -------
        np.ndarray or None
            BGR image (copy), or None if no frame received yet.
        """
        if wait_for_new:
            with self._lock:
                if self._frame_count > self._last_frame_count and self._frame is not None:
                    self._last_frame_count = self._frame_count
                    return self._frame.copy()

            self._frame_event.clear()
            if not self._frame_event.wait(timeout=timeout):
                return None

        with self._lock:
            if self._frame is None:
                return None

            if wait_for_new and self._frame_count == self._last_frame_count:
                return None

            self._last_frame_count = self._frame_count
            return self._frame.copy()

    @property
    def topic(self) -> str:
        """Return the subscribed topic name."""
        return self._config.topic

    @property
    def is_compressed(self) -> bool:
        """Return whether using compressed image transport."""
        return self._config.compressed

    @property
    def qos_reliability(self) -> QoSReliability:
        """Return the QoS reliability setting."""
        return self._config.reliability

    def close(self) -> None:
        """Destroy subscription and release resources."""
        if self._sub is not None:
            try:
                self._node.destroy_subscription(self._sub)
            except Exception:
                pass
            self._sub = None
        self._is_running = False
        self._frame_event.set()
        if self._owns_node:
            nectar_runtime.remove_node(self._node)
            try:
                self._node.destroy_node()
            except Exception:
                pass
            self._owns_node = False
