# @loc:boilerplate:begin
#!/usr/bin/env python3
import math
import time

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from cv_bridge import CvBridge
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleLocalPosition,
    VehicleStatus,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

# @loc:boilerplate:end
# @loc:core:begin
CENTER_XY = 0.05
LOST_LIMIT = 30
TAG_SIZE = 0.2
# @loc:core:end
# @loc:boilerplate:begin
_ARMING_STATE_ARMED = 2
_NAV_STATE_OFFBOARD = 14


class PID:
    """Minimal PID (Nectar provides PIDController)."""

    def __init__(self, kp: float, ki: float, kd: float, limits=(-0.4, 0.4)) -> None:
        self.kp, self.ki, self.kd = kp, ki, kd
        self.lo, self.hi = limits
        self.setpoint = 0.0
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def reset(self) -> None:
        self._i = 0.0
        self._prev_err = 0.0
        self._prev_t = None

    def update(self, value: float) -> float:
        now = time.monotonic()
        err = self.setpoint - value
        if self._prev_t is None:
            self._prev_t = now
            self._prev_err = err
            return 0.0
        dt = max(now - self._prev_t, 1e-3)
        self._i = max(self.lo, min(self.hi, self._i + err * dt))
        d = (err - self._prev_err) / dt
        self._prev_err, self._prev_t = err, now
        out = self.kp * err + self.ki * self._i + self.kd * d
        return max(self.lo, min(self.hi, out))


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def yaw_enu_to_ned(yaw_enu: float) -> float:
    return math.pi / 2.0 - yaw_enu


class ArucoCenter(Node):
    """PX4 OFFBOARD over uXRCE-DDS + ArUco + ROS Image topic (GPS local pose)."""

    def __init__(self, image_topic: str = "/camera/color/image_raw") -> None:
        super().__init__("aruco_center_px4")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.local = None
        self.status = None
        self.frame = None
        self.bridge = CvBridge()
        self._sp_n = self._sp_e = self._sp_d = 0.0
        self._sp_yaw = 0.0
        self._vn = self._ve = self._vd = 0.0
        self._velocity_mode = False

        self.create_subscription(
            VehicleLocalPosition,
            "/fmu/out/vehicle_local_position_v1",
            self._on_local,
            qos,
        )
        self.create_subscription(
            VehicleStatus, "/fmu/out/vehicle_status_v4", self._on_status, qos
        )
        self.create_subscription(Image, image_topic, self._on_image, qos)
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

        self.dictionary = aruco.getPredefinedDictionary(aruco.DICT_5X5_1000)
        self.detector = aruco.ArucoDetector(self.dictionary, aruco.DetectorParameters())
        self.camera_matrix = np.load("camera_matrix.npy")
        self.dist_coeffs = np.load("dist_coeffs.npy")
        # @loc:boilerplate:end
        # @loc:core:begin
        self.pid_x = PID(kp=-0.4, ki=-0.02, kd=0.0)
        self.pid_y = PID(kp=-0.4, ki=-0.02, kd=0.0)
        # @loc:core:end
        # @loc:boilerplate:begin

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _on_local(self, msg: VehicleLocalPosition) -> None:
        self.local = msg

    def _on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _pump(self) -> None:
        mode = OffboardControlMode()
        mode.timestamp = self._now_us()
        mode.position = not self._velocity_mode
        mode.velocity = self._velocity_mode
        self.offboard_pub.publish(mode)
        sp = TrajectorySetpoint()
        sp.timestamp = self._now_us()
        if self._velocity_mode:
            sp.position = [math.nan, math.nan, math.nan]
            sp.velocity = [self._vn, self._ve, self._vd]
            sp.yaw = math.nan
        else:
            sp.position = [self._sp_n, self._sp_e, self._sp_d]
            sp.velocity = [math.nan, math.nan, math.nan]
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
        self._velocity_mode = False
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
        self._velocity_mode = False
        self._sp_n = float(self.local.x)
        self._sp_e = float(self.local.y)
        self._sp_d = float(self.local.z) - float(altitude)
        deadline = time.time() + timeout
        while time.time() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.local is not None and -self.local.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        assert self.local is not None
        yaw_enu = math.pi / 2.0 - float(self.local.heading)
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        ve = vx * c - vy * s
        vn = vx * s + vy * c
        self._vn, self._ve, self._vd = enu_to_ned(ve, vn, vz)
        self._velocity_mode = True

    def land(self) -> None:
        self._command(176, param1=1.0, param2=4.0, param3=6.0)

    def estimate_pose(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        if ids is None:
            return None, None
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, TAG_SIZE, self.camera_matrix, self.dist_coeffs
        )
        return int(ids[0][0]), tvecs[0][0]

    # @loc:boilerplate:end
    # @loc:core:begin
    def run_center(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        lost = 0
        rate = 1.0 / 30.0
        while True:
            now = time.time()
            rclpy.spin_once(self, timeout_sec=0.0)
            frame = self.frame
            if frame is None:
                continue
            marker_id, tvec = self.estimate_pose(frame)
            if tvec is None:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                while time.time() - now < rate:
                    rclpy.spin_once(self, timeout_sec=0.01)
                if lost >= LOST_LIMIT:
                    return
                continue
            lost = 0
            err_x, err_y = float(tvec[0]), float(tvec[1])
            if err_x * err_x + err_y * err_y <= CENTER_XY * CENTER_XY:
                self.publish_velocity(0.0, 0.0)
                return
            self.publish_velocity(self.pid_x.update(err_x), self.pid_y.update(err_y))
            while time.time() - now < rate:
                rclpy.spin_once(self, timeout_sec=0.01)

    # @loc:core:end
    # @loc:boilerplate:begin


def main() -> None:
    rclpy.init()
    node = ArucoCenter()
    try:
        node.wait_telemetry()
        node.enter_offboard_and_arm()
        # @loc:boilerplate:end
        # @loc:core:begin
        node.takeoff(1.2)
        node.run_center()
        node.land()
        # @loc:core:end
        # @loc:boilerplate:begin
        time.sleep(2.0)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
