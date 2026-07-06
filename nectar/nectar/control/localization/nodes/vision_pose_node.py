#!/usr/bin/env python3
"""ROS2 node feeding a VSLAM pose to the FCU

The ``backend`` parameter selects how the external-nav estimate is delivered:

- ``mavros``  : republish onto ``/mavros/vision_pose/pose_cov`` (runs alongside
  MAVROS), via :class:`nectar.control.localization.MavrosVisionRelay`.
- ``mavlink`` : send ``VISION_POSITION_ESTIMATE`` over a dedicated pymavlink
  link (no MAVROS), reusing :class:`nectar.control.mavlink.VisionPoseBridge`.
- ``dds``     : publish ``px4_msgs/VehicleOdometry`` on
  ``/fmu/in/vehicle_visual_odometry`` (PX4 native uXRCE-DDS), via
  :class:`nectar.control.px4.vision_bridge.Px4VisionOdometryBridge`.

Run::

    ros2 run nectar vision_pose_node.py --ros-args -p backend:=mavros
    ros2 run nectar vision_pose_node.py --ros-args \\
        -p backend:=mavlink -p mavlink_url:=udp:127.0.0.1:14551
    ros2 run nectar vision_pose_node.py --ros-args -p backend:=dds
"""

import rclpy
from rclpy.node import Node

from nectar.control.localization.vision_pose_bridge import MavrosVisionRelay


class VisionPoseNode(Node):
    """Wire a VSLAM pose topic to the FCU through the selected backend."""

    BACKEND_MAVROS = "mavros"
    BACKEND_MAVLINK = "mavlink"
    BACKEND_DDS = "dds"

    def __init__(self) -> None:
        super().__init__("vision_pose_node")

        self.declare_parameter("backend", self.BACKEND_MAVROS)
        self.declare_parameter("input_topic", "/visual_slam/tracking/vo_pose_covariance")
        self.declare_parameter("output_topic", "/mavros/vision_pose/pose_cov")
        self.declare_parameter("frame_id", "")

        self.declare_parameter("mavlink_url", "udp:127.0.0.1:14551")
        self.declare_parameter("mavlink_baud", 921600)
        self.declare_parameter("source_system", 1)
        self.declare_parameter("source_component", 191)
        self.declare_parameter("heartbeat_timeout_s", 30.0)

        self.declare_parameter("odometry_topic", "/fmu/in/vehicle_visual_odometry")
        self.declare_parameter("px4_namespace", "")

        self._relay = None
        self._connection = None
        self._bridge = None
        self._dds_bridge = None

        backend = self.get_parameter("backend").value
        if backend == self.BACKEND_MAVROS:
            self._start_mavros()
        elif backend == self.BACKEND_MAVLINK:
            self._start_mavlink()
        elif backend == self.BACKEND_DDS:
            self._start_dds()
        else:
            raise ValueError(
                f"Unknown backend '{backend}'. Valid: {self.BACKEND_MAVROS}, "
                f"{self.BACKEND_MAVLINK}, {self.BACKEND_DDS}"
            )

    def _start_mavros(self) -> None:
        self._relay = MavrosVisionRelay(
            node=self,
            input_topic=self.get_parameter("input_topic").value,
            output_topic=self.get_parameter("output_topic").value,
            frame_id=self.get_parameter("frame_id").value,
        )
        self._relay.start()

    def _start_mavlink(self) -> None:
        from nectar.control.mavlink import MavlinkConnection, VisionPoseBridge

        url = self.get_parameter("mavlink_url").value
        baud = int(self.get_parameter("mavlink_baud").value)
        self.get_logger().info(f"Connecting MAVLink to {url}")
        self._connection = MavlinkConnection(
            source_system=int(self.get_parameter("source_system").value),
            source_component=int(self.get_parameter("source_component").value),
            heartbeat_timeout=float(self.get_parameter("heartbeat_timeout_s").value),
        )
        self._connection.connect(url, baud=baud)
        self._bridge = VisionPoseBridge(
            node=self,
            connection=self._connection,
            topic=self.get_parameter("input_topic").value,
        )
        self._bridge.start()

    def _start_dds(self) -> None:
        from nectar.control.px4.vision_bridge import Px4VisionOdometryBridge

        self._dds_bridge = Px4VisionOdometryBridge(
            node=self,
            input_topic=self.get_parameter("input_topic").value,
            output_topic=self.get_parameter("odometry_topic").value,
            px4_namespace=self.get_parameter("px4_namespace").value,
        )
        self._dds_bridge.start()

    def destroy_node(self) -> bool:
        if self._relay is not None:
            self._relay.stop()
        if self._bridge is not None:
            self._bridge.stop()
        if self._dds_bridge is not None:
            self._dds_bridge.stop()
        if self._connection is not None:
            self._connection.close()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VisionPoseNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
