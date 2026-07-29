# @loc:boilerplate:begin
#!/usr/bin/env python3
"""Stack A Without: MAVROS GUIDED + OAK-D + Ultralytics seg/cls + DO_SET_SERVO."""

import time

import depthai as dai
import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from mavros_msgs.msg import State
from mavros_msgs.srv import CommandBool, CommandLong, CommandTOL, SetMode
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from ultralytics import YOLO

# @loc:boilerplate:end
# @loc:core:begin
CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_SEG_CLASS = "person"
CONFIRM_LABEL = "person"
STANDOFF_M = 1.2
APPROACH_VX = 0.2
RATE = 1.0 / 30.0
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


class StackAPilot(Node):
    def __init__(self) -> None:
        super().__init__("c8_stack_a")
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
        self.cmd_cli = self.create_client(CommandLong, "/mavros/cmd/command")
        self.seg_model = YOLO("yolov8n-seg.pt")
        self.cls_model = YOLO("yolov8n-cls.pt")
        pipeline = dai.Pipeline()
        cam_rgb = pipeline.create(dai.node.ColorCamera)
        cam_rgb.setBoardSocket(dai.CameraBoardSocket.CAM_A)
        cam_rgb.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        mono_l = pipeline.create(dai.node.MonoCamera)
        mono_r = pipeline.create(dai.node.MonoCamera)
        mono_l.setBoardSocket(dai.CameraBoardSocket.CAM_B)
        mono_r.setBoardSocket(dai.CameraBoardSocket.CAM_C)
        stereo = pipeline.create(dai.node.StereoDepth)
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
        mono_l.out.link(stereo.left)
        mono_r.out.link(stereo.right)
        xout_rgb = pipeline.create(dai.node.XLinkOut)
        xout_rgb.setStreamName("rgb")
        cam_rgb.video.link(xout_rgb.input)
        xout_depth = pipeline.create(dai.node.XLinkOut)
        xout_depth.setStreamName("depth")
        stereo.depth.link(xout_depth.input)
        self._device = dai.Device(pipeline)
        self._q_rgb = self._device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        self._q_depth = self._device.getOutputQueue(
            name="depth", maxSize=4, blocking=False
        )
        # @loc:boilerplate:end
        # @loc:core:begin
        self.pid_x = PID(kp=-0.002, ki=0.0, kd=0.0)
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

    def hold_payload(self) -> None:
        req = CommandLong.Request()
        req.command = 183
        req.param1 = float(1 + 8)
        req.param2 = 1000.0
        self.call(self.cmd_cli, req)

    def release_payload(self) -> None:
        req = CommandLong.Request()
        req.command = 183
        req.param1 = float(1 + 8)
        req.param2 = 2000.0
        self.call(self.cmd_cli, req)

    def land(self) -> None:
        req = CommandTOL.Request()
        req.altitude = 0.0
        self.call(self.land_cli, req)

    def get_range(self, cx: float, cy: float, pixel_h: float):
        del pixel_h
        depth_msg = self._q_depth.tryGet()
        if depth_msg is None:
            return None
        depth = depth_msg.getFrame()
        u, v = int(cx), int(cy)
        if v < 0 or u < 0 or v >= depth.shape[0] or u >= depth.shape[1]:
            return None
        # OAK-D depth is typically millimeters.
        mm = float(depth[v, u])
        if mm <= 0.0:
            return None
        return mm / 1000.0

    def read_target(self):
        packet = self._q_rgb.tryGet()
        if packet is None:
            return None, None
        frame = packet.getCvFrame()
        out = self.seg_model.predict(frame, conf=0.25, verbose=False)[0]
        names = out.names
        candidates = []
        if out.boxes is not None and out.masks is not None:
            for i, box in enumerate(out.boxes):
                cls_id = int(box.cls.item())
                if names[cls_id] != TARGET_SEG_CLASS:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                candidates.append(
                    {
                        "conf": float(box.conf.item()),
                        "xyxy": (x1, y1, x2, y2),
                        "center": ((x1 + x2) / 2.0, (y1 + y2) / 2.0),
                        "height": abs(y2 - y1),
                    }
                )
        if not candidates:
            return frame, None
        return frame, max(candidates, key=lambda c: c["conf"])

    def confirm(self, frame, seg) -> bool:
        x1, y1, x2, y2 = [int(v) for v in seg["xyxy"]]
        x1, y1 = max(0, x1), max(0, y1)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return False
        out = self.cls_model.predict(crop, verbose=False)[0]
        top1 = int(out.probs.top1)
        return out.names[top1] == CONFIRM_LABEL

    # @loc:boilerplate:end
    # @loc:core:begin
    def run(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        self.takeoff(1.5)

        centered_seg = None
        lost = 0
        while True:
            frame, seg = self.read_target()
            if seg is None:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(RATE)
                if lost >= LOST_LIMIT:
                    break
                continue
            lost = 0
            h, w = frame.shape[:2]
            cx, cy = seg["center"]
            err_x = float(cx - w / 2.0)
            err_y = float(cy - h / 2.0)
            if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
                self.publish_velocity(0.0, 0.0)
                centered_seg = seg
                break
            self.publish_velocity(self.pid_y.update(err_y), self.pid_x.update(-err_x))
            time.sleep(RATE)

        confirmed = False
        if centered_seg is not None:
            frame, _ = self.read_target()
            if frame is not None:
                confirmed = self.confirm(frame, centered_seg)

        approached = False
        if confirmed:
            lost = 0
            while True:
                frame, seg = self.read_target()
                if seg is None:
                    lost += 1
                    self.publish_velocity(0.0, 0.0)
                    time.sleep(RATE)
                    if lost >= LOST_LIMIT:
                        break
                    continue
                lost = 0
                h, w = frame.shape[:2]
                cx, cy = seg["center"]
                err_x = float(cx - w / 2.0)
                range_m = self.get_range(cx, cy, float(seg["height"]))
                if range_m is not None and range_m <= STANDOFF_M:
                    self.publish_velocity(0.0, 0.0)
                    approached = True
                    break
                self.publish_velocity(APPROACH_VX, self.pid_x.update(-err_x))
                time.sleep(RATE)

        if approached:
            self.hold_payload()
            time.sleep(1.0)
            self.release_payload()
            time.sleep(1.0)

        self.land()

    # @loc:core:end
    # @loc:boilerplate:begin
    def close(self) -> None:
        self._device.close()


def main() -> None:
    rclpy.init()
    node = StackAPilot()
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
