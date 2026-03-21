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
        self.declare_parameter("fallback_transform_index", 0)
        self._model_name = (
            self.get_parameter("model_name").get_parameter_value().string_value
        )
        self._model_prefix = f"{self._model_name}::"
        self._fallback_index = (
            self.get_parameter("fallback_transform_index")
            .get_parameter_value()
            .integer_value
        )
        gz_topic = (
            self.get_parameter("gz_pose_topic").get_parameter_value().string_value
        )
        self._miss_count = 0
        self._using_fallback = False

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
        # dynamic_pose/info contains transforms for ALL models.
        # Find the one matching our target model.
        tf_match = None
        for tf in msg.transforms:
            child = tf.child_frame_id
            if child == self._model_name or child.startswith(self._model_prefix):
                tf_match = tf
                break
        if tf_match is None:
            if msg.transforms and all(not t.child_frame_id for t in msg.transforms):
                idx = max(0, min(int(self._fallback_index), len(msg.transforms) - 1))
                tf_match = msg.transforms[idx]
                if not self._using_fallback:
                    self.get_logger().warning(
                        "VisionPoseBridge: TF child_frame_id is empty for all transforms; "
                        "using fallback_transform_index=%d" % idx
                    )
                    self._using_fallback = True
            else:
                self._using_fallback = False

        if tf_match is None:
            self._miss_count += 1
            if self._miss_count % 100 == 1:
                sample = ", ".join(t.child_frame_id for t in msg.transforms[:6])
                self.get_logger().warning(
                    "VisionPoseBridge: model '%s' not found in %d transforms. Sample: [%s]"
                    % (self._model_name, len(msg.transforms), sample)
                )
            return  # target model not in this message
        self._miss_count = 0

        out = PoseWithCovarianceStamped()
        if tf_match.header.stamp.sec != 0 or tf_match.header.stamp.nanosec != 0:
            out.header.stamp = tf_match.header.stamp
        else:
            out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = "map"
        out.pose.pose.position.x = tf_match.transform.translation.x
        out.pose.pose.position.y = tf_match.transform.translation.y
        out.pose.pose.position.z = tf_match.transform.translation.z
        out.pose.pose.orientation = tf_match.transform.rotation

        # Low covariance — ground-truth pose is "perfect"
        out.pose.covariance[0] = 0.01  # x
        out.pose.covariance[7] = 0.01  # y
        out.pose.covariance[14] = 0.01  # z
        out.pose.covariance[21] = 0.01  # roll
        out.pose.covariance[28] = 0.01  # pitch
        out.pose.covariance[35] = 0.01  # yaw

        self._pub.publish(out)


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
