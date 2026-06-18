"""Native PX4 transport over the uXRCE-DDS bridge (px4_msgs).

Implements :class:`~nectar.control.vehicle.transport.VehicleTransport` directly
against PX4 uORB topics exposed by the `uXRCE-DDS client
<https://docs.px4.io/main/en/ros2/user_guide.html>`_:

- Telemetry on ``/fmu/out/*`` (``VehicleLocalPosition``, ``VehicleStatus``,
  ``VehicleGlobalPosition``, ``VehicleAttitude``), subscribed with the
  ``sensor_data`` QoS PX4 requires.
- Commands via ``/fmu/in/vehicle_command`` (``VehicleCommand``).
- Setpoints via ``/fmu/in/offboard_control_mode`` (``OffboardControlMode``)
  paired with ``/fmu/in/trajectory_setpoint`` (``TrajectorySetpoint*``).

PX4 uses NED/FRD on the wire; the vehicle core uses ENU/FLU, so this transport
converts on egress/ingest (the same job MAVROS does internally for the MAVROS
path).

Requires ``px4_msgs`` in the workspace and a running ``MicroXRCEAgent``.

See Also
--------
https://docs.px4.io/main/en/ros2/user_guide.html
https://docs.px4.io/main/en/ros2/offboard_control.html
"""

from __future__ import annotations

import math
from typing import Optional, Union

from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

from nectar.control.px4.modes import MODE_TO_PX4
from nectar.control.vehicle.transport import VehicleTransport
from nectar.control.vehicle.types import (
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    TargetFrame,
    Vec3,
    VehicleState,
)

try:
    from px4_msgs.msg import (
        OffboardControlMode,
        TrajectorySetpoint,
        VehicleCommand,
        VehicleGlobalPosition,
        VehicleLocalPosition,
        VehicleStatus,
    )

    _PX4_MSGS_AVAILABLE = True
except ImportError:  # px4_msgs not built into the workspace
    _PX4_MSGS_AVAILABLE = False

# PX4 nav_state -> readable mode name (subset used by the SDK).
# Source: px4_msgs VehicleStatus NAVIGATION_STATE_* constants.
_NAV_STATE_TO_MODE = {
    4: "AUTO.LOITER",
    5: "AUTO.RTL",
    14: "OFFBOARD",
    17: "AUTO.TAKEOFF",
    18: "AUTO.LAND",
}

_ARMING_STATE_ARMED = 2


def px4_msgs_available() -> bool:
    """True when ``px4_msgs`` is importable in this workspace."""
    return _PX4_MSGS_AVAILABLE


class Px4DdsTransport(VehicleTransport):
    """PX4 transport over uXRCE-DDS (px4_msgs)."""

    def __init__(self) -> None:
        if not _PX4_MSGS_AVAILABLE:
            raise RuntimeError(
                "px4_msgs is not available. Clone PX4/px4_msgs (version-matched to your "
                "PX4 firmware) into the workspace, build it, and run a MicroXRCEAgent. "
                "See nectar/nectar/control/px4/README.md."
            )
        self._drone = None
        self._config = None

        self._vehicle_state = VehicleState()
        self._local_plain: Optional[LocalPose] = None
        self._gps_plain: Optional[GeoPoint] = None
        self._heading_val: Optional[float] = None
        self._rel_alt_val: Optional[float] = None
        self._range_val: Optional[float] = None
        self._connected = False

        self._offboard_pub = None
        self._setpoint_pub = None
        self._command_pub = None

    # Lifecycle

    def attach(self, drone) -> None:
        super().attach(drone)
        self._config = drone.config

    def start(self) -> None:
        cfg = self._config
        ns = getattr(cfg, "px4_namespace", "")
        drone = self._drone

        # /fmu/out topic names are version-dependent (PX4 versions some uORB
        # topics, e.g. vehicle_local_position_v1 / vehicle_status_v4). Read them
        # from config so they can be matched to the running firmware/px4_msgs.
        local_topic = getattr(cfg, "local_position_topic", "/fmu/out/vehicle_local_position_v1")
        status_topic = getattr(cfg, "status_topic", "/fmu/out/vehicle_status_v4")
        global_topic = getattr(cfg, "global_position_topic", "/fmu/out/vehicle_global_position")

        # PX4 publishers (/fmu/out/*) require BEST_EFFORT, KEEP_LAST sensor QoS.
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        drone._create_subscriber(
            VehicleLocalPosition, f"{ns}{local_topic}", self._on_local, sensor_qos
        )
        drone._create_subscriber(VehicleStatus, f"{ns}{status_topic}", self._on_status, sensor_qos)
        drone._create_subscriber(
            VehicleGlobalPosition, f"{ns}{global_topic}", self._on_global, sensor_qos
        )

        self._offboard_pub = drone._create_publisher(
            OffboardControlMode, f"{ns}/fmu/in/offboard_control_mode", 10
        )
        self._setpoint_pub = drone._create_publisher(
            TrajectorySetpoint, f"{ns}/fmu/in/trajectory_setpoint", 10
        )
        self._command_pub = drone._create_publisher(
            VehicleCommand, f"{ns}/fmu/in/vehicle_command", 10
        )

    def close(self) -> None:
        # ROS entities are created via BaseDrone helpers and torn down there.
        pass

    @property
    def _node(self):
        return self._drone.node

    def _now_us(self) -> int:
        return self._node.get_clock().now().nanoseconds // 1000

    # Frame helpers (PX4 NED/FRD <-> core ENU/FLU)

    @staticmethod
    def _enu_to_ned(x: float, y: float, z: float) -> tuple:
        # ENU (East, North, Up) -> NED (North, East, Down)
        return (y, x, -z)

    @staticmethod
    def _ned_to_enu(x: float, y: float, z: float) -> tuple:
        # NED (North, East, Down) -> ENU (East, North, Up)
        return (y, x, -z)

    @staticmethod
    def _yaw_enu_to_ned(yaw_enu: float) -> float:
        # ENU yaw (0=East, CCW) -> NED yaw (0=North, CW)
        return math.pi / 2.0 - yaw_enu

    @staticmethod
    def _yaw_ned_to_enu(yaw_ned: float) -> float:
        return math.pi / 2.0 - yaw_ned

    # Subscriber callbacks

    def _on_local(self, msg) -> None:
        ex, ey, ez = self._ned_to_enu(msg.x, msg.y, msg.z)
        self._local_plain = LocalPose(
            position=Vec3(ex, ey, ez),
            yaw=self._yaw_ned_to_enu(msg.heading),
        )
        self._rel_alt_val = -float(msg.z)
        # Compass heading in degrees (NED, 0=North).
        self._heading_val = math.degrees(msg.heading) % 360.0
        if getattr(msg, "dist_bottom_valid", False):
            self._range_val = float(msg.dist_bottom)
        self._connected = True

    def _on_status(self, msg) -> None:
        mode = _NAV_STATE_TO_MODE.get(int(msg.nav_state), str(msg.nav_state))
        self._vehicle_state = VehicleState(
            connected=True,
            armed=int(msg.arming_state) == _ARMING_STATE_ARMED,
            guided=int(msg.nav_state) == 14,
            mode=mode,
            system_status=int(msg.arming_state),
        )
        self._connected = True

    def _on_global(self, msg) -> None:
        self._gps_plain = GeoPoint(
            latitude=float(msg.lat),
            longitude=float(msg.lon),
            altitude=float(msg.alt),
        )

    # Telemetry

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> VehicleState:
        return self._vehicle_state

    @property
    def local_pose(self) -> Optional[LocalPose]:
        return self._local_plain

    @property
    def vision_pose(self) -> Optional[LocalPose]:
        # PX4's EKF2 fuses external vision; the SDK reads the fused local pose.
        return self._local_plain

    @property
    def gps(self) -> Optional[GeoPoint]:
        return self._gps_plain

    @property
    def heading(self) -> Optional[float]:
        return self._heading_val

    @property
    def rel_alt(self) -> Optional[float]:
        return self._rel_alt_val

    @property
    def rangefinder(self) -> Optional[float]:
        return self._range_val

    # Driver lifecycle (the uXRCE-DDS agent is the "driver")

    def driver_name(self) -> str:
        return "MicroXRCEAgent"

    def driver_command(self) -> str:
        port = getattr(self._config, "agent_port", 8888)
        return f"MicroXRCEAgent udp4 -p {port}"

    def start_driver(self) -> bool:
        from nectar.utils.process import ProcessUtils

        name = self.driver_name()
        if ProcessUtils.is_node_running(name, timeout=2.0):
            return True
        return ProcessUtils.start_process(self.driver_command(), name)

    # Commands (VehicleCommand)

    def _send_command(self, command: int, **params) -> bool:
        msg = VehicleCommand()
        msg.command = int(command)
        for i in range(1, 8):
            setattr(msg, f"param{i}", float(params.get(f"param{i}", 0.0)))
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.timestamp = self._now_us()
        self._command_pub.publish(msg)
        return True

    def set_mode(self, mode: str) -> bool:
        main_sub = MODE_TO_PX4.get(mode.upper())
        if main_sub is None:
            self._node.get_logger().error(f"Unknown PX4 mode: {mode}")
            return False
        main_mode, sub_mode = main_sub
        # VEHICLE_CMD_DO_SET_MODE (176): param1=1 (custom), param2=main, param3=sub.
        return self._send_command(176, param1=1.0, param2=float(main_mode), param3=float(sub_mode))

    def arm(self) -> bool:
        # VEHICLE_CMD_COMPONENT_ARM_DISARM (400): param1=1 arm.
        return self._send_command(400, param1=1.0)

    def disarm(self, force: bool = True) -> bool:
        return self._send_command(400, param1=0.0, param2=21196.0 if force else 0.0)

    def command_takeoff(self, altitude: float) -> bool:
        # VEHICLE_CMD_NAV_TAKEOFF (22); param7 = altitude (AMSL). Fallback only —
        # Px4Drone takes off via an offboard climb setpoint.
        return self._send_command(22, param7=float(altitude))

    def command_land(self) -> bool:
        # VEHICLE_CMD_NAV_LAND (21). Px4Drone uses AUTO.LAND mode instead.
        return self._send_command(21)

    def set_home(self, current: bool = True) -> bool:
        # VEHICLE_CMD_DO_SET_HOME (179): param1=1 uses the current position.
        return self._send_command(179, param1=1.0 if current else 0.0)

    def set_param(self, name: str, value: Union[int, float]) -> bool:
        # PX4 parameters are not bridged as a uXRCE-DDS service by default.
        self._node.get_logger().warn(
            f"set_param({name}) is not supported over uXRCE-DDS; set it via QGC or the MAVROS path."
        )
        return False

    def send_command_long(self, command: int, *params: float) -> bool:
        kwargs = {f"param{i + 1}": v for i, v in enumerate(params[:7])}
        return self._send_command(command, **kwargs)

    # Setpoints (OffboardControlMode + TrajectorySetpoint)

    def _publish_offboard_mode(self, *, position: bool, velocity: bool) -> None:
        msg = OffboardControlMode()
        msg.position = position
        msg.velocity = velocity
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        msg.timestamp = self._now_us()
        self._offboard_pub.publish(msg)

    def send_velocity_target(
        self,
        vx: float,
        vy: float,
        vz: float,
        yaw_rate: float,
        frame: TargetFrame,
    ) -> None:
        # Resolve a world-ENU velocity, then convert to NED.
        if frame == TargetFrame.BODY:
            yaw = self._local_plain.yaw if self._local_plain is not None else 0.0
            cos_y, sin_y = math.cos(yaw), math.sin(yaw)
            # FLU body (vx fwd, vy left) -> world ENU
            ve = vx * cos_y - vy * sin_y
            vn = vx * sin_y + vy * cos_y
            vu = vz
        else:
            ve, vn, vu = vx, vy, vz
        nx, ny, nz = self._enu_to_ned(ve, vn, vu)

        self._publish_offboard_mode(position=False, velocity=True)
        sp = TrajectorySetpoint()
        sp.position = [float("nan"), float("nan"), float("nan")]
        sp.velocity = [float(nx), float(ny), float(nz)]
        sp.yaw = float("nan")
        sp.yawspeed = float(-yaw_rate)  # NED yaw is CW positive
        sp.timestamp = self._now_us()
        self._setpoint_pub.publish(sp)

    def send_local_target(self, target: LocalTarget) -> None:
        nx, ny, nz = self._enu_to_ned(target.position.x, target.position.y, target.position.z)
        self._publish_offboard_mode(position=True, velocity=False)
        sp = TrajectorySetpoint()
        sp.position = [float(nx), float(ny), float(nz)]
        sp.velocity = [float("nan"), float("nan"), float("nan")]
        sp.yaw = float(self._yaw_enu_to_ned(target.yaw))
        sp.yawspeed = float("nan")
        sp.timestamp = self._now_us()
        self._setpoint_pub.publish(sp)

    def send_global_target(self, target: GlobalTarget) -> None:
        # PX4 offboard TrajectorySetpoint is local-frame only; global setpoints
        # are not supported on the native path. Use PID/PID_EKF or the MAVROS path.
        self._node.get_logger().warn(
            "Global setpoints are not supported over the native PX4 (uXRCE-DDS) "
            "path; use a PID navigation method or the MAVROS transport."
        )
