#!/usr/bin/env python3
"""
Vision Pose Bridge — Gazebo ground-truth pose to MAVROS vision pose.

Subscribes to the Gazebo PosePublisher output (bridged to ROS 2 by
ros_gz_bridge) and republishes as PoseWithCovarianceStamped on
/mavros/vision_pose/pose_cov.

This replaces the real RealSense + Isaac ROS VSLAM pipeline in indoor
simulation.  ArduPilot SITL receives the pose as VISION_POSITION_ESTIMATE
when EKF3 is configured with EK3_SRC1_POSXY=6 (ExternalNav).

Usage (launched automatically by sitl_gazebo.launch.py world:=indoor):
    ros2 run nectar vision_pose_bridge
"""

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from tf2_msgs.msg import TFMessage


class VisionPoseBridge(Node):
    """Bridge Gazebo ground-truth model pose to /mavros/vision_pose/pose_cov."""

    def __init__(self) -> None:
        super().__init__("vision_pose_bridge")

        self.declare_parameter("model_name", "iris")
        self.declare_parameter("gz_pose_topic", "/world/indoor_room/dynamic_pose/info")
        # Index of the model-root pose in dynamic_pose/info (first entry), used
        # when the ros_gz Pose_V->TFMessage bridge strips child_frame_id.
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

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        self._sub = self.create_subscription(
            TFMessage,
            gz_topic,
            self._pose_callback,
            qos,
        )

        self._pub = self.create_publisher(
            PoseWithCovarianceStamped,
            "/mavros/vision_pose/pose_cov",
            10,
        )

        self.get_logger().info(
            f"VisionPoseBridge: {gz_topic} (model={self._model_name})"
            " -> /mavros/vision_pose/pose_cov"
        )

    def _pose_callback(self, msg: TFMessage) -> None:
        tf = self._select_transform(msg)
        if tf is None:
            return

        out = PoseWithCovarianceStamped()
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "map"
        out.pose.pose.position.x = tf.transform.translation.x
        out.pose.pose.position.y = tf.transform.translation.y
        out.pose.pose.position.z = tf.transform.translation.z
        out.pose.pose.orientation = tf.transform.rotation

        # Low covariance — ground-truth pose is "perfect"
        out.pose.covariance[0] = 0.01  # x
        out.pose.covariance[7] = 0.01  # y
        out.pose.covariance[14] = 0.01  # z
        out.pose.covariance[21] = 0.01  # roll
        out.pose.covariance[28] = 0.01  # pitch
        out.pose.covariance[35] = 0.01  # yaw

        self._pub.publish(out)

    def _select_transform(self, msg: TFMessage):
        """Pick the model-root transform from a dynamic_pose/info batch.

        Prefers a transform whose ``child_frame_id`` matches the model name. The
        ros_gz ``Pose_V`` -> ``TFMessage`` bridge can leave all frame ids empty;
        in that case it falls back to the model-root index (the first entry in
        dynamic_pose/info), which is the model's world pose.
        """
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
    node = VisionPoseBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
