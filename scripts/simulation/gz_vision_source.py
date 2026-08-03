#!/usr/bin/env python3
"""Gazebo ground-truth pose -> canonical VSLAM topics (SITL emulator).

Publishes pose and a finite-differenced twist (same 10-pose window as cuVSLAM's
``PoseCache::GetVelocity``). Launched by ``sitl_gazebo.launch.py`` (ArduPilot
indoor, TFMessage from world Pose_V) and ``px4_sitl.launch.py`` (PX4 indoor,
PoseStamped from model PosePublisher).
"""

from collections import deque

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from tf2_msgs.msg import TFMessage

from nectar.control.localization.frames import rotate_by_quaternion

_POSE_WINDOW = 10


class GzVisionSource(Node):
    """Emulate a VSLAM pose source from Gazebo ground-truth model pose."""

    def __init__(self) -> None:
        super().__init__("gz_vision_source")

        self.declare_parameter("model_name", "iris")
        # Launch files override: ArduPilot uses /world/<name>/dynamic_pose/info
        # (TFMessage); PX4 uses /model/x500_nectar/pose (PoseStamped).
        self.declare_parameter(
            "gz_pose_topic", "/world/nectar_indoor/dynamic_pose/info"
        )
        # "tf" = TFMessage (Pose_V bridge); "pose" = PoseStamped (model Pose bridge)
        self.declare_parameter("input_type", "tf")
        self.declare_parameter(
            "output_topic", "/visual_slam/tracking/vo_pose_covariance"
        )
        self.declare_parameter("odometry_topic", "/visual_slam/tracking/odometry")
        # Fallback index when ros_gz strips child_frame_id from Pose_V->TFMessage.
        self.declare_parameter("model_index", 0)
        self._model_name = (
            self.get_parameter("model_name").get_parameter_value().string_value
        )
        self._model_index = (
            self.get_parameter("model_index").get_parameter_value().integer_value
        )
        self._warned_fallback = False
        gz_topic = (
            self.get_parameter("gz_pose_topic").get_parameter_value().string_value
        )
        out_topic = (
            self.get_parameter("output_topic").get_parameter_value().string_value
        )
        input_type = (
            self.get_parameter("input_type").get_parameter_value().string_value.lower()
        )

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        if input_type == "pose":
            self._sub = self.create_subscription(
                PoseStamped, gz_topic, self._pose_stamped_callback, qos
            )
        else:
            self._sub = self.create_subscription(
                TFMessage, gz_topic, self._tf_callback, qos
            )

        self._pub = self.create_publisher(
            PoseWithCovarianceStamped,
            out_topic,
            qos,
        )

        odom_topic = (
            self.get_parameter("odometry_topic").get_parameter_value().string_value
        )
        self._odom_pub = self.create_publisher(Odometry, odom_topic, qos)
        self._pose_window = deque(maxlen=_POSE_WINDOW)

        # Difference sim time (/clock), not wall clock — Gazebo RTF is often << 1.
        self._sim_time = None
        self.create_subscription(Clock, "/clock", self._on_clock, 10)

        self.get_logger().info(
            f"GzVisionSource: {gz_topic} (type={input_type}, model={self._model_name}) "
            f"-> {out_topic}, {odom_topic}"
        )

    def _pose_stamped_callback(self, msg: PoseStamped) -> None:
        self._emit_pose(msg.pose.position, msg.pose.orientation)

    def _tf_callback(self, msg: TFMessage) -> None:
        tf = self._select_transform(msg)
        if tf is None:
            return
        self._emit_pose(tf.transform.translation, tf.transform.rotation)

    def _emit_pose(self, position, orientation) -> None:
        out = PoseWithCovarianceStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "map"
        out.pose.pose.position.x = position.x
        out.pose.pose.position.y = position.y
        out.pose.pose.position.z = position.z
        out.pose.pose.orientation = orientation

        out.pose.covariance[0] = 0.01
        out.pose.covariance[7] = 0.01
        out.pose.covariance[14] = 0.01
        out.pose.covariance[21] = 0.01
        out.pose.covariance[28] = 0.01
        out.pose.covariance[35] = 0.01

        self._pub.publish(out)
        self._publish_odometry(out)

    def _on_clock(self, msg: Clock) -> None:
        self._sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9

    def _publish_odometry(self, pose_msg: PoseWithCovarianceStamped) -> None:
        if self._sim_time is None:
            stamp = pose_msg.header.stamp
            now = stamp.sec + stamp.nanosec * 1e-9
        else:
            now = self._sim_time
        p = pose_msg.pose.pose.position
        q = pose_msg.pose.pose.orientation
        self._pose_window.append((now, (p.x, p.y, p.z), (q.x, q.y, q.z, q.w)))

        odom = Odometry()
        odom.header = pose_msg.header
        odom.child_frame_id = "base_link"
        odom.pose = pose_msg.pose

        t0, p0, q0 = self._pose_window[0]
        dt = now - t0
        if dt > 1e-6:
            world = ((p.x - p0[0]) / dt, (p.y - p0[1]) / dt, (p.z - p0[2]) / dt)
            # World -> body of oldest sample (PoseCache::GetVelocity).
            qx, qy, qz, qw = q0
            vx, vy, vz = rotate_by_quaternion(world, (-qx, -qy, -qz, qw))
            odom.twist.twist.linear.x = vx
            odom.twist.twist.linear.y = vy
            odom.twist.twist.linear.z = vz

        self._odom_pub.publish(odom)

    def _select_transform(self, msg: TFMessage):
        """Pick the model-root transform; fall back to index if frame ids are empty."""
        for tf in msg.transforms:
            if tf.child_frame_id == self._model_name:
                return tf

        if msg.transforms and not any(tf.child_frame_id for tf in msg.transforms):
            if not self._warned_fallback:
                self.get_logger().warn(
                    "child_frame_id empty (ros_gz bridge stripped names); "
                    f"using index {self._model_index} for model '{self._model_name}'"
                )
                self._warned_fallback = True
            if 0 <= self._model_index < len(msg.transforms):
                return msg.transforms[self._model_index]

        return None


def main() -> None:
    rclpy.init()
    node = GzVisionSource()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
