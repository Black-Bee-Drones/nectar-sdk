"""Direct pymavlink VSLAM pose/speed -> FCU (``VISION_POSITION_ESTIMATE`` / ``VISION_SPEED_ESTIMATE``).

For >= 4 Hz Non-GPS feeds see
https://ardupilot.org/dev/docs/mavlink-nongps-position-estimation.html.

``VisionPoseSubscriber`` updates companion ENU pose only.
``VisionPoseBridge`` / ``VisionSpeedBridge`` also send to the FCU.
"""

import time
from typing import Callable, Optional

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf_transformations import euler_from_quaternion

from nectar.control.localization.frames import (
    body_velocity_to_ned,
    covariance_urt_to_mavlink,
    enu_to_ned,
    euler_enu_to_ned,
    pose_covariance_enu_to_ned,
)
from nectar.control.mavlink.connection import MavlinkConnection
from nectar.control.vehicle.types import LocalPose, Vec3

PoseCallback = Callable[[LocalPose], None]

_POSE_COVARIANCE_ZERO = [0.0] * 21
# ArduPilot ignores VISION_SPEED covariance and uses VISO_VEL_M_NSE.
_COVARIANCE_UNKNOWN = [float("nan")] + [0.0] * 8


def _local_pose_from_msg(pose) -> LocalPose:
    p = pose.position
    q = pose.orientation
    _, _, yaw_enu = euler_from_quaternion([q.x, q.y, q.z, q.w])
    return LocalPose(position=Vec3(p.x, p.y, p.z), yaw=yaw_enu)


class VisionPoseSubscriber:
    """Subscribe to a VSLAM pose topic for companion nav (no FCU send)."""

    def __init__(
        self,
        node: Node,
        topic: str,
        on_pose: PoseCallback,
    ) -> None:
        self._node = node
        self._topic = topic
        self._on_pose = on_pose
        self._sub = None

    def start(self) -> None:
        if self._sub is not None:
            return
        if "pose_cov" in self._topic:
            self._sub = self._node.create_subscription(
                PoseWithCovarianceStamped, self._topic, self._on_cov, qos_profile_sensor_data
            )
        else:
            self._sub = self._node.create_subscription(
                PoseStamped, self._topic, self._on_pose_stamped, qos_profile_sensor_data
            )
        self._node.get_logger().info(f"VisionPoseSubscriber: {self._topic}")

    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None

    def _on_cov(self, msg: PoseWithCovarianceStamped) -> None:
        self._on_pose(_local_pose_from_msg(msg.pose.pose))

    def _on_pose_stamped(self, msg: PoseStamped) -> None:
        self._on_pose(_local_pose_from_msg(msg.pose))


class VisionPoseBridge:
    """Relay a VSLAM pose topic to the FCU as ``VISION_POSITION_ESTIMATE``."""

    def __init__(
        self,
        node: Node,
        connection: MavlinkConnection,
        topic: str,
        on_pose: Optional[PoseCallback] = None,
    ) -> None:
        self._node = node
        self._connection = connection
        self._topic = topic
        self._on_pose = on_pose
        self._sub = None
        self._protocol_checked = False

    def start(self) -> None:
        if self._sub is not None:
            return
        if "pose_cov" in self._topic:
            self._sub = self._node.create_subscription(
                PoseWithCovarianceStamped, self._topic, self._on_cov, qos_profile_sensor_data
            )
        else:
            self._sub = self._node.create_subscription(
                PoseStamped, self._topic, self._on_pose_stamped, qos_profile_sensor_data
            )
        self._node.get_logger().info(f"VisionPoseBridge: relaying {self._topic} -> FCU")

    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None

    def _check_covariance_transmittable(self) -> None:
        """Warn once if the link is MAVLink 1 (covariance is a v2 extension)."""
        if self._protocol_checked:
            return
        self._protocol_checked = True
        if self._connection.master.WIRE_PROTOCOL_VERSION != "2.0":
            self._node.get_logger().warning(
                "FCU link negotiated MAVLink 1: the pose covariance cannot be sent "
                "(MAVLink 2 extension field). ArduPilot will use VISO_POS_M_NSE."
            )

    def _on_cov(self, msg: PoseWithCovarianceStamped) -> None:
        self._send(msg.pose.pose, msg.pose.covariance)

    def _on_pose_stamped(self, msg: PoseStamped) -> None:
        self._send(msg.pose, None)

    def _send(self, pose, covariance) -> None:
        if self._on_pose is not None:
            self._on_pose(_local_pose_from_msg(pose))

        p = pose.position
        q = pose.orientation
        roll_enu, pitch_enu, yaw_enu = euler_from_quaternion([q.x, q.y, q.z, q.w])

        x_ned, y_ned, z_ned = enu_to_ned((p.x, p.y, p.z))
        roll_ned, pitch_ned, yaw_ned = euler_enu_to_ned(roll_enu, pitch_enu, yaw_enu)

        cov_urt = _POSE_COVARIANCE_ZERO
        if covariance is not None:
            cov_urt = covariance_urt_to_mavlink(pose_covariance_enu_to_ned(covariance))
            self._check_covariance_transmittable()

        usec = int(time.monotonic() * 1e6) & 0xFFFFFFFFFFFFFFFF
        with self._connection.send_lock:
            self._connection.master.mav.vision_position_estimate_send(
                usec, x_ned, y_ned, z_ned, roll_ned, pitch_ned, yaw_ned, cov_urt
            )


class VisionSpeedBridge:
    """Relay VSLAM odometry twist to the FCU as ``VISION_SPEED_ESTIMATE`` (NED)."""

    def __init__(
        self,
        node: Node,
        connection: MavlinkConnection,
        topic: str,
    ) -> None:
        self._node = node
        self._connection = connection
        self._topic = topic
        self._sub = None

    def start(self) -> None:
        if self._sub is not None:
            return
        self._sub = self._node.create_subscription(
            Odometry, self._topic, self._on_odometry, qos_profile_sensor_data
        )
        self._node.get_logger().info(f"VisionSpeedBridge: relaying {self._topic} -> FCU")

    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None

    def _on_odometry(self, msg: Odometry) -> None:
        lin = msg.twist.twist.linear
        q = msg.pose.pose.orientation
        vx, vy, vz = body_velocity_to_ned((lin.x, lin.y, lin.z), (q.x, q.y, q.z, q.w))

        usec = int(time.monotonic() * 1e6) & 0xFFFFFFFFFFFFFFFF
        with self._connection.send_lock:
            self._connection.master.mav.vision_speed_estimate_send(
                usec, vx, vy, vz, _COVARIANCE_UNKNOWN
            )
