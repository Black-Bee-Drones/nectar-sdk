"""MAVROS transport for :class:`ArduPilotDrone`.

Bridges the transport-agnostic vehicle core to a running ``mavros_node``:
ROS subscriptions populate telemetry, service clients issue commands, and
publishers emit setpoints. Telemetry is converted to plain core types in the
subscriber callbacks.
"""

from typing import Optional, Union

from geographic_msgs.msg import GeoPoseStamped
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from mavros_msgs.msg import GlobalPositionTarget, PositionTarget, State
from mavros_msgs.srv import CommandBool, CommandHome, CommandLong, CommandTOL, SetMode
from rcl_interfaces.msg import Parameter, ParameterType
from rcl_interfaces.srv import SetParameters
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import NavSatFix, Range
from std_msgs.msg import Float64
from tf_transformations import quaternion_from_euler

from nectar.control.ardupilot.transport import MavlinkTransport
from nectar.control.ardupilot.types import (
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    TargetFrame,
    Vec3,
    VehicleState,
)
from nectar.control.types import PoseSource
from nectar.utils.position_utils import PositionUtils
from nectar.utils.process import ProcessUtils

# Bitmask: position + yaw active (velocity/accel/yaw-rate ignored).
_POSITION_MASK = (
    PositionTarget.IGNORE_AFX
    | PositionTarget.IGNORE_AFY
    | PositionTarget.IGNORE_AFZ
    | PositionTarget.IGNORE_YAW_RATE
    | PositionTarget.IGNORE_VX
    | PositionTarget.IGNORE_VY
    | PositionTarget.IGNORE_VZ
)

# Bitmask: velocity + yaw-rate active (position/accel/yaw ignored).
_VELOCITY_MASK = 1479


class MavrosTransport(MavlinkTransport):
    """MAVROS-backed transport for ArduPilot/PX4 flight controllers."""

    def __init__(self) -> None:
        self._drone = None
        self._config = None
        self._pose_source = PoseSource.GPS

        self._vehicle_state = VehicleState()
        self._local_plain: Optional[LocalPose] = None
        self._vision_plain: Optional[LocalPose] = None
        self._gps_plain: Optional[GeoPoint] = None
        self._heading_val: Optional[float] = None
        self._rel_alt_val: Optional[float] = None
        self._range_val: Optional[float] = None

        self._local_pub = None
        self._gps_pub = None
        self._gps_raw_pub = None

    # Lifecycle

    def attach(self, drone) -> None:
        super().attach(drone)
        self._config = drone.config
        self._pose_source = drone.config.pose_source

    def start(self) -> None:
        self._setup_subscribers()
        self._setup_publishers()
        self._setup_services()

    def close(self) -> None:
        # ROS entities are created via the drone's BaseDrone helpers, which
        # tracks and destroys them in BaseDrone.cleanup(); nothing extra here.
        pass

    @property
    def _node(self):
        return self._drone.node

    @property
    def _is_indoor(self) -> bool:
        return self._pose_source == PoseSource.VISION

    # Subscribers / publishers / services

    def _setup_subscribers(self) -> None:
        drone = self._drone
        config = self._config

        # /mavros/state is TRANSIENT_LOCAL: match it to receive the cached
        # latest state on subscribe and reliably catch arm/mode changes.
        state_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=10,
        )
        drone._create_subscriber(State, config.state_topic, self._on_state, state_qos)
        drone._create_subscriber(Range, config.lidar_topic, self._on_range, qos_profile_sensor_data)
        drone._create_subscriber(
            PoseStamped, config.local_position_topic, self._on_local, qos_profile_sensor_data
        )

        if self._is_indoor:
            if "pose_cov" in config.vision_topic:
                drone._create_subscriber(
                    PoseWithCovarianceStamped,
                    config.vision_topic,
                    self._on_vision_cov,
                    qos_profile_sensor_data,
                )
            else:
                drone._create_subscriber(
                    PoseStamped,
                    config.vision_topic,
                    self._on_vision,
                    qos_profile_sensor_data,
                )
        else:
            drone._create_subscriber(
                NavSatFix, config.gps_topic, self._on_gps, qos_profile_sensor_data
            )
            drone._create_subscriber(
                Float64, config.rel_alt_topic, self._on_rel_alt, qos_profile_sensor_data
            )
            drone._create_subscriber(
                Float64, config.heading_topic, self._on_heading, qos_profile_sensor_data
            )

    def _setup_publishers(self) -> None:
        drone = self._drone
        self._local_pub = drone._create_publisher(PositionTarget, "/mavros/setpoint_raw/local", 1)
        if not self._is_indoor:
            self._gps_pub = drone._create_publisher(
                GeoPoseStamped, "/mavros/setpoint_position/global", 1
            )
            self._gps_raw_pub = drone._create_publisher(
                GlobalPositionTarget, "/mavros/setpoint_raw/global", 1
            )

    def _setup_services(self) -> None:
        drone = self._drone
        self._mode_srv = drone._create_client(SetMode, "/mavros/set_mode")
        self._arm_srv = drone._create_client(CommandBool, "/mavros/cmd/arming")
        self._takeoff_srv = drone._create_client(CommandTOL, "/mavros/cmd/takeoff")
        self._land_srv = drone._create_client(CommandTOL, "/mavros/cmd/land")
        self._home_srv = drone._create_client(CommandHome, "/mavros/cmd/set_home")
        self._command_srv = drone._create_client(CommandLong, "/mavros/cmd/command")
        self._param_srv = drone._create_client(SetParameters, "/mavros/param/set_parameters")

    # Subscriber callbacks (convert to plain core types)

    def _on_state(self, msg: State) -> None:
        self._vehicle_state = VehicleState(
            connected=msg.connected,
            armed=msg.armed,
            guided=msg.guided,
            mode=msg.mode,
            system_status=msg.system_status,
        )

    def _on_local(self, msg: PoseStamped) -> None:
        p = msg.pose.position
        self._local_plain = LocalPose(
            position=Vec3(p.x, p.y, p.z),
            yaw=PositionUtils.get_yaw_from_pose(msg),
        )

    def _on_vision(self, msg: PoseStamped) -> None:
        p = msg.pose.position
        self._vision_plain = LocalPose(
            position=Vec3(p.x, p.y, p.z),
            yaw=PositionUtils.get_yaw_from_pose(msg),
        )

    def _on_vision_cov(self, msg: PoseWithCovarianceStamped) -> None:
        ps = PoseStamped()
        ps.header = msg.header
        ps.pose = msg.pose.pose
        self._on_vision(ps)

    def _on_gps(self, msg: NavSatFix) -> None:
        self._gps_plain = GeoPoint(
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude=msg.altitude,
        )

    def _on_heading(self, msg: Float64) -> None:
        self._heading_val = msg.data

    def _on_rel_alt(self, msg: Float64) -> None:
        self._rel_alt_val = msg.data

    def _on_range(self, msg: Range) -> None:
        self._range_val = msg.range

    # Telemetry (plain)

    @property
    def connected(self) -> bool:
        return self._vehicle_state.connected

    @property
    def state(self) -> VehicleState:
        return self._vehicle_state

    @property
    def local_pose(self) -> Optional[LocalPose]:
        return self._local_plain

    @property
    def vision_pose(self) -> Optional[LocalPose]:
        return self._vision_plain

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

    # Driver lifecycle

    def driver_name(self) -> str:
        return "mavros_node"

    def driver_command(self) -> str:
        return f"ros2 launch mavros apm.launch fcu_url:={self._config.connection_string}"

    def start_driver(self) -> bool:
        driver_name = self.driver_name()
        if ProcessUtils.is_node_running(driver_name, timeout=2.0):
            self._node.get_logger().info(f"Driver node {driver_name} already running")
            return True
        return ProcessUtils.start_process(self.driver_command(), driver_name)

    # Commands

    def set_mode(self, mode: str) -> bool:
        try:
            req = SetMode.Request()
            req.custom_mode = mode
            res = self._drone._call_service(
                self._mode_srv, req, f"Mode: {mode}", f"Mode {mode} failed", sync=True
            )
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Set mode failed: {e}")
            return False

    def arm(self) -> bool:
        req = CommandBool.Request()
        req.value = True
        res = self._drone._call_service(self._arm_srv, req, "Armed", "Arm failed", sync=True)
        return bool(res)

    def disarm(self, force: bool = True) -> bool:
        try:
            cmd = CommandLong.Request()
            cmd.command = 400  # MAV_CMD_COMPONENT_ARM_DISARM
            cmd.param1 = 0.0
            cmd.param2 = 21196.0 if force else 0.0  # Force disarm flag
            res = self._drone._call_service(
                self._command_srv, cmd, "Disarmed", "Disarm failed", sync=True
            )
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Disarm failed: {e}")
            return False

    def command_takeoff(self, altitude: float) -> bool:
        req = CommandTOL.Request()
        req.altitude = float(altitude)
        res = self._drone._call_service(
            self._takeoff_srv,
            req,
            f"Takeoff to {altitude:.2f}m",
            "Takeoff command failed",
            sync=True,
        )
        return bool(res)

    def command_land(self) -> bool:
        req = CommandTOL.Request()
        req.altitude = 0.0
        res = self._drone._call_service(self._land_srv, req, "Landing", "Land failed", sync=True)
        return bool(res)

    def set_home(self, current: bool = True) -> bool:
        req = CommandHome.Request()
        req.current_gps = current
        res = self._drone._call_service(
            self._home_srv, req, "Home set", "Set home failed", sync=True
        )
        return bool(res)

    def set_param(self, name: str, value: Union[int, float]) -> bool:
        try:
            param = Parameter()
            param.name = name
            if isinstance(value, float):
                param.value.type = ParameterType.PARAMETER_DOUBLE
                param.value.double_value = value
            else:
                param.value.type = ParameterType.PARAMETER_INTEGER
                param.value.integer_value = value

            req = SetParameters.Request()
            req.parameters.append(param)
            res = self._drone._call_service(
                self._param_srv, req, f"{name} set", f"{name} failed", sync=True
            )
            if res is None:
                return False
            return all(r.successful for r in res.results)
        except TimeoutError as e:
            self._node.get_logger().error(f"Set param {name} failed: {e}")
            return False

    def send_command_long(self, command: int, *params: float) -> bool:
        cmd = CommandLong.Request()
        cmd.command = int(command)
        fields = ("param1", "param2", "param3", "param4", "param5", "param6", "param7")
        for field_name, value in zip(fields, params):
            setattr(cmd, field_name, float(value))
        res = self._drone._call_service(
            self._command_srv,
            cmd,
            f"Command {command} sent",
            f"Command {command} failed",
            sync=True,
        )

        return bool(res) and res.success

    # Setpoints

    def send_velocity_target(
        self,
        vx: float,
        vy: float,
        vz: float,
        yaw_rate: float,
        frame: TargetFrame,
    ) -> None:
        msg = PositionTarget()
        msg.coordinate_frame = (
            PositionTarget.FRAME_LOCAL_NED
            if frame == TargetFrame.LOCAL
            else PositionTarget.FRAME_BODY_NED
        )
        msg.type_mask = _VELOCITY_MASK
        msg.velocity.x = float(vx)
        msg.velocity.y = float(vy)
        msg.velocity.z = float(vz)
        msg.yaw_rate = float(yaw_rate)
        self._local_pub.publish(msg)

    def send_local_target(self, target: LocalTarget) -> None:
        msg = PositionTarget()
        msg.header.frame_id = "map"
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = _POSITION_MASK
        msg.position.x = float(target.position.x)
        msg.position.y = float(target.position.y)
        msg.position.z = float(target.position.z)
        msg.yaw = float(target.yaw)
        self._local_pub.publish(msg)

    def send_global_target(self, target: GlobalTarget) -> None:
        msg = GeoPoseStamped()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.pose.position.latitude = float(target.latitude)
        msg.pose.position.longitude = float(target.longitude)
        msg.pose.position.altitude = float(target.altitude)
        yaw = target.yaw if target.yaw is not None else 0.0
        quat = quaternion_from_euler(0, 0, yaw)
        msg.pose.orientation.x = float(quat[0])
        msg.pose.orientation.y = float(quat[1])
        msg.pose.orientation.z = float(quat[2])
        msg.pose.orientation.w = float(quat[3])
        self._gps_pub.publish(msg)
