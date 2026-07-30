# @loc:boilerplate:begin
#!/usr/bin/env python3
"""GPS patrol without Nectar (MAVROS position). PoseSource.GPS path."""

import math
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget, State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

_POSITION_MASK = (
    PositionTarget.IGNORE_VX
    | PositionTarget.IGNORE_VY
    | PositionTarget.IGNORE_VZ
    | PositionTarget.IGNORE_AFX
    | PositionTarget.IGNORE_AFY
    | PositionTarget.IGNORE_AFZ
    | PositionTarget.IGNORE_YAW_RATE
)


def yaw_from_quat(q) -> float:
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


class GpsPatrol(Node):
    def __init__(self) -> None:
        super().__init__("gps_patrol")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.state = State()
        self.pose = PoseStamped()
        self.create_subscription(
            State, "/mavros/state", lambda m: setattr(self, "state", m), 10
        )
        self.create_subscription(
            PoseStamped,
            "/mavros/local_position/pose",
            lambda m: setattr(self, "pose", m),
            qos,
        )
        self.setpoint_pub = self.create_publisher(
            PositionTarget, "/mavros/setpoint_raw/local", 10
        )
        self.mode_cli = self.create_client(SetMode, "/mavros/set_mode")
        self.arm_cli = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.takeoff_cli = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self.land_cli = self.create_client(CommandTOL, "/mavros/cmd/land")

    def call(self, client, request, timeout: float = 5.0):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"service unavailable: {client.srv_name}")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
        if future.result() is None:
            raise RuntimeError(f"service call failed: {client.srv_name}")
        return future.result()

    def wait_connected(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.state.connected:
                return
        raise TimeoutError("FCU not connected")

    def set_guided_and_arm(self) -> None:
        req = SetMode.Request()
        req.custom_mode = "GUIDED"
        self.call(self.mode_cli, req)
        while self.state.mode != "GUIDED":
            rclpy.spin_once(self, timeout_sec=0.1)
        arm = CommandBool.Request()
        arm.value = True
        self.call(self.arm_cli, arm)
        while not self.state.armed:
            rclpy.spin_once(self, timeout_sec=0.1)

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        req = CommandTOL.Request()
        req.altitude = float(altitude)
        self.call(self.takeoff_cli, req)
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.pose.pose.position.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_to_local(
        self, x: float, y: float, z: float, precision: float = 0.3
    ) -> None:
        yaw = yaw_from_quat(self.pose.pose.orientation)
        target = PositionTarget()
        target.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        target.type_mask = _POSITION_MASK
        target.position.x = float(x)
        target.position.y = float(y)
        target.position.z = float(z)
        target.yaw = float(yaw)
        deadline = time.time() + 60.0
        while time.time() < deadline:
            target.header.stamp = self.get_clock().now().to_msg()
            self.setpoint_pub.publish(target)
            rclpy.spin_once(self, timeout_sec=0.05)
            dx = self.pose.pose.position.x - x
            dy = self.pose.pose.position.y - y
            dz = self.pose.pose.position.z - z
            if math.sqrt(dx * dx + dy * dy + dz * dz) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        req = CommandTOL.Request()
        req.altitude = 0.0
        self.call(self.land_cli, req)


def main() -> None:
    rclpy.init()
    node = GpsPatrol()
    try:
        node.wait_connected()
        node.set_guided_and_arm()
        time.sleep(1.0)
        # @loc:boilerplate:end
        # @loc:core:begin
        node.takeoff(2.0)
        node.move_to_local(3.0, 0.0, 2.0, precision=0.3)
        node.move_to_local(3.0, 3.0, 2.0, precision=0.3)
        node.land()
        # @loc:core:end
        # @loc:boilerplate:begin
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
