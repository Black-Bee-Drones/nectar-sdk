# @loc:boilerplate:begin
#!/usr/bin/env python3
"""Stack B Without: PX4 pymavlink OFFBOARD + ROS RGB + HF seg/cls + geometric range."""

import time

import cv2
import numpy as np
import rclpy
import torch
from cv_bridge import CvBridge
from PIL import Image as PILImage
from pymavlink import mavutil
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
    AutoModelForUniversalSegmentation,
)

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
_M = mavutil.mavlink
_VELOCITY_MASK = (
    _M.POSITION_TARGET_TYPEMASK_X_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Y_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Z_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_IGNORE
)
# PX4 custom mode packing: main=6 (OFFBOARD), sub=0 → custom_mode field.
_PX4_OFFBOARD_CUSTOM = 6 << 16
_PX4_AUTO_LAND_CUSTOM = (4 << 16) | (6 << 0)


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


class StackBPilot(Node):
    def __init__(self, connection_string: str = "udp:0.0.0.0:14540") -> None:
        super().__init__("c8_stack_b")
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.bridge = CvBridge()
        self.frame = None
        self.create_subscription(Image, "/camera/color/image_raw", self._on_image, qos)
        self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True)
        self.master.wait_heartbeat()
        self._local = None
        self._request_streams()
        self.seg_processor = AutoImageProcessor.from_pretrained(
            "facebook/maskformer-swin-tiny-coco"
        )
        self.seg_model = AutoModelForUniversalSegmentation.from_pretrained(
            "facebook/maskformer-swin-tiny-coco"
        )
        self.seg_model.eval()
        self.cls_processor = AutoImageProcessor.from_pretrained(
            "google/vit-base-patch16-224"
        )
        self.cls_model = AutoModelForImageClassification.from_pretrained(
            "google/vit-base-patch16-224"
        )
        self.cls_model.eval()
        # @loc:boilerplate:end
        # @loc:core:begin
        self.pid_x = PID(kp=-0.002, ki=0.0, kd=0.0)
        self.pid_y = PID(kp=-0.002, ki=0.0, kd=0.0)
        # @loc:core:end
        # @loc:boilerplate:begin

    def _on_image(self, msg: Image) -> None:
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _request_streams(self) -> None:
        for msg_id, hz in (
            (_M.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 20),
            (_M.MAVLINK_MSG_ID_ATTITUDE, 20),
            (_M.MAVLINK_MSG_ID_HEARTBEAT, 1),
        ):
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                _M.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                msg_id,
                int(1e6 / hz),
                0,
                0,
                0,
                0,
                0,
            )

    def _spin_local(self, timeout: float = 0.5):
        msg = self.master.recv_match(
            type="LOCAL_POSITION_NED", blocking=True, timeout=timeout
        )
        if msg is not None:
            self._local = msg
        return self._local

    def _set_px4_mode(self, custom_mode: int) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_DO_SET_MODE,
            0,
            float(_M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED),
            float((custom_mode >> 16) & 0xFF),
            float(custom_mode & 0xFFFF),
            0,
            0,
            0,
            0,
        )

    def enter_offboard_and_arm(self) -> None:
        # Seed setpoints before OFFBOARD (PX4 requirement).
        for _ in range(20):
            self.publish_velocity(0.0, 0.0, 0.0)
            time.sleep(0.05)
        self._set_px4_mode(_PX4_OFFBOARD_CUSTOM)
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        deadline = time.time() + 6.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and (hb.base_mode & _M.MAV_MODE_FLAG_SAFETY_ARMED):
                return
        raise TimeoutError("PX4 arm/OFFBOARD failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        # Climb via body-up velocity until local -z reaches altitude.
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.publish_velocity(0.0, 0.0, 0.5)
            msg = self._spin_local(timeout=0.1)
            if msg is not None and -msg.z >= altitude - 0.3:
                self.publish_velocity(0.0, 0.0, 0.0)
                return
        raise TimeoutError("takeoff settle")

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        # PX4 LOCAL_NED: +x forward north, +y east, +z down.
        vn, ve, vd = float(vx), -float(vy), -float(vz)
        self.master.mav.set_position_target_local_ned_send(
            0,
            self.master.target_system,
            self.master.target_component,
            _M.MAV_FRAME_BODY_NED,
            _VELOCITY_MASK,
            0.0,
            0.0,
            0.0,
            vn,
            ve,
            vd,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )
        self._spin_local(timeout=0.0)

    def hold_payload(self) -> None:
        # MAV_CMD_DO_SET_ACTUATOR (187); param1 = actuator 1 value in [-1, 1].
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            187,
            0,
            -1.0,
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            0.0,
        )

    def release_payload(self) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            187,
            0,
            1.0,
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            float("nan"),
            0.0,
        )

    def land(self) -> None:
        self._set_px4_mode(_PX4_AUTO_LAND_CUSTOM)

    def get_range(self, cx: float, cy: float, pixel_h: float):
        del cx, cy
        # Linear height→distance proxy (cm→m); role-equivalent to DistanceEstimator.
        cm = 2200.0 / max(float(pixel_h), 1.0)
        return cm / 100.0

    def read_target(self):
        rclpy.spin_once(self, timeout_sec=0.05)
        frame = self.frame
        if frame is None:
            return None, None
        pil = PILImage.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        inputs = self.seg_processor(images=pil, return_tensors="pt")
        with torch.no_grad():
            outputs = self.seg_model(**inputs)
        result = self.seg_processor.post_process_instance_segmentation(
            outputs, target_sizes=[pil.size[::-1]]
        )[0]
        id2label = self.seg_model.config.id2label
        candidates = []
        segments = result.get("segments_info") or []
        for info in segments:
            label = id2label.get(int(info["label_id"]), "")
            if label != TARGET_SEG_CLASS:
                continue
            # Approximate bbox from mask if present.
            mask = result.get("segmentation")
            if mask is None:
                continue
            ys, xs = np.where(mask.numpy() == int(info["id"]))
            if len(xs) == 0:
                continue
            x1, x2 = float(xs.min()), float(xs.max())
            y1, y2 = float(ys.min()), float(ys.max())
            candidates.append(
                {
                    "conf": float(info.get("score", 0.5)),
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
        pil = PILImage.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        inputs = self.cls_processor(images=pil, return_tensors="pt")
        with torch.no_grad():
            outputs = self.cls_model(**inputs)
        pred = int(outputs.logits.argmax(-1).item())
        name = self.cls_model.config.id2label[pred]
        return name == CONFIRM_LABEL

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


def main() -> None:
    rclpy.init()
    node = StackBPilot()
    try:
        deadline = time.time() + 30.0
        while time.time() < deadline and node.frame is None:
            rclpy.spin_once(node, timeout_sec=0.1)
        node.enter_offboard_and_arm()
        time.sleep(1.0)
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
