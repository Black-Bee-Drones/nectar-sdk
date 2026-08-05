#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

os.environ.setdefault("MAVLINK20", "1")

from pymavlink import mavutil

from nectar.control.mavlink.connection import normalize_connection_string

_WIRE_TYPES = ("VISION_POSITION_ESTIMATE", "VISION_SPEED_ESTIMATE")
_FUSED_TYPES = (
    "LOCAL_POSITION_NED",
    "ATTITUDE",
    "EKF_STATUS_REPORT",
    "GPS_RAW_INT",
    "HEARTBEAT",
)
_ALL_TYPES = _WIRE_TYPES + _FUSED_TYPES

# EKF_STATUS_FLAGS (common.xml) — horizontal position absolute / relative.
_EKF_POS_HORIZ_ABS = 1 << 1
_EKF_POS_HORIZ_REL = 1 << 7

_AUTOPILOT_NAMES = {
    mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA: "ArduPilot",
    mavutil.mavlink.MAV_AUTOPILOT_PX4: "PX4",
    mavutil.mavlink.MAV_AUTOPILOT_GENERIC: "Generic",
}

_TYPE_NAMES = {
    mavutil.mavlink.MAV_TYPE_QUADROTOR: "Quadrotor",
    mavutil.mavlink.MAV_TYPE_HEXAROTOR: "Hexarotor",
    mavutil.mavlink.MAV_TYPE_OCTOROTOR: "Octorotor",
    mavutil.mavlink.MAV_TYPE_COAXIAL: "Coaxial",
    mavutil.mavlink.MAV_TYPE_HELICOPTER: "Helicopter",
    mavutil.mavlink.MAV_TYPE_FIXED_WING: "FixedWing",
    mavutil.mavlink.MAV_TYPE_GROUND_ROVER: "Rover",
}


@dataclass
class _MsgStats:
    stamps: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    last_wall: float = 0.0
    last_payload: Optional[dict] = None

    def hit(self, payload: Optional[dict] = None) -> None:
        now = time.monotonic()
        self.stamps.append(now)
        self.last_wall = now
        if payload is not None:
            self.last_payload = payload

    @property
    def hz(self) -> Optional[float]:
        if len(self.stamps) < 2:
            return None
        dt = self.stamps[-1] - self.stamps[0]
        if dt <= 1e-6:
            return None
        return (len(self.stamps) - 1) / dt

    @property
    def age_ms(self) -> Optional[float]:
        if self.last_wall <= 0.0:
            return None
        return (time.monotonic() - self.last_wall) * 1000.0


class RosRateProbe:
    """Optional BEST_EFFORT subscriptions for VSLAM / mavros / DDS vision topics."""

    TOPICS = (
        (
            "/visual_slam/tracking/vo_pose_covariance",
            "geometry_msgs/msg/PoseWithCovarianceStamped",
        ),
        ("/visual_slam/tracking/odometry", "nav_msgs/msg/Odometry"),
        ("/mavros/vision_pose/pose_cov", "geometry_msgs/msg/PoseWithCovarianceStamped"),
        ("/mavros/vision_speed/speed_twist", "geometry_msgs/msg/TwistStamped"),
        ("/fmu/in/vehicle_visual_odometry", "px4_msgs/msg/VehicleOdometry"),
    )

    def __init__(self) -> None:
        self.stats: Dict[str, _MsgStats] = {t: _MsgStats() for t, _ in self.TOPICS}
        self._node = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data

        rclpy.init(args=None)
        self._node = rclpy.create_node("vision_fcu_check_ros")

        for topic, type_key in self.TOPICS:
            msg_type = self._resolve_type(type_key)
            if msg_type is None:
                continue
            self._node.create_subscription(
                msg_type,
                topic,
                lambda _msg, t=topic: self.stats[t].hit(),
                qos_profile_sensor_data,
            )

        self._thread = threading.Thread(target=self._spin, name="vision_fcu_check_ros", daemon=True)
        self._thread.start()

    def _spin(self) -> None:
        import rclpy

        while not self._stop.is_set() and rclpy.ok():
            rclpy.spin_once(self._node, timeout_sec=0.05)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._node is not None:
            self._node.destroy_node()
        try:
            import rclpy

            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass

    @staticmethod
    def _resolve_type(type_key: str):
        try:
            if type_key == "geometry_msgs/msg/PoseWithCovarianceStamped":
                from geometry_msgs.msg import PoseWithCovarianceStamped

                return PoseWithCovarianceStamped
            if type_key == "geometry_msgs/msg/TwistStamped":
                from geometry_msgs.msg import TwistStamped

                return TwistStamped
            if type_key == "nav_msgs/msg/Odometry":
                from nav_msgs.msg import Odometry

                return Odometry
            if type_key == "px4_msgs/msg/VehicleOdometry":
                from px4_msgs.msg import VehicleOdometry

                return VehicleOdometry
        except ImportError:
            return None
        return None


class VisionFcuCheck:
    def __init__(
        self,
        connection: str,
        baud: int = 921600,
        heartbeat_timeout: float = 15.0,
        refresh_hz: float = 2.0,
        ros: bool = False,
        expect_hz: Optional[float] = None,
        duration: Optional[float] = None,
    ) -> None:
        self.connection = normalize_connection_string(connection)
        self.baud = baud
        self.heartbeat_timeout = heartbeat_timeout
        self.refresh_period = 1.0 / max(refresh_hz, 0.5)
        self.expect_hz = expect_hz
        self.duration = duration
        self.master: Optional[mavutil.mavfile] = None
        self.stats: Dict[str, _MsgStats] = {name: _MsgStats() for name in _ALL_TYPES}
        self.fcu_name = "?"
        self.sys_id = 0
        self._ros: Optional[RosRateProbe] = RosRateProbe() if ros else None
        self._ok_samples = 0
        self._need_ok = 0
        if expect_hz is not None and duration is not None:
            self._need_ok = max(1, int(duration * refresh_hz * 0.6))

    def connect(self) -> None:
        self.master = mavutil.mavlink_connection(
            self.connection,
            baud=self.baud,
            source_system=255,
            source_component=mavutil.mavlink.MAV_COMP_ID_MISSIONPLANNER,
        )
        deadline = time.monotonic() + self.heartbeat_timeout
        while time.monotonic() < deadline:
            msg = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if msg is None:
                continue
            if msg.type in (
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            ):
                continue
            self.master.target_system = msg.get_srcSystem()
            self.master.target_component = msg.get_srcComponent()
            self.sys_id = self.master.target_system
            ap = _AUTOPILOT_NAMES.get(msg.autopilot, f"autopilot={msg.autopilot}")
            vt = _TYPE_NAMES.get(msg.type, f"type={msg.type}")
            self.fcu_name = f"{ap}/{vt}"
            self.stats["HEARTBEAT"].hit({"autopilot": msg.autopilot, "type": msg.type})
            self._request_streams()
            return
        raise TimeoutError(
            f"No FCU heartbeat within {self.heartbeat_timeout}s on {self.connection}"
        )

    def _request_streams(self) -> None:
        assert self.master is not None
        # Prefer MESSAGE_INTERVAL (Hz → us). Fall back to legacy DATA_STREAM.
        intervals_hz = {
            mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED: 20,
            mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE: 20,
            mavutil.mavlink.MAVLINK_MSG_ID_EKF_STATUS_REPORT: 2,
            mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT: 2,
            mavutil.mavlink.MAVLINK_MSG_ID_VISION_POSITION_ESTIMATE: 0,  # listen only
        }
        for msg_id, hz in intervals_hz.items():
            if hz <= 0:
                continue
            try:
                self.master.mav.command_long_send(
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                    0,
                    float(msg_id),
                    1e6 / float(hz),
                    0,
                    0,
                    0,
                    0,
                    0,
                )
            except Exception:
                pass
        try:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                20,
                1,
            )
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
                10,
                1,
            )
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                20,
                1,
            )
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
                2,
                1,
            )
        except Exception:
            pass

    def _drain(self) -> None:
        assert self.master is not None
        while True:
            msg = self.master.recv_match(type=list(_ALL_TYPES), blocking=False)
            if msg is None:
                break
            name = msg.get_type()
            if name == "VISION_POSITION_ESTIMATE":
                yaw = float(getattr(msg, "yaw", 0.0))
                self.stats[name].hit(
                    {
                        "x": float(msg.x),
                        "y": float(msg.y),
                        "z": float(msg.z),
                        "yaw_deg": math.degrees(yaw),
                    }
                )
            elif name == "VISION_SPEED_ESTIMATE":
                self.stats[name].hit({"vx": float(msg.x), "vy": float(msg.y), "vz": float(msg.z)})
            elif name == "LOCAL_POSITION_NED":
                self.stats[name].hit({"x": float(msg.x), "y": float(msg.y), "z": float(msg.z)})
            elif name == "ATTITUDE":
                self.stats[name].hit(
                    {
                        "roll": math.degrees(float(msg.roll)),
                        "pitch": math.degrees(float(msg.pitch)),
                        "yaw": math.degrees(float(msg.yaw)),
                    }
                )
            elif name == "EKF_STATUS_REPORT":
                flags = int(msg.flags)
                horiz = "OK" if (flags & (_EKF_POS_HORIZ_ABS | _EKF_POS_HORIZ_REL)) else "NO"
                self.stats[name].hit({"flags": flags, "pos_horiz": horiz})
            elif name == "GPS_RAW_INT":
                self.stats[name].hit(
                    {
                        "fix": int(msg.fix_type),
                        "sats": int(getattr(msg, "satellites_visible", 0) or 0),
                    }
                )
            elif name == "HEARTBEAT":
                if msg.type not in (
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                ):
                    self.stats[name].hit()

    @staticmethod
    def _fmt_hz(hz: Optional[float]) -> str:
        if hz is None:
            return "  -- Hz"
        return f"{hz:5.1f} Hz"

    @staticmethod
    def _fmt_age(age: Optional[float]) -> str:
        if age is None:
            return "age   -- ms"
        return f"age {age:5.0f} ms"

    def _line_wire_pose(self) -> str:
        s = self.stats["VISION_POSITION_ESTIMATE"]
        if s.last_payload is None:
            return (
                f"  VISION_POSITION_ESTIMATE   {self._fmt_hz(None)}  "
                f"{self._fmt_age(None)}  (none on this link)"
            )
        p = s.last_payload
        return (
            f"  VISION_POSITION_ESTIMATE   {self._fmt_hz(s.hz)}  {self._fmt_age(s.age_ms)}  "
            f"xyz {p['x']:7.3f} {p['y']:7.3f} {p['z']:7.3f}  yaw {p['yaw_deg']:6.1f} deg"
        )

    def _line_wire_speed(self) -> str:
        s = self.stats["VISION_SPEED_ESTIMATE"]
        if s.last_payload is None:
            return f"  VISION_SPEED_ESTIMATE       {self._fmt_hz(None)}  (none)"
        p = s.last_payload
        return (
            f"  VISION_SPEED_ESTIMATE       {self._fmt_hz(s.hz)}  {self._fmt_age(s.age_ms)}  "
            f"v {p['vx']:6.2f} {p['vy']:6.2f} {p['vz']:6.2f}"
        )

    def _line_local(self) -> str:
        s = self.stats["LOCAL_POSITION_NED"]
        if s.last_payload is None:
            return f"  LOCAL_POSITION_NED         {self._fmt_hz(None)}  {self._fmt_age(None)}"
        p = s.last_payload
        return (
            f"  LOCAL_POSITION_NED         {self._fmt_hz(s.hz)}  {self._fmt_age(s.age_ms)}  "
            f"ned {p['x']:7.3f} {p['y']:7.3f} {p['z']:7.3f}"
        )

    def _line_attitude(self) -> str:
        s = self.stats["ATTITUDE"]
        if s.last_payload is None:
            return f"  ATTITUDE                   {self._fmt_hz(None)}"
        p = s.last_payload
        return (
            f"  ATTITUDE                   {self._fmt_hz(s.hz)}  {self._fmt_age(s.age_ms)}  "
            f"rpy {p['roll']:6.1f} {p['pitch']:6.1f} {p['yaw']:6.1f} deg"
        )

    def _line_ekf(self) -> str:
        s = self.stats["EKF_STATUS_REPORT"]
        if s.last_payload is None:
            return "  EKF_STATUS_REPORT          (none yet)"
        p = s.last_payload
        return (
            f"  EKF_STATUS_REPORT          flags=0x{p['flags']:x}  pos_horiz={p['pos_horiz']}  "
            f"{self._fmt_hz(s.hz)}"
        )

    def _line_gps(self) -> str:
        s = self.stats["GPS_RAW_INT"]
        if s.last_payload is None:
            return "  GPS_RAW_INT                (none yet)"
        p = s.last_payload
        note = "(ok indoor)" if p["fix"] == 0 else "(GPS active)"
        return (
            f"  GPS_RAW_INT                fix={p['fix']}  sats={p['sats']}  {note}  "
            f"{self._fmt_hz(s.hz)}"
        )

    def _summary(self) -> Tuple[str, bool]:
        local = self.stats["LOCAL_POSITION_NED"]
        vpe = self.stats["VISION_POSITION_ESTIMATE"]
        gps = self.stats["GPS_RAW_INT"]

        fused_ok = (
            local.hz is not None
            and local.hz >= (self.expect_hz or 2.0)
            and (local.age_ms is None or local.age_ms < 500.0)
        )
        # Without --expect-hz, still require some fused pose for OK.
        if self.expect_hz is None:
            fused_ok = local.last_payload is not None and (
                local.age_ms is None or local.age_ms < 1000.0
            )

        wire = "OK" if vpe.last_payload is not None else "MISSING_ON_LINK"
        gps_idle = "OK"
        if gps.last_payload is not None and gps.last_payload["fix"] >= 2:
            gps_idle = "GPS_FIX"

        fused_s = "OK" if fused_ok else "STALE"
        line = f"SUMMARY  fused_pose={fused_s}  vision_wire={wire}  gps_idle={gps_idle}"
        return line, fused_ok

    def render(self) -> str:
        lines = [
            f"Vision FCU check  link={self.connection}  fcu={self.fcu_name}  sys={self.sys_id}",
            "WIRE (on this link, if present)",
            self._line_wire_pose(),
            self._line_wire_speed(),
            "FUSED",
            self._line_local(),
            self._line_attitude(),
            self._line_ekf(),
            "GPS",
            self._line_gps(),
        ]
        if self._ros is not None:
            lines.append("ROS (--ros)")
            for topic, _ in RosRateProbe.TOPICS:
                s = self._ros.stats[topic]
                short = topic.replace("/visual_slam/tracking/", ".../")
                if s.last_wall <= 0.0:
                    lines.append(f"  {short:<42}  -- Hz")
                else:
                    lines.append(f"  {short:<42}  {self._fmt_hz(s.hz)}  {self._fmt_age(s.age_ms)}")
        summary, _ = self._summary()
        lines.append(summary)
        return "\n".join(lines)

    def run(self) -> int:
        self.connect()
        if self._ros is not None:
            self._ros.start()

        deadline = time.monotonic() + self.duration if self.duration is not None else None
        exit_code = 0
        try:
            while True:
                self._drain()
                text = self.render()
                # Live dashboard when interactive; plain print for --duration smoke.
                if self.duration is None and sys.stdout.isatty():
                    sys.stdout.write("\033[2J\033[H")
                print(text, flush=True)
                if self.duration is None and sys.stdout.isatty():
                    print("\nCtrl+C to exit", flush=True)

                _, fused_ok = self._summary()
                if self.expect_hz is not None:
                    if fused_ok:
                        self._ok_samples += 1
                    if deadline is not None and time.monotonic() >= deadline:
                        exit_code = 0 if self._ok_samples >= self._need_ok else 1
                        if exit_code != 0:
                            print(
                                f"\nFAIL: fused LOCAL_POSITION_NED below "
                                f"{self.expect_hz} Hz (ok_samples={self._ok_samples}/"
                                f"{self._need_ok})",
                                file=sys.stderr,
                            )
                        else:
                            print(
                                f"\nOK: fused pose held ≥{self.expect_hz} Hz "
                                f"({self._ok_samples} samples)",
                                file=sys.stderr,
                            )
                        break
                elif deadline is not None and time.monotonic() >= deadline:
                    break

                time.sleep(self.refresh_period)
        except KeyboardInterrupt:
            print("\nstopped", file=sys.stderr)
        finally:
            if self._ros is not None:
                self._ros.stop()
            if self.master is not None:
                try:
                    self.master.close()
                except Exception:
                    pass
        return exit_code


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Monitor FCU fused vision state (LOCAL_POSITION_NED) and optionally "
            "ROS vision topics. VISION_* on the wire is best-effort."
        )
    )
    p.add_argument(
        "--connection",
        "-c",
        default="udp:0.0.0.0:14550",
        help="MAVLink endpoint (default udp:0.0.0.0:14550). "
        "ArduPilot SITL: tcp:127.0.0.1:5762 if MAVROS owns 5760; else 5760. "
        "PX4 SITL: udp:0.0.0.0:14540.",
    )
    p.add_argument("--baud", type=int, default=921600, help="Serial baud (ignored for UDP/TCP)")
    p.add_argument(
        "--heartbeat-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for first FCU heartbeat",
    )
    p.add_argument("--refresh-hz", type=float, default=2.0, help="Dashboard refresh rate")
    p.add_argument(
        "--ros",
        action="store_true",
        help="Also show VSLAM / mavros / DDS vision topic rates (shared ROS_DOMAIN_ID)",
    )
    p.add_argument(
        "--expect-hz",
        type=float,
        default=None,
        help="Require fused LOCAL_POSITION_NED at least this Hz (with --duration)",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Run for N seconds then exit (use with --expect-hz for smoke tests)",
    )
    return p.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = _parse_args(argv)
    if args.expect_hz is not None and args.duration is None:
        print("--expect-hz requires --duration", file=sys.stderr)
        return 2
    check = VisionFcuCheck(
        connection=args.connection,
        baud=args.baud,
        heartbeat_timeout=args.heartbeat_timeout,
        refresh_hz=args.refresh_hz,
        ros=args.ros,
        expect_hz=args.expect_hz,
        duration=args.duration,
    )
    try:
        return check.run()
    except TimeoutError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
