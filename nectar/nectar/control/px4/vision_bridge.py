"""VSLAM pose -> PX4 ``VehicleOdometry`` on ``/fmu/in/vehicle_visual_odometry``."""

import time
from typing import Optional, Tuple

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from tf_transformations import euler_from_quaternion, quaternion_from_euler

from nectar.control.localization.frames import (
    body_velocity_to_ned,
    enu_to_ned,
    euler_enu_to_ned,
    pose_variance_diagonal_enu_to_ned,
)

try:
    from px4_msgs.msg import VehicleOdometry

    _PX4_MSGS_AVAILABLE = True
except ImportError:  # px4_msgs not built into the workspace
    _PX4_MSGS_AVAILABLE = False

_NAN = float("nan")


class Px4VisionOdometryBridge:
    """Relay a VSLAM pose (and optional twist) to PX4 as ``VehicleOdometry``."""

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str = "/fmu/in/vehicle_visual_odometry",
        px4_namespace: str = "",
        speed_topic: str = "",
        speed_timeout_s: float = 0.5,
    ) -> None:
        self._node = node
        self._input_topic = input_topic
        self._output_topic = f"{px4_namespace}{output_topic}"
        self._speed_topic = speed_topic
        self._speed_timeout_s = speed_timeout_s
        self._sub = None
        self._pub = None
        self._speed_sub = None
        # (vx, vy, vz, monotonic_stamp), replaced atomically by the twist callback.
        self._velocity_ned: Optional[Tuple[float, float, float, float]] = None

    def start(self) -> None:
        if not _PX4_MSGS_AVAILABLE:
            raise RuntimeError(
                "px4_msgs is not available. Clone PX4/px4_msgs (version-matched to your "
                "PX4 firmware) into the workspace and build it. See "
                "nectar/nectar/control/px4/README.md."
            )
        if self._sub is not None:
            return
        # PX4 subscribes to /fmu/in/* with BEST_EFFORT/KEEP_LAST; match it.
        pub_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self._pub = self._node.create_publisher(VehicleOdometry, self._output_topic, pub_qos)
        if "pose_cov" in self._input_topic:
            self._sub = self._node.create_subscription(
                PoseWithCovarianceStamped, self._input_topic, self._on_cov, qos_profile_sensor_data
            )
        else:
            self._sub = self._node.create_subscription(
                PoseStamped, self._input_topic, self._on_pose, qos_profile_sensor_data
            )
        if self._speed_topic:
            self._speed_sub = self._node.create_subscription(
                Odometry, self._speed_topic, self._on_odometry, qos_profile_sensor_data
            )
        self._node.get_logger().info(
            f"Px4VisionOdometryBridge: {self._input_topic} -> {self._output_topic}"
            + (f" (+ velocity from {self._speed_topic})" if self._speed_topic else "")
        )

    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None
        if self._speed_sub is not None:
            self._node.destroy_subscription(self._speed_sub)
            self._speed_sub = None
        if self._pub is not None:
            self._node.destroy_publisher(self._pub)
            self._pub = None

    def _on_odometry(self, msg: Odometry) -> None:
        lin = msg.twist.twist.linear
        q = msg.pose.pose.orientation
        vx, vy, vz = body_velocity_to_ned((lin.x, lin.y, lin.z), (q.x, q.y, q.z, q.w))
        self._velocity_ned = (vx, vy, vz, time.monotonic())

    def _fresh_velocity(self) -> Optional[Tuple[float, float, float]]:
        sample = self._velocity_ned
        if sample is None:
            return None
        vx, vy, vz, stamp = sample
        if time.monotonic() - stamp > self._speed_timeout_s:
            return None
        return (vx, vy, vz)

    def _on_cov(self, msg: PoseWithCovarianceStamped) -> None:
        position_var, orientation_var = pose_variance_diagonal_enu_to_ned(msg.pose.covariance)
        self._publish(msg.pose.pose, position_var=position_var, orientation_var=orientation_var)

    def _on_pose(self, msg: PoseStamped) -> None:
        self._publish(msg.pose, position_var=None, orientation_var=None)

    def _publish(self, pose, position_var, orientation_var) -> None:
        p = pose.position
        q = pose.orientation
        roll, pitch, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
        qx, qy, qz, qw = quaternion_from_euler(*euler_enu_to_ned(roll, pitch, yaw))
        x_ned, y_ned, z_ned = enu_to_ned((p.x, p.y, p.z))

        odom = VehicleOdometry()
        usec = self._node.get_clock().now().nanoseconds // 1000  # XRCE-DDS syncs the offset
        odom.timestamp = usec
        odom.timestamp_sample = usec
        odom.pose_frame = VehicleOdometry.POSE_FRAME_NED
        odom.position = [float(x_ned), float(y_ned), float(z_ned)]
        odom.q = [float(qw), float(qx), float(qy), float(qz)]
        velocity = self._fresh_velocity()
        if velocity is None:
            odom.velocity_frame = VehicleOdometry.VELOCITY_FRAME_UNKNOWN
            odom.velocity = [_NAN, _NAN, _NAN]
        else:
            odom.velocity_frame = VehicleOdometry.VELOCITY_FRAME_NED
            odom.velocity = [float(v) for v in velocity]
        odom.angular_velocity = [_NAN, _NAN, _NAN]
        odom.position_variance = (
            [float(v) for v in position_var] if position_var is not None else [_NAN, _NAN, _NAN]
        )
        odom.orientation_variance = (
            [float(v) for v in orientation_var]
            if orientation_var is not None
            else [_NAN, _NAN, _NAN]
        )
        odom.velocity_variance = [_NAN, _NAN, _NAN]
        # quality / reset_counter intentionally 0 until cuVSLAM exposes a mapped
        # tracking-quality signal; EKF2_EV_QMIN defaults to 0 so fusion still runs.
        odom.reset_counter = 0
        odom.quality = 0
        self._pub.publish(odom)
