# @loc:boilerplate:begin
#!/usr/bin/env python3
import math
import time

from pymavlink import mavutil

_M = mavutil.mavlink
_POSITION_MASK = (
    _M.POSITION_TARGET_TYPEMASK_VX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
)


def enu_to_ned(x: float, y: float, z: float):
    return y, x, -z


def ned_to_enu(n: float, e: float, d: float):
    return e, n, -d


class MavlinkPilot:
    def __init__(self, connection_string: str = "udp:127.0.0.1:14550") -> None:
        self.master = mavutil.mavlink_connection(connection_string, autoreconnect=True)
        self.master.wait_heartbeat()
        self._local = None
        self._yaw_ned = 0.0
        self._request_streams()

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

    def _spin(self, timeout: float = 0.5):
        """Drain the link; LOCAL_POSITION_NED has no yaw — attitude carries it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self.master.recv_match(
                blocking=True, timeout=max(0.0, deadline - time.time())
            )
            if msg is None:
                break
            t = msg.get_type()
            if t == "LOCAL_POSITION_NED":
                self._local = msg
            elif t == "ATTITUDE":
                self._yaw_ned = float(msg.yaw)
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
            msg = self._spin()
            if msg is not None and -msg.z >= altitude - 0.3:
                return
        raise TimeoutError("takeoff settle")

    def move_body(
        self, forward: float, left: float, up: float, precision: float = 0.3
    ) -> None:
        msg = self._spin(timeout=2.0)
        if msg is None:
            raise RuntimeError("no LOCAL_POSITION_NED")
        x, y, z = ned_to_enu(msg.x, msg.y, msg.z)
        yaw_enu = math.pi / 2.0 - self._yaw_ned
        c, s = math.cos(yaw_enu), math.sin(yaw_enu)
        tx = x + forward * c - left * s
        ty = y + forward * s + left * c
        tz = z + up
        n, e, d = enu_to_ned(tx, ty, tz)
        yaw_ned = self._yaw_ned
        deadline = time.time() + 60.0
        while time.time() < deadline:
            self.master.mav.set_position_target_local_ned_send(
                0,
                self.master.target_system,
                self.master.target_component,
                _M.MAV_FRAME_LOCAL_NED,
                _POSITION_MASK,
                n,
                e,
                d,
                0,
                0,
                0,
                0,
                0,
                0,
                yaw_ned,
                0,
            )
            msg = self._spin(timeout=0.2)
            if msg is None:
                continue
            cx, cy, cz = ned_to_enu(msg.x, msg.y, msg.z)
            if math.sqrt((cx - tx) ** 2 + (cy - ty) ** 2 + (cz - tz) ** 2) <= precision:
                return
        raise TimeoutError("position settle")

    def land(self) -> None:
        self.set_mode("LAND")


def main() -> None:
    pilot = MavlinkPilot("udp:127.0.0.1:14550")
    pilot.set_mode("GUIDED")
    pilot.arm()
    time.sleep(1.0)
    # @loc:boilerplate:end
    # @loc:core:begin
    pilot.takeoff(2.0)
    pilot.move_body(forward=5.0, left=0.0, up=0.0, precision=0.3)
    pilot.land()


# @loc:core:end
# @loc:boilerplate:begin
if __name__ == "__main__":
    main()
# @loc:boilerplate:end
