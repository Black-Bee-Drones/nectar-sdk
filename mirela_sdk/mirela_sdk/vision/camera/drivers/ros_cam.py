from typing import Optional
import numpy as np
import threading
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from sensor_msgs.msg import Image as RosImage
from sensor_msgs.msg import CompressedImage as RosCompressedImage
from cv_bridge import CvBridge

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.config import ROSConfig


class ROSCam(AbstractCam):
    """
    Camera driver for ROS image topics.

    Subscribes to sensor_msgs/Image or sensor_msgs/CompressedImage topics.
    Uses BEST_EFFORT QoS 

    Parameters
    ----------
    node : Node
        ROS2 node for subscription creation.
    config : ROSConfig
        Configuration with topic name and compression settings.
    """

    def __init__(self, node: Node, config: ROSConfig) -> None:
        super().__init__(name=config.name)
        self._node = node
        self._config = config
        self._bridge = CvBridge()
        self._frame: Optional[np.ndarray] = None
        self._sub = None
        self._frame_event = threading.Event()
        self._lock = threading.Lock()
        self._frame_count = 0
        self._last_frame_count = -1

        self._qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )

    def _cb(self, msg) -> None:
        """Subscription callback for image messages."""
        try:
            if self._config.compressed:
                frame = self._bridge.compressed_imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )
            else:
                frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

            with self._lock:
                self._frame = frame
                self._frame_count += 1
            self._frame_event.set()

        except Exception as e:
            self._node.get_logger().error(f"ROSCam: failed to convert image: {e}")

    def start(self) -> None:
        """
        Create subscription to configured topic.
        """
        self._node.get_logger().info(
            f"ROSCam: Subscribing to {self._config.topic} "
            f"(compressed={self._config.compressed})"
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

    def get_frame(
        self, wait_for_new: bool = False, timeout: float = 1.0
    ) -> Optional[np.ndarray]:
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
            BGR image, or None if no frame received yet.
        """
        if wait_for_new:
            self._frame_event.clear()
            if not self._frame_event.wait(timeout=timeout):
                with self._lock:
                    return self._frame.copy() if self._frame is not None else None

        with self._lock:
            if self._frame is None:
                return None

            current_count = self._frame_count
            if wait_for_new and current_count == self._last_frame_count:
                return None

            self._last_frame_count = current_count
            return self._frame.copy()

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