# @loc:boilerplate:begin
#!/usr/bin/env python3
import math
import time

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

# @loc:boilerplate:end
# @loc:core:begin
LINE_COLOR = "blue"
CENTER_TOL_PX = 25.0
LOST_LIMIT = 40
FOLLOW_TIMEOUT_S = 20.0
CRUISE_VX = 0.25
RATE = 1.0 / 30.0
# @loc:core:end
# @loc:boilerplate:begin
# OpenCV HSV band for "blue" (stand-in for Nectar color preset).
HSV_LOW = (100, 80, 40)
HSV_HIGH = (130, 255, 255)


class PID:
    def __init__(self, kp: float, ki: float, kd: float, limits=(-0.35, 0.35)) -> None:
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


def detect_line_rotated_rect(frame):
    """Color mask + minAreaRect (RotatedRect-equivalent without Nectar)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(HSV_LOW), np.array(HSV_HIGH))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return float("nan"), float("nan"), float("nan")
    cnt = max(contours, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 50:
        return float("nan"), float("nan"), float("nan")
    rect = cv2.minAreaRect(cnt)
    (cx, cy), (_w, _h), angle = rect
    return float(cx), float(cy), float(angle)


class LineFollow(Node):
    def __init__(self) -> None:
        super().__init__("line_follow")
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
        self.vel_pub = self.create_publisher(
            TwistStamped, "/mavros/setpoint_velocity/cmd_vel", 10
        )
        self.mode_cli = self.create_client(SetMode, "/mavros/set_mode")
        self.arm_cli = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.takeoff_cli = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self.land_cli = self.create_client(CommandTOL, "/mavros/cmd/land")
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("cannot open webcam")
        # @loc:boilerplate:end
        # @loc:core:begin
        self.pid_y = PID(kp=-0.002, ki=0.0, kd=0.0)
        # @loc:core:end
        # @loc:boilerplate:begin

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
        raise TimeoutError("FCU not connected via MAVROS")

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

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = float(vx)
        msg.twist.linear.y = float(vy)
        msg.twist.linear.z = float(vz)
        self.vel_pub.publish(msg)
        rclpy.spin_once(self, timeout_sec=0.0)

    def land(self) -> None:
        req = CommandTOL.Request()
        req.altitude = 0.0
        self.call(self.land_cli, req)

    # @loc:boilerplate:end
    # @loc:core:begin
    def run(self) -> None:
        self.pid_y.reset()
        self.takeoff(1.2)
        lost = 0
        # ACQUIRE
        while True:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                continue
            cx, _cy, _angle = detect_line_rotated_rect(frame)
            if not math.isnan(cx):
                break
            lost += 1
            self.publish_velocity(0.0, 0.0)
            time.sleep(RATE)
            if lost >= LOST_LIMIT:
                self.land()
                return

        lost = 0
        t0 = time.time()
        while time.time() - t0 < FOLLOW_TIMEOUT_S:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                continue
            cx, _cy, _angle = detect_line_rotated_rect(frame)
            if math.isnan(cx):
                lost += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(RATE)
                if lost >= LOST_LIMIT:
                    break
                continue
            lost = 0
            h, w = frame.shape[:2]
            err_x = float(cx - w / 2.0)
            if abs(err_x) <= CENTER_TOL_PX:
                vy = 0.0
            else:
                vy = self.pid_y.update(err_x)
            self.publish_velocity(CRUISE_VX, vy)
            time.sleep(RATE)

        self.publish_velocity(0.0, 0.0)
        time.sleep(0.2)
        self.land()

    # @loc:core:end
    # @loc:boilerplate:begin
    def close(self) -> None:
        self.cap.release()


def main() -> None:
    rclpy.init()
    node = LineFollow()
    try:
        node.wait_connected()
        node.set_guided_and_arm()
        time.sleep(1.0)
        node.run()
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
