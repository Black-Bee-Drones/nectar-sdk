# @loc:boilerplate:begin
#!/usr/bin/env python3
"""Relay an external pose topic into MAVROS vision_pose (FCU EKF).

Topic names are parameters — match your producer. MAVLink without Nectar sends
VISION_POSITION_ESTIMATE instead; PX4 DDS publishes VehicleOdometry. See
Localization README for those paths.
"""

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data


class VisionPoseRelay(Node):
    def __init__(
        self,
        input_topic: str = "/visual_slam/tracking/vo_pose_covariance",
        output_topic: str = "/mavros/vision_pose/pose_cov",
    ) -> None:
        super().__init__("vision_pose_relay")
        self.pub = self.create_publisher(
            PoseWithCovarianceStamped, output_topic, qos_profile_sensor_data
        )
        self.create_subscription(
            PoseWithCovarianceStamped,
            input_topic,
            self._on_pose,
            qos_profile_sensor_data,
        )

    def _on_pose(self, msg: PoseWithCovarianceStamped) -> None:
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = VisionPoseRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
