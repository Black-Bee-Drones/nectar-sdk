from typing import Optional
import numpy as np

from rclpy.node import Node
from sensor_msgs.msg import Image as RosImage
from sensor_msgs.msg import CompressedImage as RosCompressedImage
from cv_bridge import CvBridge

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.config import ROSConfig


class ROSCam(AbstractCam):
    """
    Camera driver for ROS image topics.

    Subscribes to sensor_msgs/Image or sensor_msgs/CompressedImage topics.

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

    def _cb(self, msg) -> None:
        """Subscription callback for image messages."""
        try:
            if self._config.compressed:
                self._frame = self._bridge.compressed_imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )
            else:
                self._frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self._node.get_logger().error(f"ROSCam: failed to convert image: {e}")

    def start(self) -> None:
        """
        Create subscription to configured topic.
        """
        if self._config.compressed:
            self._sub = self._node.create_subscription(
                RosCompressedImage, self._config.topic, self._cb, 10
            )
        else:
            self._sub = self._node.create_subscription(
                RosImage, self._config.topic, self._cb, 10
            )
        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Return the most recently received frame.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if no frame received yet.
        """
        return self._frame

    def close(self) -> None:
        """Destroy subscription and release resources."""
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None
        self._is_running = False
