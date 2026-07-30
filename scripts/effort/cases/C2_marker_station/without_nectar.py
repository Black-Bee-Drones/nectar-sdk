# @loc:boilerplate:begin
#!/usr/bin/env python3
"""Marker station approach without Nectar (MAVROS + OpenCV ArUco)."""

import time

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped, TwistStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

# @loc:boilerplate:end
# @loc:core:begin
CENTER_XY = 0.05
STANDOFF_M = 1.0
TOL_M = 0.15
LOST_LIMIT = 30
SETTLE_CONFIRM = 3
APPROACH_GAIN = 0.3
RATE = 1.0 / 30.0
TAG_SIZE = 0.2
# @loc:core:end
# @loc:boilerplate:begin


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


class MarkerApproach(Node):
    def __init__(self, image_topic: str = "/camera/color/image_raw") -> None:
        super().__init__("marker_approach")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.state = State()
        self.pose = PoseStamped()
        self.frame = None
        self.bridge = CvBridge()
        self.create_subscription(
            State, "/mavros/state", lambda m: setattr(self, "state", m), 10
        )
        self.create_subscription(
            PoseStamped,
            "/mavros/local_position/pose",
            lambda m: setattr(self, "pose", m),
            qos,
        )
        self.create_subscription(Image, image_topic, self._on_image, qos)
        self.vel_pub = self.create_publisher(
            TwistStamped, "/mavros/setpoint_velocity/cmd_vel", 10
        )
        self.mode_cli = self.create_client(SetMode, "/mavros/set_mode")
        self.arm_cli = self.create_client(CommandBool, "/mavros/cmd/arming")
        self.takeoff_cli = self.create_client(CommandTOL, "/mavros/cmd/takeoff")
        self.land_cli = self.create_client(CommandTOL, "/mavros/cmd/land")
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

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

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

    def land(self) -> None:
        req = CommandTOL.Request()
        req.altitude = 0.0
        self.call(self.land_cli, req)

    def estimate_pose(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        if ids is None:
            return None, None
        _rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            corners, TAG_SIZE, self.camera_matrix, self.dist_coeffs
        )
        return int(ids[0][0]), tvecs[0][0]

    # @loc:boilerplate:end
    # @loc:core:begin
    def run_station(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        lost = 0
        tvec = None
        # SEARCH
        while True:
            now = time.time()
            rclpy.spin_once(self, timeout_sec=0.0)
            frame = self.frame
            if frame is None:
                continue
            marker_id, tvec = self.estimate_pose(frame)
            if tvec is not None:
                break
            lost += 1
            self.publish_velocity(0.0, 0.0)
            while time.time() - now < RATE:
                rclpy.spin_once(self, timeout_sec=0.01)
            if lost >= LOST_LIMIT:
                return

        phase = "center"
        settles = 0
        lost = 0
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
                while time.time() - now < RATE:
                    rclpy.spin_once(self, timeout_sec=0.01)
                if lost >= LOST_LIMIT:
                    return
                continue
            lost = 0
            err_x, err_y, err_z = float(tvec[0]), float(tvec[1]), float(tvec[2])
            centered = err_x * err_x + err_y * err_y <= CENTER_XY * CENTER_XY
            range_err = float(err_z - STANDOFF_M)
            in_band = centered and abs(range_err) <= TOL_M

            if phase == "center":
                if centered:
                    phase = "approach"
                else:
                    self.publish_velocity(
                        self.pid_x.update(err_x), self.pid_y.update(err_y)
                    )
                    while time.time() - now < RATE:
                        rclpy.spin_once(self, timeout_sec=0.01)
                    continue

            if phase == "approach":
                if in_band:
                    phase = "settle"
                    settles = 0
                else:
                    vx = (
                        APPROACH_GAIN * range_err
                        if centered
                        else self.pid_x.update(err_x)
                    )
                    self.publish_velocity(vx, self.pid_y.update(err_y))
                    while time.time() - now < RATE:
                        rclpy.spin_once(self, timeout_sec=0.01)
                    continue

            if in_band:
                settles += 1
                self.publish_velocity(0.0, 0.0)
                while time.time() - now < RATE:
                    rclpy.spin_once(self, timeout_sec=0.01)
                if settles >= SETTLE_CONFIRM:
                    return
            else:
                settles = 0
                phase = "approach" if centered else "center"

    # @loc:core:end
    # @loc:boilerplate:begin


def main() -> None:
    rclpy.init()
    node = MarkerApproach()
    try:
        node.wait_connected()
        node.set_guided_and_arm()
        time.sleep(1.0)
        # @loc:boilerplate:end
        # @loc:core:begin
        node.takeoff(1.2)
        node.run_station()
        node.land()
        # @loc:core:end
        # @loc:boilerplate:begin
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
