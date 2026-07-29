# @loc:boilerplate:begin
#!/usr/bin/env python3
import math
import time

import cv2
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
from ultralytics import YOLO

# @loc:boilerplate:end
# @loc:core:begin
N_GATES = 2
GATE_CLASS = "gate"
CENTER_PX = 40.0
CENTER_CONFIRM = 3
LOST_LIMIT = 30
SEARCH_STEP_M = 0.4
SEARCH_STEPS = 6
PASS_M = 1.5
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin
_ARMING_STATE_ARMED = 2
_NAV_STATE_OFFBOARD = 14


class PID:
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


class GatePilot(Node):
    """PX4 OFFBOARD over uXRCE-DDS + YOLO + webcam."""

    def __init__(self) -> None:
        super().__init__("gate_sequence_px4")
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
        self.model = YOLO("yolov8n.pt")
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("cannot open webcam")
        # @loc:boilerplate:end
        # @loc:core:begin
        self.pid_x = PID(kp=-0.002, ki=0.0, kd=0.0)
        self.pid_y = PID(kp=-0.002, ki=0.0, kd=0.0)
        # @loc:core:end
        # @loc:boilerplate:begin

    def _now_us(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def _on_local(self, msg: VehicleLocalPosition) -> None:
        self.local = msg

    def _on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

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

    def _read_gate(self):
        ok, frame = self.cap.read()
        rclpy.spin_once(self, timeout_sec=0.0)
        if not ok or frame is None:
            return None, None
        out = self.model.predict(frame, conf=0.25, verbose=False)[0]
        names = out.names
        candidates = []
        if out.boxes is not None:
            for box in out.boxes:
                cls_id = int(box.cls.item())
                if names[cls_id] == GATE_CLASS:
                    candidates.append(box)
        if not candidates:
            return frame, None
        box = max(candidates, key=lambda b: float(b.conf.item()))
        return frame, box

    # @loc:boilerplate:end
    # @loc:core:begin
    def search_gate(self) -> bool:
        for step in range(SEARCH_STEPS):
            frame, box = self._read_gate()
            if box is not None:
                return True
            vy = SEARCH_STEP_M if (step % 2 == 0) else -SEARCH_STEP_M
            vz = 0.15 if (step % 4 == 3) else 0.0
            self.publish_velocity(0.0, vy, vz)
            time.sleep(0.8)
        return False

    def align_gate(self) -> bool:
        self.pid_x.reset()
        self.pid_y.reset()
        confirms = 0
        lost = 0
        while True:
            frame, box = self._read_gate()
            if box is None:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(RATE)
                if lost >= LOST_LIMIT:
                    return False
                continue
            lost = 0
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            h, w = frame.shape[:2]
            err_x = float(cx - w / 2.0)
            err_y = float(cy - h / 2.0)
            if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
                confirms += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(RATE)
                if confirms >= CENTER_CONFIRM:
                    return True
                continue
            confirms = 0
            self.publish_velocity(self.pid_y.update(err_y), self.pid_x.update(-err_x))
            time.sleep(RATE)

    def pass_gate(self) -> None:
        self.publish_velocity(PASS_M / 2.0, 0.0)
        time.sleep(2.0)
        self.publish_velocity(0.0, 0.0)
        time.sleep(0.2)

    def run(self) -> None:
        self.takeoff(1.2)
        for _ in range(N_GATES):
            if not self.search_gate():
                break
            if not self.align_gate():
                break
            self.pass_gate()
        self.land()

    # @loc:core:end
    # @loc:boilerplate:begin
    def close(self) -> None:
        self.cap.release()


def main() -> None:
    rclpy.init()
    node = GatePilot()
    try:
        node.wait_telemetry()
        node.enter_offboard_and_arm()
        time.sleep(1.0)
        node.run()
        time.sleep(2.0)
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
