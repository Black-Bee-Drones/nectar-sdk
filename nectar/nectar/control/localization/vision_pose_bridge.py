"""MAVROS-backend vision-pose relay.

Forwards a VSLAM pose topic onto
``/mavros/vision_pose`` so the FCU's EKF consumes it as an external
position source
"""

from typing import Optional

from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data


class MavrosVisionRelay:
    """Relay a VSLAM covariance-pose topic to MAVROS vision pose.

    Parameters
    ----------
    node : Node
        ROS node owning the pub/sub.
    input_topic : str
        VSLAM ``PoseWithCovarianceStamped`` topic.
    output_topic : str
        MAVROS vision-pose topic. Default ``/mavros/vision_pose/pose_cov``.
    frame_id : str, optional
        Override the message ``frame_id`` when non-empty.
    """

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str = "/mavros/vision_pose/pose_cov",
        frame_id: str = "",
    ) -> None:
        self._node = node
        self._input_topic = input_topic
        self._output_topic = output_topic
        self._frame_id = frame_id
        self._sub = None
        self._pub: Optional[object] = None

    def start(self) -> None:
        """Create the publisher and subscription."""
        if self._sub is not None:
            return
        self._pub = self._node.create_publisher(
            PoseWithCovarianceStamped, self._output_topic, qos_profile_sensor_data
        )
        self._sub = self._node.create_subscription(
            PoseWithCovarianceStamped,
            self._input_topic,
            self._relay,
            qos_profile_sensor_data,
        )
        self._node.get_logger().info(
            f"MavrosVisionRelay: {self._input_topic} -> {self._output_topic}"
        )

    def stop(self) -> None:
        """Tear down the pub/sub."""
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None
        if self._pub is not None:
            self._node.destroy_publisher(self._pub)
            self._pub = None

    def _relay(self, msg: PoseWithCovarianceStamped) -> None:
        if self._frame_id:
            msg.header.frame_id = self._frame_id
        self._pub.publish(msg)
