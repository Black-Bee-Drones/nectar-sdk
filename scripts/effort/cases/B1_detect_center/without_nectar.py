# @loc:boilerplate:begin
#!/usr/bin/env python3
import time

import cv2
from pymavlink import mavutil
from ultralytics import YOLO

# @loc:boilerplate:end
# @loc:core:begin
CENTER_PX = 40.0
LOST_LIMIT = 30
TARGET_CLASS = "person"
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


class DetectCenter:
    """ArduPilot GUIDED over pymavlink + YOLO + webcam.

    Indoor EKF still needs an external VISION_POSITION_ESTIMATE feed (separate
    VSLAM relay). Nectar starts that bridge when pose_source=VISION.
    """

    def __init__(self, connection_string: str = "udp:127.0.0.1:14550") -> None:
        self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True)
        self.master.wait_heartbeat()
        self._local = None
        self._request_streams()
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

    def set_mode(self, mode: str) -> None:
        mapping = self.master.mode_mapping()
        if mode not in mapping:
            raise RuntimeError(f"mode {mode!r} not in mode_mapping")
        self.master.mav.set_mode_send(
            self.master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mapping[mode],
        )
        deadline = time.time() + 5.0
        while time.time() < deadline:
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if hb and mavutil.mode_string_v10(hb) == mode:
                return
        raise TimeoutError(f"failed to enter {mode}")

    def arm(self) -> None:
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
            if hb and (hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                return
        raise TimeoutError("arm failed")

    def takeoff(self, altitude: float, timeout: float = 25.0) -> None:
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            _M.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            float(altitude),
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._spin_local()
            if msg is not None and -msg.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def publish_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
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

    def land(self) -> None:
        self.set_mode("LAND")

    # @loc:boilerplate:end
    # @loc:core:begin
    def run_center(self) -> None:
        self.pid_x.reset()
        self.pid_y.reset()
        lost = 0
        rate = 1.0 / 30.0
        while True:
            ok, frame = self.cap.read()
            self._spin_local(timeout=0.0)
            if not ok or frame is None:
                continue
            out = self.model.predict(frame, conf=0.25, verbose=False)[0]
            names = out.names
            candidates = []
            if out.boxes is not None:
                for box in out.boxes:
                    cls_id = int(box.cls.item())
                    if names[cls_id] == TARGET_CLASS:
                        candidates.append(box)
            if not candidates:
                lost += 1
                self.publish_velocity(0.0, 0.0)
                time.sleep(rate)
                if lost >= LOST_LIMIT:
                    return
                continue
            lost = 0
            box = max(candidates, key=lambda b: float(b.conf.item()))
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            h, w = frame.shape[:2]
            err_x = float(cx - w / 2.0)
            err_y = float(cy - h / 2.0)
            if err_x * err_x + err_y * err_y <= CENTER_PX * CENTER_PX:
                self.publish_velocity(0.0, 0.0)
                return
            self.publish_velocity(self.pid_y.update(err_y), self.pid_x.update(-err_x))
            time.sleep(rate)

    # @loc:core:end
    # @loc:boilerplate:begin
    def close(self) -> None:
        self.cap.release()


def main() -> None:
    pilot = DetectCenter("udp:127.0.0.1:14550")
    try:
        pilot.set_mode("GUIDED")
        pilot.arm()
        time.sleep(1.0)
        # @loc:boilerplate:end
        # @loc:core:begin
        pilot.takeoff(1.2)
        pilot.run_center()
        pilot.land()
        # @loc:core:end
        # @loc:boilerplate:begin
    finally:
        pilot.close()


if __name__ == "__main__":
    main()
# @loc:boilerplate:end
