"""Companion VSLAM pose -> FCU external-navigation feed.

Indoor, the FCU's EKF3 needs an external position source. With MAVROS this is
provided by ``vision_to_mavros`` relaying the VSLAM pose onto
``/mavros/vision_pose/pose``. :class:`MavlinkDrone` has no MAVROS, so
:class:`VisionPoseBridge` plays that role directly: it subscribes to the VSLAM
pose topic and forwards each sample to the FCU as ``VISION_POSITION_ESTIMATE``
(message id 102), sharing the drone's :class:`MavlinkConnection`.

ArduPilot Non-GPS Position Estimation expects this feed at >= 4 Hz; VSLAM
typically runs much faster. See
https://ardupilot.org/dev/docs/mavlink-nongps-position-estimation.html.
"""

import math
import time
from typing import Callable, Optional

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf_transformations import euler_from_quaternion

from nectar.control.ardupilot.types import LocalPose, Vec3
from nectar.control.mavlink.connection import MavlinkConnection

PoseCallback = Callable[[LocalPose], None]


class VisionPoseBridge:
    """Relay a ROS VSLAM pose topic to the FCU as ``VISION_POSITION_ESTIMATE``.

    Parameters
    ----------
    node : Node
        ROS node owning the subscription (the drone's node).
    connection : MavlinkConnection
        Shared FCU endpoint; sends serialize through its ``send_lock``.
    topic : str
        VSLAM pose topic (``PoseStamped`` or ``PoseWithCovarianceStamped``;
        a ``"pose_cov"`` substring selects the covariance type).
    on_pose : callable, optional
        Invoked with the ENU :class:`LocalPose` for every sample (used by the
        transport to expose ``vision_pose`` for companion-side PID navigation).
    """

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

    def start(self) -> None:
        """Subscribe to the VSLAM pose topic."""
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
        """Destroy the subscription."""
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None

    def _on_cov(self, msg: PoseWithCovarianceStamped) -> None:
        ps = PoseStamped()
        ps.header = msg.header
        ps.pose = msg.pose.pose
        self._on_pose_stamped(ps)

    def _on_pose_stamped(self, msg: PoseStamped) -> None:
        p = msg.pose.position
        q = msg.pose.orientation
        roll_enu, pitch_enu, yaw_enu = euler_from_quaternion([q.x, q.y, q.z, q.w])

        if self._on_pose is not None:
            self._on_pose(LocalPose(position=Vec3(p.x, p.y, p.z), yaw=yaw_enu))

        # ENU/FLU -> NED/FRD for the FCU.
        x_ned, y_ned, z_ned = p.y, p.x, -p.z
        roll_ned = roll_enu
        pitch_ned = -pitch_enu
        yaw_ned = (math.pi / 2.0) - yaw_enu

        usec = int(time.monotonic() * 1e6) & 0xFFFFFFFFFFFFFFFF
        with self._connection.send_lock:
            self._connection.master.mav.vision_position_estimate_send(
                usec, x_ned, y_ned, z_ned, roll_ned, pitch_ned, yaw_ned
            )
