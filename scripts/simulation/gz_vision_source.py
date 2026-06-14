#!/usr/bin/env python3
"""Gazebo ground-truth pose -> canonical VSLAM pose topic (SITL VSLAM emulator).

Usage (launched automatically by sitl_gazebo.launch.py world:=indoor):
    ros2 run nectar gz_vision_source.py
"""

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from tf2_msgs.msg import TFMessage


class GzVisionSource(Node):
    """Emulate a VSLAM pose source from Gazebo ground-truth model pose."""

    def __init__(self) -> None:
        super().__init__("gz_vision_source")

        self.declare_parameter("model_name", "iris")
        self.declare_parameter("gz_pose_topic", "/world/indoor_room/dynamic_pose/info")
        self.declare_parameter(
            "output_topic", "/visual_slam/tracking/vo_pose_covariance"
        )
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
        out_topic = (
            self.get_parameter("output_topic").get_parameter_value().string_value
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
            out_topic,
            qos,
        )

        self.get_logger().info(
            f"GzVisionSource: {gz_topic} (model={self._model_name}) -> {out_topic}"
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
