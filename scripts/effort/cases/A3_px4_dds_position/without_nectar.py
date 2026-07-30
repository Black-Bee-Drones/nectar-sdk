# @loc:boilerplate:begin
#!/usr/bin/env python3
import math
import time

import rclpy
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

_ARMING_STATE_ARMED = 2
_NAV_STATE_OFFBOARD = 14


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def yaw_enu_to_ned(yaw_enu: float) -> float:
    return math.pi / 2.0 - yaw_enu


class Px4DdsPilot(Node):
    def __init__(self) -> None:
        super().__init__("px4_dds_position_mission")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.local = None
        self.status = None
        self._sp_n = self._sp_e = self._sp_d = 0.0
        self._sp_yaw = 0.0
        self._position_mode = True
        self.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position_v1",
            self._on_local,
            qos,
        )
        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status_v4", self._on_status, qos
        )
        self.offboard_pub = self.create_publisher(
            OffboardControlMode, "/fmu/in/offboard_control_mode", 10
        )
        self.setpoint_pub = self.create_publisher(
            TrajectorySetpoint, "/fmu/in/trajectory_setpoint", 10
        )
        self.command_pub = self.create_publisher(
            VehicleCommand, "/fmu/in/vehicle_command", 10
        )
        self.create_timer(0.05, self._pump)

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _on_local(self, msg: VehicleLocalPosition) -> None:
        self.local = msg

    def _on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    def _pump(self) -> None:
        mode = OffboardControlMode()
        mode.timestamp = self._now_us()
        mode.position = self._position_mode
        mode.velocity = not self._position_mode
        self.offboard_pub.publish(mode)
        sp = TrajectorySetpoint()
        sp.timestamp = self._now_us()
        if self._position_mode:
            sp.position = [self._sp_n, self._sp_e, self._sp_d]
            sp.velocity = [math.nan, math.nan, math.nan]
        else:
            sp.position = [math.nan, math.nan, math.nan]
            sp.velocity = [0.0, 0.0, 0.0]
        sp.yaw = self._sp_yaw
        sp.yawspeed = math.nan
        self.setpoint_pub.publish(sp)

    def _command(self, command: int, **params) -> None:
        msg = VehicleCommand()
        msg.timestamp = self._now_us()
        msg.command = int(command)
        for i in range(1, 8):
            setattr(msg, f"param{i}", float(params.get(f"param{i}", 0.0)))
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)

    def wait_telemetry(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.local is not None and self.status is not None:
                return
        raise TimeoutError("no PX4 telemetry on uXRCE-DDS")

    def hold_current(self) -> None:
        assert self.local is not None
        self._position_mode = True
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z)
        self._sp_yaw = yaw_enu_to_ned(math.pi / 2.0 - float(self.local.heading))

    def enter_offboard_and_arm(self) -> None:
        self.hold_current()
        for _ in range(20):
            rclpy.spin_once(self, timeout_sec=0.05)
        self._command(176, param1=1.0, param2=6.0, param3=0.0)
        self._command(400, param1=1.0)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if (
                self.status is not None
                and self.status.arming_state == _ARMING_STATE_ARMED
                and self.status.nav_state == _NAV_STATE_OFFBOARD
            ):
                return
        raise TimeoutError("OFFBOARD arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        assert self.local is not None
        self._position_mode = True
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z) - float(altitude)
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is not None and -self.local.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_body(
        self, forward: float, left: float, up: float, precision: float = 0.3
    ) -> None:
        assert self.local is not None
        ex0 = float(self.local.y)
        ey0 = float(self.local.x)
        ez0 = -float(self.local.z)
        yaw_enu = math.pi / 2.0 - float(self.local.heading)
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        ex = ex0 + forward * c - left * s
        ey = ey0 + forward * s + left * c
        ez = ez0 + up
        tn, te, td = enu_to_ned(ex, ey, ez)
        self._sp_n, self._sp_e, self._sp_d = tn, te, td
        self._sp_yaw = yaw_enu_to_ned(yaw_enu)
        deadline = time.time() + 60.0
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is None:
                continue
            cx, cy, cz = float(self.local.y), float(self.local.x), -float(self.local.z)
            if math.sqrt((cx - ex) ** 2 + (cy - ey) ** 2 + (cz - ez) ** 2) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        self._command(176, param1=1.0, param2=4.0, param3=6.0)


def main() -> None:
    rclpy.init()
    node = Px4DdsPilot()
    try:
        node.wait_telemetry()
        node.enter_offboard_and_arm()
        # @loc:boilerplate:end
        # @loc:core:begin
        node.takeoff(2.0)
        node.move_body(forward=5.0, left=0.0, up=0.0, precision=0.3)
        node.land()
        time.sleep(2.0)
    # @loc:core:end
    # @loc:boilerplate:begin
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
