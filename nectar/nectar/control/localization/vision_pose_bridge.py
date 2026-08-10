"""MAVROS-backend vision-pose and vision-speed relays."""

from typing import Optional

from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, qos_profile_sensor_data

from nectar.control.localization.frames import rotate_by_quaternion

# MAVROS plugins subscribe with depth-10 RELIABLE; BEST_EFFORT is incompatible.
_MAVROS_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)


class _MavrosRelayBase:
    """Shared pub/sub lifecycle for MAVROS vision relays."""

    _label: str = "MavrosRelay"

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str,
        frame_id: str = "",
    ) -> None:
        self._node = node
        self._input_topic = input_topic
        self._output_topic = output_topic
        self._frame_id = frame_id
        self._sub = None
        self._pub: Optional[object] = None

    def _create_pub_sub(self) -> None:
        raise NotImplementedError

    def start(self) -> None:
        if self._sub is not None:
            return
        self._create_pub_sub()
        self._node.get_logger().info(f"{self._label}: {self._input_topic} -> {self._output_topic}")

    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None
        if self._pub is not None:
            self._node.destroy_publisher(self._pub)
            self._pub = None


class MavrosVisionRelay(_MavrosRelayBase):
    """Republish VSLAM ``PoseWithCovarianceStamped`` onto ``/mavros/vision_pose``."""

    _label = "MavrosVisionRelay"

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str = "/mavros/vision_pose/pose_cov",
        frame_id: str = "",
    ) -> None:
        super().__init__(node, input_topic, output_topic, frame_id)

    def _create_pub_sub(self) -> None:
        self._pub = self._node.create_publisher(
            PoseWithCovarianceStamped, self._output_topic, _MAVROS_QOS
        )
        self._sub = self._node.create_subscription(
            PoseWithCovarianceStamped,
            self._input_topic,
            self._relay,
            qos_profile_sensor_data,
        )

    def _relay(self, msg: PoseWithCovarianceStamped) -> None:
        if self._frame_id:
            msg.header.frame_id = self._frame_id
        self._pub.publish(msg)


class MavrosVisionSpeedRelay(_MavrosRelayBase):
    """Rotate body twist to ENU and publish ``TwistStamped`` for MAVROS vision_speed."""

    _label = "MavrosVisionSpeedRelay"

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str = "/mavros/vision_speed/speed_twist",
        frame_id: str = "",
    ) -> None:
        super().__init__(node, input_topic, output_topic, frame_id)

    def _create_pub_sub(self) -> None:
        self._pub = self._node.create_publisher(TwistStamped, self._output_topic, _MAVROS_QOS)
        self._sub = self._node.create_subscription(
            Odometry, self._input_topic, self._relay, qos_profile_sensor_data
        )

    def _relay(self, msg: Odometry) -> None:
        lin = msg.twist.twist.linear
        q = msg.pose.pose.orientation
        vx, vy, vz = rotate_by_quaternion((lin.x, lin.y, lin.z), (q.x, q.y, q.z, q.w))

        out = TwistStamped()
        out.header = msg.header
        if self._frame_id:
            out.header.frame_id = self._frame_id
        out.twist.linear.x = vx
        out.twist.linear.y = vy
        out.twist.linear.z = vz
        self._pub.publish(out)
