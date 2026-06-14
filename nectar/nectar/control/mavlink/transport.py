"""Direct-pymavlink transport for :class:`ArduPilotDrone`.

* **RX** — a ROS timer on the drone's node drains ``recv_match(blocking=False)``
  and decodes MAVLink messages into plain telemetry types. This keeps the
  concurrency model identical to MAVROS: telemetry is updated on the executor
  thread, blocking flight calls read it on the user thread (atomic whole-object
  reads), per :mod:`nectar.runtime`.
* **TX** — commands/setpoints are sent directly via ``master.mav.*_send``,
  serialized through the connection's :attr:`~MavlinkConnection.send_lock`
  (single reader, many senders). A 1 Hz heartbeat timer announces the companion.

Frame conventions: the core speaks ENU/FLU (see
:mod:`nectar.control.ardupilot.types`); this transport converts to the wire's
NED/FRD on egress and back to ENU on ingest, exactly as MAVROS does internally.
"""

from __future__ import annotations

import math
import time
from typing import Dict, Optional, Union

from pymavlink import mavutil

from nectar.control.ardupilot.transport import MavlinkTransport
from nectar.control.ardupilot.types import (
    Attitude,
    DistanceReading,
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    SensorOrientation,
    TargetFrame,
    Vec3,
    VehicleState,
)
from nectar.control.mavlink.connection import MavlinkConnection
from nectar.control.mavlink.streams import request_message_intervals
from nectar.control.types import PoseSource
from nectar.utils.log import OK

_M = mavutil.mavlink

# Bitmask: velocity + yaw-rate active (position/accel/yaw ignored).
_VELOCITY_MASK = (
    _M.POSITION_TARGET_TYPEMASK_X_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Y_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_Z_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_IGNORE
)

# Bitmask: position + yaw active (velocity/accel/yaw-rate ignored).
_POSITION_MASK = (
    _M.POSITION_TARGET_TYPEMASK_VX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_VZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AX_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AY_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_AZ_IGNORE
    | _M.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
)


def _normalize_angle(angle: float) -> float:
    """Wrap a radian angle to ``(-pi, pi]``."""
    return math.atan2(math.sin(angle), math.cos(angle))


def _ned_yaw_to_enu(yaw_ned: float) -> float:
    """Convert a NED yaw (0=North, CW) to ENU yaw (0=East, CCW)."""
    return _normalize_angle(math.pi / 2.0 - yaw_ned)


def _enu_yaw_to_ned(yaw_enu: float) -> float:
    """Convert an ENU yaw (0=East, CCW) to NED yaw (0=North, CW)."""
    return _normalize_angle(math.pi / 2.0 - yaw_enu)


class PymavlinkTransport(MavlinkTransport):
    """Transport that talks MAVLink directly over a :class:`MavlinkConnection`.

    Parameters
    ----------
    connection : MavlinkConnection, optional
        Pre-built endpoint to share (e.g. with a rangefinder publisher). When
        ``None``, one is created from the drone config in :meth:`attach`.
    """

    def __init__(self, connection: Optional[MavlinkConnection] = None) -> None:
        self._drone = None
        self._config = None
        self._pose_source = PoseSource.GPS
        self._connection = connection
        self._owns_connection = connection is None

        self._rx_timer = None
        self._hb_timer = None
        self._vision_bridge = None
        self._link_timeout = 3.0
        self._last_heartbeat = 0.0

        # Plain telemetry
        self._vehicle_state = VehicleState()
        self._local_pos_enu: Optional[Vec3] = None
        self._yaw_enu: float = 0.0
        self._attitude: Optional[Attitude] = None
        self._vision_plain: Optional[LocalPose] = None

        self._gps_lat: Optional[float] = None
        self._gps_lon: Optional[float] = None
        self._gps_amsl: float = 0.0
        self._gps_ellipsoid: Optional[float] = None
        self._heading_val: Optional[float] = None
        self._rel_alt_val: Optional[float] = None
        self._range_val: Optional[float] = None
        self._distances: Dict[int, DistanceReading] = {}

        # Command bookkeeping (populated by the RX path).
        self._params: Dict[str, float] = {}
        self._acks: Dict[int, int] = {}
        self._last_statustext: Optional[str] = None

    # Lifecycle

    def attach(self, drone) -> None:
        super().attach(drone)
        self._config = drone.config
        self._pose_source = drone.config.pose_source

        if self._connection is None:
            self._connection = MavlinkConnection(
                source_system=getattr(self._config, "source_system", 1),
                source_component=getattr(
                    self._config, "source_component", _M.MAV_COMP_ID_ONBOARD_COMPUTER
                ),
                heartbeat_timeout=getattr(self._config, "heartbeat_timeout", 30.0),
            )

    def start(self) -> None:
        config = self._config

        if not self._connection.is_connected:
            self._node.get_logger().info(f"Connecting MAVLink: {config.connection_string}")
            self._connection.connect(config.connection_string, getattr(config, "baud", 921600))
            self._node.get_logger().info("MAVLink heartbeat handshake complete")

        request_message_intervals(self._connection, getattr(config, "stream_rates", None))

        rx_period = 1.0 / getattr(config, "rx_rate_hz", 100.0)
        hb_period = 1.0 / getattr(config, "heartbeat_hz", 1.0)
        group = self._drone._callback_group
        self._rx_timer = self._node.create_timer(rx_period, self._drain_rx, callback_group=group)
        self._hb_timer = self._node.create_timer(
            hb_period, self._send_heartbeat, callback_group=group
        )

        # Indoor: feed the EKF external nav (companion VSLAM pose -> FCU), since
        # there is no MAVROS doing it. Started before the drone waits on sensors.
        if self._pose_source == PoseSource.VISION:
            from nectar.control.mavlink.vision_bridge import VisionPoseBridge

            self._vision_bridge = VisionPoseBridge(
                self._node,
                self._connection,
                getattr(config, "vision_pose_topic", "/visual_slam/tracking/vo_pose_covariance"),
                on_pose=self.update_vision_pose,
            )
            self._vision_bridge.start()

    def close(self) -> None:
        if self._vision_bridge is not None:
            self._vision_bridge.stop()
            self._vision_bridge = None
        for timer in (self._rx_timer, self._hb_timer):
            if timer is not None:
                try:
                    self._node.destroy_timer(timer)
                except Exception:
                    pass
        self._rx_timer = None
        self._hb_timer = None
        if self._owns_connection and self._connection is not None:
            self._connection.close()

    @property
    def _node(self):
        return self._drone.node

    @property
    def connection(self) -> MavlinkConnection:
        """The underlying endpoint (shareable with sensor publishers)."""
        return self._connection

    # RX path (executor thread)

    def _drain_rx(self) -> None:
        """Decode all MAVLink messages queued since the last tick."""
        master = self._connection.master
        if master is None:
            return
        for _ in range(200):
            msg = master.recv_match(blocking=False)
            if msg is None:
                return
            handler = self._HANDLERS.get(msg.get_type())
            if handler is not None:
                handler(self, msg)

    def _on_heartbeat(self, msg) -> None:
        if msg.type in (_M.MAV_TYPE_GCS, _M.MAV_TYPE_ONBOARD_CONTROLLER):
            return
        self._last_heartbeat = time.monotonic()
        armed = bool(msg.base_mode & _M.MAV_MODE_FLAG_SAFETY_ARMED)
        mode = mavutil.mode_string_v10(msg)
        self._vehicle_state = VehicleState(
            connected=True,
            armed=armed,
            guided=(mode == "GUIDED"),
            mode=mode,
            system_status=msg.system_status,
        )

    def _on_global_position_int(self, msg) -> None:
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        amsl = msg.alt / 1000.0
        self._gps_lat = lat
        self._gps_lon = lon
        self._gps_amsl = amsl
        # Report WGS84 ellipsoid height (AMSL + geoid undulation), matching
        # MAVROS /global_position/global. The core's GPS setpoint path subtracts
        # the same undulation to recover AMSL; the FCU's GPS_RAW_INT.alt_ellipsoid
        # is unreliable in SITL (set equal to AMSL), so derive it here instead.
        self._gps_ellipsoid = amsl + self._geoid_separation(lat, lon)
        self._rel_alt_val = msg.relative_alt / 1000.0
        if msg.hdg != 65535:
            self._heading_val = msg.hdg / 100.0

    def _geoid_separation(self, lat: float, lon: float) -> float:
        """EGM96 geoid undulation N such that ellipsoid = AMSL + N."""
        from nectar.control.ardupilot.gps_utils import GPSUtils

        try:
            return GPSUtils.geoid_height(lat, lon)
        except Exception:
            return 0.0

    def _on_local_position_ned(self, msg) -> None:
        # NED -> ENU: East=y, North=x, Up=-z.
        self._local_pos_enu = Vec3(x=msg.y, y=msg.x, z=-msg.z)

    def _on_attitude(self, msg) -> None:
        self._yaw_enu = _ned_yaw_to_enu(msg.yaw)
        self._attitude = Attitude(roll=msg.roll, pitch=-msg.pitch, yaw=self._yaw_enu)

    def _on_rangefinder(self, msg) -> None:
        self._range_val = float(msg.distance)

    def _on_distance_sensor(self, msg) -> None:
        orientation = SensorOrientation.from_mavlink(msg.orientation)
        reading = DistanceReading(
            distance=msg.current_distance / 100.0,
            orientation=orientation,
            min_distance=msg.min_distance / 100.0,
            max_distance=msg.max_distance / 100.0,
            sensor_id=msg.id,
            sensor_type=msg.type,
            signal_quality=(getattr(msg, "signal_quality", 0) or None),
            raw_orientation=msg.orientation,
            timestamp=time.monotonic(),
        )
        # Copy-on-write so user-thread reads always see a consistent snapshot.
        self._distances = {**self._distances, msg.id: reading}
        # The downward sensor is the height-above-ground source for altitude.
        if orientation == SensorOrientation.DOWN:
            self._range_val = reading.distance

    def _on_param_value(self, msg) -> None:
        name = msg.param_id
        if isinstance(name, bytes):
            name = name.decode("ascii", "ignore")
        self._params[name.rstrip("\x00")] = msg.param_value

    def _on_command_ack(self, msg) -> None:
        self._acks[msg.command] = msg.result

    def _on_statustext(self, msg) -> None:
        """Surface FCU text (e.g. ``PreArm: ...`` reasons) on the ROS logger."""
        text = msg.text
        if isinstance(text, bytes):
            text = text.decode("ascii", "ignore")
        text = text.rstrip("\x00").strip()
        if not text or text == self._last_statustext:
            return
        self._last_statustext = text
        logger = self._node.get_logger()
        if msg.severity <= _M.MAV_SEVERITY_ERROR:
            logger.error(f"FCU: {text}")
        elif msg.severity <= _M.MAV_SEVERITY_WARNING:
            logger.warn(f"FCU: {text}")
        else:
            logger.info(f"FCU: {text}")

    _HANDLERS = {
        "HEARTBEAT": _on_heartbeat,
        "GLOBAL_POSITION_INT": _on_global_position_int,
        "LOCAL_POSITION_NED": _on_local_position_ned,
        "ATTITUDE": _on_attitude,
        "RANGEFINDER": _on_rangefinder,
        "DISTANCE_SENSOR": _on_distance_sensor,
        "PARAM_VALUE": _on_param_value,
        "COMMAND_ACK": _on_command_ack,
        "STATUSTEXT": _on_statustext,
    }

    # TX helpers

    @staticmethod
    def _time_boot_ms() -> int:
        return int(time.monotonic() * 1000) & 0xFFFFFFFF

    def _send_heartbeat(self) -> None:
        master = self._connection.master
        if master is None:
            return
        with self._connection.send_lock:
            master.mav.heartbeat_send(
                _M.MAV_TYPE_ONBOARD_CONTROLLER, _M.MAV_AUTOPILOT_INVALID, 0, 0, 0
            )

    def _command_long(self, command: int, *params: float, want_ack: bool = False) -> bool:
        master = self._connection.master
        values = [float(p) for p in params[:7]]
        values += [0.0] * (7 - len(values))
        if want_ack:
            self._acks.pop(int(command), None)
        with self._connection.send_lock:
            master.mav.command_long_send(
                master.target_system, master.target_component, int(command), 0, *values
            )
        if not want_ack:
            return True
        result = self._poll(lambda: self._acks.get(int(command)), timeout=1.0)
        if result is None:
            return True  # No ACK observed; assume accepted (best-effort).
        return result in (_M.MAV_RESULT_ACCEPTED, _M.MAV_RESULT_IN_PROGRESS)

    def _poll(self, getter, timeout: float, interval: float = 0.02):
        """Poll ``getter()`` until it returns non-None or ``timeout`` elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = getter()
            if value is not None:
                return value
            time.sleep(interval)
        return getter()

    def driver_name(self) -> str:
        return ""

    def driver_command(self) -> str:
        return ""

    def start_driver(self) -> bool:
        return True

    # Telemetry

    @property
    def connected(self) -> bool:
        return (time.monotonic() - self._last_heartbeat) < self._link_timeout

    @property
    def state(self) -> VehicleState:
        s = self._vehicle_state
        return VehicleState(
            connected=self.connected,
            armed=s.armed,
            guided=s.guided,
            mode=s.mode,
            system_status=s.system_status,
        )

    @property
    def local_pose(self) -> Optional[LocalPose]:
        if self._local_pos_enu is None:
            return None
        return LocalPose(position=self._local_pos_enu, yaw=self._yaw_enu)

    @property
    def vision_pose(self) -> Optional[LocalPose]:
        return self._vision_plain

    @property
    def gps(self) -> Optional[GeoPoint]:
        if self._gps_lat is None:
            return None
        altitude = self._gps_ellipsoid if self._gps_ellipsoid is not None else self._gps_amsl
        return GeoPoint(latitude=self._gps_lat, longitude=self._gps_lon, altitude=altitude)

    @property
    def heading(self) -> Optional[float]:
        return self._heading_val

    @property
    def rel_alt(self) -> Optional[float]:
        return self._rel_alt_val

    @property
    def rangefinder(self) -> Optional[float]:
        return self._range_val

    @property
    def distance_sensors(self) -> Dict[int, DistanceReading]:
        return self._distances

    @property
    def attitude(self) -> Optional[Attitude]:
        return self._attitude

    def update_vision_pose(self, pose: Optional[LocalPose]) -> None:
        """Set the external-vision pose (called by :class:`VisionPoseBridge`)."""
        self._vision_plain = pose

    # Commands

    def set_mode(self, mode: str) -> bool:
        master = self._connection.master
        mapping = master.mode_mapping() or {}
        mode_id = mapping.get(mode)
        if mode_id is None:
            self._node.get_logger().error(
                f"Unknown flight mode '{mode}'. Available: {sorted(mapping)}"
            )
            return False
        with self._connection.send_lock:
            master.mav.set_mode_send(
                master.target_system, _M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id
            )
        return True

    def arm(self) -> bool:
        return self._command_long(_M.MAV_CMD_COMPONENT_ARM_DISARM, 1, 0)

    def disarm(self, force: bool = True) -> bool:
        return self._command_long(_M.MAV_CMD_COMPONENT_ARM_DISARM, 0, 21196 if force else 0)

    def command_takeoff(self, altitude: float) -> bool:
        return self._command_long(_M.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, float(altitude))

    def command_land(self) -> bool:
        return self.set_mode("LAND")

    def set_home(self, current: bool = True) -> bool:
        return self._command_long(_M.MAV_CMD_DO_SET_HOME, 1 if current else 0)

    def set_param(self, name: str, value: Union[int, float]) -> bool:
        master = self._connection.master
        self._params.pop(name, None)
        with self._connection.send_lock:
            master.mav.param_set_send(
                master.target_system,
                master.target_component,
                name.encode("ascii"),
                float(value),
                _M.MAV_PARAM_TYPE_REAL32,
            )
        # ArduPilot echoes PARAM_VALUE within a few ms for a known parameter and
        # stays silent for an unknown one, so a short timeout keeps alias probing
        # responsive without false negatives on a fast link.
        echoed = self._poll(lambda: self._params.get(name), timeout=0.5)
        if echoed is None:
            return False
        tolerance = max(1e-4, abs(float(value)) * 1e-3)
        if abs(echoed - float(value)) > tolerance:
            return False
        self._node.get_logger().info(f"{OK} {name} set")
        return True

    def send_command_long(self, command: int, *params: float) -> bool:
        return self._command_long(command, *params, want_ack=True)

    # Setpoints

    def send_velocity_target(
        self,
        vx: float,
        vy: float,
        vz: float,
        yaw_rate: float,
        frame: TargetFrame,
    ) -> None:
        if frame == TargetFrame.LOCAL:
            coordinate_frame = _M.MAV_FRAME_LOCAL_NED
            vn, ve, vd = float(vy), float(vx), -float(vz)  # ENU -> NED
        else:
            coordinate_frame = _M.MAV_FRAME_BODY_NED
            vn, ve, vd = float(vx), -float(vy), -float(vz)  # FLU -> FRD
        yaw_rate_ned = -float(yaw_rate)

        master = self._connection.master
        with self._connection.send_lock:
            master.mav.set_position_target_local_ned_send(
                self._time_boot_ms(),
                master.target_system,
                master.target_component,
                coordinate_frame,
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
                yaw_rate_ned,
            )

    def send_local_target(self, target: LocalTarget) -> None:
        # ENU -> NED position; ENU yaw -> NED yaw.
        x_ned = float(target.position.y)
        y_ned = float(target.position.x)
        z_ned = -float(target.position.z)
        yaw_ned = _enu_yaw_to_ned(target.yaw)

        master = self._connection.master
        with self._connection.send_lock:
            master.mav.set_position_target_local_ned_send(
                self._time_boot_ms(),
                master.target_system,
                master.target_component,
                _M.MAV_FRAME_LOCAL_NED,
                _POSITION_MASK,
                x_ned,
                y_ned,
                z_ned,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                yaw_ned,
                0.0,
            )

    def send_global_target(self, target: GlobalTarget) -> None:
        yaw_ned = _enu_yaw_to_ned(target.yaw)

        master = self._connection.master
        with self._connection.send_lock:
            master.mav.set_position_target_global_int_send(
                self._time_boot_ms(),
                master.target_system,
                master.target_component,
                _M.MAV_FRAME_GLOBAL_INT,
                _POSITION_MASK,
                int(target.latitude * 1e7),
                int(target.longitude * 1e7),
                float(target.altitude),
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                yaw_ned,
                0.0,
            )
