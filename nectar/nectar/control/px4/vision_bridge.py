"""Companion VSLAM pose -> PX4 native uXRCE-DDS external-navigation feed.

DDS-native counterpart of :class:`nectar.control.mavlink.VisionPoseBridge`:
instead of ``VISION_POSITION_ESTIMATE`` it publishes ``px4_msgs/VehicleOdometry``
on ``/fmu/in/vehicle_visual_odometry``, which the Micro XRCE-DDS Agent forwards
to PX4's EKF2. Requires ``px4_msgs`` and a running ``MicroXRCEAgent``.
"""

import math

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data
from tf_transformations import euler_from_quaternion, quaternion_from_euler

try:
    from px4_msgs.msg import VehicleOdometry

    _PX4_MSGS_AVAILABLE = True
except ImportError:  # px4_msgs not built into the workspace
    _PX4_MSGS_AVAILABLE = False

_NAN = float("nan")


class Px4VisionOdometryBridge:
    """Relay a ROS VSLAM pose topic to PX4 as ``VehicleOdometry``.

    Parameters
    ----------
    node : Node
        ROS node owning the pub/sub.
    input_topic : str
        VSLAM pose topic (``PoseStamped`` or ``PoseWithCovarianceStamped``;
        a ``"pose_cov"`` substring selects the covariance type).
    output_topic : str
        PX4 subscribed topic. Default ``/fmu/in/vehicle_visual_odometry``.
    px4_namespace : str
        Prefix matching the uXRCE-DDS client namespace (e.g. ``/uav_1``).
    """

    def __init__(
        self,
        node: Node,
        input_topic: str,
        output_topic: str = "/fmu/in/vehicle_visual_odometry",
        px4_namespace: str = "",
    ) -> None:
        self._node = node
        self._input_topic = input_topic
        self._output_topic = f"{px4_namespace}{output_topic}"
        self._sub = None
        self._pub = None

    def start(self) -> None:
        """Create the publisher and subscription."""
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
        self._node.get_logger().info(
            f"Px4VisionOdometryBridge: {self._input_topic} -> {self._output_topic}"
        )

    def stop(self) -> None:
        """Tear down the pub/sub."""
        if self._sub is not None:
            self._node.destroy_subscription(self._sub)
            self._sub = None
        if self._pub is not None:
            self._node.destroy_publisher(self._pub)
            self._pub = None

    def _on_cov(self, msg: PoseWithCovarianceStamped) -> None:
        c = msg.pose.covariance  # row-major 6x6 (x, y, z, roll, pitch, yaw)
        self._publish(
            msg.pose.pose,
            position_var=(c[7], c[0], c[14]),  # NED swaps x/y
            orientation_var=(c[21], c[28], c[35]),
        )

    def _on_pose(self, msg: PoseStamped) -> None:
        self._publish(msg.pose, position_var=None, orientation_var=None)

    def _publish(self, pose, position_var, orientation_var) -> None:
        p = pose.position
        q = pose.orientation
        roll, pitch, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
        # ENU/FLU -> NED/FRD (identical to control/mavlink/vision_bridge.py).
        qx, qy, qz, qw = quaternion_from_euler(roll, -pitch, (math.pi / 2.0) - yaw)

        odom = VehicleOdometry()
        usec = self._node.get_clock().now().nanoseconds // 1000  # XRCE-DDS syncs the offset
        odom.timestamp = usec
        odom.timestamp_sample = usec
        odom.pose_frame = VehicleOdometry.POSE_FRAME_NED
        odom.position = [float(p.y), float(p.x), float(-p.z)]
        odom.q = [float(qw), float(qx), float(qy), float(qz)]
        odom.velocity_frame = VehicleOdometry.VELOCITY_FRAME_UNKNOWN
        odom.velocity = [_NAN, _NAN, _NAN]
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
        odom.reset_counter = 0
        odom.quality = 0
        self._pub.publish(odom)
