from pathlib import Path
from typing import Optional, Union

import numpy as np
import rclpy
from geographic_msgs.msg import GeoPoseStamped
from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros_msgs.msg import GlobalPositionTarget, PositionTarget, State
from mavros_msgs.srv import CommandBool, CommandHome, CommandLong, CommandTOL, SetMode
from rcl_interfaces.msg import Parameter
from rcl_interfaces.srv import SetParameters
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, NavSatFix, Range
from std_msgs.msg import Float64
from tf_transformations import quaternion_from_euler

from nectar.control.base import BaseDrone
from nectar.control.config import DroneConfig, MavrosConfig
from nectar.control.exceptions import (
    CapabilityNotSupportedError,
    SensorNotAvailableError,
    TakeoffPositionNotSetError,
)
from nectar.control.factory import DroneFactory
from nectar.control.mavros.gps_utils import GPSUtils
from nectar.control.mavros.navigator import MavrosNavigator
from nectar.control.pid import PIDConfig, PositionPIDConfig
from nectar.control.types import (
    AltitudeSource,
    MoveReference,
    NavigationStrategy,
    PoseSource,
    RTLStrategy,
)
from nectar.utils.gps_calculate import GPSCalculate
from nectar.utils.position_utils import PositionUtils
from nectar.utils.process import ProcessUtils


class MavrosDrone(BaseDrone):
    """
    MAVROS drone implementation for ArduPilot/PX4 flight controllers.

    Parameters
    ----------
    config : MavrosConfig
        MAVROS-specific configuration.
    node : Node
        ROS2 node for communication.
    """

    def __init__(self, config: MavrosConfig, node: Node) -> None:
        self._mavros_state = State()
        self._gps: Optional[NavSatFix] = None
        self._heading: Optional[Float64] = None
        self._rel_alt: Optional[Float64] = None
        self._vision_pos: Optional[PoseWithCovarianceStamped] = None
        self._rng_alt: Optional[Range] = None
        self._imu: Optional[Imu] = None
        self._pid_config: Optional[PositionPIDConfig] = None
        self._takeoff_position = None
        self._initial_altitude: float = 0.0
        self._initial_heading: float = 0.0
        self._pose_source = config.pose_source

        super().__init__(config, node)
        self._setup_subscribers()
        self._setup_publishers()
        self._setup_services()
        self._startup_sensors()
        self._load_pid_config()
        self._navigator = MavrosNavigator(self)

        self._node.get_logger().info("MavrosDrone initialized")

    @classmethod
    def from_config(cls, config: DroneConfig, node: Node) -> "MavrosDrone":
        """
        Factory method for DroneFactory registration.

        Parameters
        ----------
        config : DroneConfig
            Configuration object (converted to MavrosConfig if needed).
        node : Node
            ROS2 node.

        Returns
        -------
        MavrosDrone
            Configured drone instance.
        """
        if not isinstance(config, MavrosConfig):
            config = MavrosConfig()
        return cls(config, node)

    @property
    def is_indoor(self) -> bool:
        """True if configured for vision-based indoor navigation."""
        return self._pose_source == PoseSource.VISION

    @property
    def mavros_state(self) -> State:
        """
        MAVROS state message (connected, armed, mode).

        Returns
        -------
        State
            MAVROS state message. See:
            https://docs.ros.org/en/humble/p/mavros_msgs/msg/State.html
        """
        return self._mavros_state

    @property
    def is_armed(self) -> Optional[bool]:
        """Check if motors are armed."""
        return self._mavros_state.armed if self._mavros_state else None

    @property
    def flight_mode(self) -> Optional[str]:
        """Current ArduPilot/PX4 flight mode."""
        return self._mavros_state.mode if self._mavros_state else None

    @property
    def is_fcu_connected(self) -> Optional[bool]:
        """Check if FCU is connected via MAVROS."""
        return self._mavros_state.connected if self._mavros_state else None

    @property
    def gps(self) -> NavSatFix:
        """
        GPS fix data.

        Returns
        -------
        NavSatFix
            GPS message with latitude, longitude, altitude. See:
            https://docs.ros.org/en/humble/p/sensor_msgs/msg/NavSatFix.html

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("GPS", "indoor")
        return self._gps

    @property
    def heading(self) -> float:
        """
        Compass heading in degrees.

        Returns
        -------
        float
            Heading in degrees from Float64 message. See:
            https://docs.ros.org/en/humble/p/std_msgs/msg/Float64.html

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("Heading", "indoor")
        return self._heading.data if self._heading else 0.0

    @property
    def rel_alt(self) -> float:
        """
        Relative altitude above home position.

        Returns
        -------
        float
            Altitude in meters from Float64 message. See:
            https://docs.ros.org/en/humble/p/std_msgs/msg/Float64.html

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("Relative altitude", "indoor")
        return self._rel_alt.data if self._rel_alt else 0.0

    @property
    def vision_pos(self) -> Optional[PoseWithCovarianceStamped]:
        """
        Vision-based pose estimate from external source (T265, d435i, etc.).

        Returns
        -------
        Optional[PoseWithCovarianceStamped]
            Vision pose message. See:
            https://docs.ros.org/en/humble/p/geometry_msgs/msg/PoseWithCovarianceStamped.html
        """
        return self._vision_pos

    @property
    def lidar_available(self) -> bool:
        """Whether lidar data has been received."""
        return self._rng_alt is not None

    @property
    def pid_config(self) -> Optional[PositionPIDConfig]:
        """Current PID configuration for position control."""
        return self._pid_config

    def get_altitude(self, source: AltitudeSource = AltitudeSource.AUTO) -> Optional[float]:
        """
        Get altitude from a specific sensor source.

        Parameters
        ----------
        source : AltitudeSource, default=AUTO
            Sensor source to read altitude from:

            - AUTO: best available (lidar > vision Z > relative altitude).
            - LIDAR: lidar rangefinder reading.
            - VISION: vision pose Z component.
            - REL_ALT: GPS-based relative altitude.

        Returns
        -------
        float or None
            Altitude in meters, or None if the requested source is unavailable.
        """
        if source == AltitudeSource.LIDAR:
            return self._rng_alt.range if self._rng_alt else None
        if source == AltitudeSource.VISION:
            if self._vision_pos is not None:
                return self._vision_pos.pose.pose.position.z
            return None
        if source == AltitudeSource.REL_ALT:
            if not self.is_indoor and self._rel_alt is not None:
                return self._rel_alt.data
            return None
        # AUTO: lidar > vision Z > relative altitude
        if self._rng_alt is not None:
            return self._rng_alt.range
        if self._vision_pos is not None:
            return self._vision_pos.pose.pose.position.z
        if self._rel_alt is not None:
            return self._rel_alt.data
        return None

    @property
    def position(self) -> Union[PoseWithCovarianceStamped, NavSatFix]:
        """
        Current position as vision pose (indoor) or GPS (outdoor).

        Returns
        -------
        Union[PoseWithCovarianceStamped, NavSatFix]
            - Indoor: PoseWithCovarianceStamped. See:
              https://docs.ros.org/en/humble/p/geometry_msgs/msg/PoseWithCovarianceStamped.html
            - Outdoor: NavSatFix. See:
              https://docs.ros.org/en/humble/p/sensor_msgs/msg/NavSatFix.html
        """
        if self.is_indoor:
            return self._vision_pos
        return self._gps

    @property
    def position_as_target(self) -> Optional[Union[PositionTarget, GeoPoseStamped]]:
        """
        Current position converted to setpoint message type.

        Returns
        -------
        Optional[Union[PositionTarget, GeoPoseStamped]]
            - Indoor: PositionTarget. See:
              https://docs.ros.org/en/humble/p/mavros_msgs/msg/PositionTarget.html
            - Outdoor: GeoPoseStamped. See:
              https://docs.ros.org/en/humble/p/geographic_msgs/msg/GeoPoseStamped.html
            - None if no position data.
        """
        if self.is_indoor:
            if self._vision_pos is None:
                self._node.get_logger().debug("position_as_target: No vision data")
                return None
            lidar = self._rng_alt.range if self._rng_alt else None
            return PositionUtils.convert_position_to_target(self._vision_pos, lidar=lidar)
        if self._gps is None:
            self._node.get_logger().debug("position_as_target: No GPS data")
            return None
        return PositionUtils.convert_position_to_target(self._gps, self.heading)

    def _setup_subscribers(self) -> None:
        """Initialize ROS2 subscribers for sensor data based on pose source."""
        config: MavrosConfig = self._config

        self._create_subscriber(
            State,
            config.state_topic,
            lambda msg: setattr(self, "_mavros_state", msg),
            10,
        )

        self._create_subscriber(
            Range,
            config.lidar_topic,
            lambda msg: setattr(self, "_rng_alt", msg),
            10,
        )

        self._create_subscriber(
            Imu,
            config.imu_topic,
            lambda msg: setattr(self, "_imu", msg),
            qos_profile_sensor_data,
        )

        if self._pose_source == PoseSource.VISION:
            self._create_subscriber(
                PoseWithCovarianceStamped,
                config.vision_topic,
                lambda msg: setattr(self, "_vision_pos", msg),
                qos_profile_sensor_data,
            )
        else:
            self._create_subscriber(
                NavSatFix,
                config.gps_topic,
                lambda msg: setattr(self, "_gps", msg),
                qos_profile_sensor_data,
            )
            self._create_subscriber(
                Float64,
                config.rel_alt_topic,
                lambda msg: setattr(self, "_rel_alt", msg),
                qos_profile_sensor_data,
            )
            self._create_subscriber(
                Float64,
                config.heading_topic,
                lambda msg: setattr(self, "_heading", msg),
                qos_profile_sensor_data,
            )

    def _setup_publishers(self) -> None:
        """Initialize ROS2 publishers for setpoint commands."""
        self._local_pub = self._create_publisher(PositionTarget, "/mavros/setpoint_raw/local", 1)

        if not self.is_indoor:
            self._gps_pub = self._create_publisher(
                GeoPoseStamped, "/mavros/setpoint_position/global", 1
            )
            self._gps_raw_pub = self._create_publisher(
                GlobalPositionTarget, "/mavros/setpoint_raw/global", 1
            )

    def publish_setpoint(self, target: Union[PositionTarget, GeoPoseStamped]) -> None:
        """
        Publish navigation target to the appropriate MAVROS setpoint topic.

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            PositionTarget publishes to local setpoint topic.
            GeoPoseStamped publishes to GPS setpoint topic.
        """
        if isinstance(target, GeoPoseStamped):
            self._gps_pub.publish(target)
        else:
            self._local_pub.publish(target)

    def _setup_services(self) -> None:
        """Initialize ROS2 service clients for MAVROS commands."""
        self._mode_srv = self._create_client(SetMode, "/mavros/set_mode")
        self._arm_srv = self._create_client(CommandBool, "/mavros/cmd/arming")
        self._takeoff_srv = self._create_client(CommandTOL, "/mavros/cmd/takeoff")
        self._land_srv = self._create_client(CommandTOL, "/mavros/cmd/land")
        self._home_srv = self._create_client(CommandHome, "/mavros/cmd/set_home")
        self._command_srv = self._create_client(CommandLong, "/mavros/cmd/command")
        self._param_srv = self._create_client(SetParameters, "/mavros/param/set_parameters")

    def _startup_sensors(self) -> None:
        """
        Wait for expected sensors to become available.

        When ``expect_lidar`` is False the lidar wait is skipped. The
        subscriber remains active, so lidar data is still captured if
        it becomes available later.

        Stores initial altitude and heading for GPS offset calculations.
        """
        config: MavrosConfig = self._config
        timeout = Duration(seconds=config.sensor_timeout)

        self._node.get_logger().info("Starting sensor initialization...")

        if config.expect_lidar:
            start = self._node.get_clock().now()
            while self._node.get_clock().now() - start < timeout:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                if self._rng_alt is not None:
                    self._node.get_logger().info("LiDAR available")
                    break
            if self._rng_alt is None:
                self._node.get_logger().warn("LiDAR not available")
        else:
            self._node.get_logger().info("LiDAR not checked")

        start = self._node.get_clock().now()
        sensors_ok = False

        if self.is_indoor:
            while self._node.get_clock().now() - start < timeout:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                if self._vision_pos is not None:
                    sensors_ok = True
                    self._node.get_logger().info("Vision pose received")
                    break
            self._initial_altitude = 0.0
            self._initial_heading = 0.0
        else:
            while self._node.get_clock().now() - start < timeout:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                if self._gps is not None and self._heading is not None:
                    sensors_ok = True
                    self._node.get_logger().info("GPS and heading received")
                    break
            if sensors_ok:
                self._initial_altitude = self._gps.altitude
                self._initial_heading = self._heading.data

        if not sensors_ok:
            self._node.get_logger().warn("Sensor initialization incomplete")

    def _load_pid_config(self) -> None:
        """Load PID configuration from file or use defaults based on indoor/outdoor mode."""
        config: MavrosConfig = self._config

        if config.pid_config_file:
            path = Path(config.pid_config_file)
        else:
            config_dir = Path(__file__).parent.parent / "config" / "mavros"
            if self.is_indoor:
                path = config_dir / "position_indoor.yaml"
            else:
                path = config_dir / "position_outdoor.yaml"

        if path.exists():
            self._pid_config = PositionPIDConfig.from_yaml(path)
        else:
            self._pid_config = self._default_pid_config()

    def _default_pid_config(self) -> PositionPIDConfig:
        """
        Generate default PID configuration.

        Returns
        -------
        PositionPIDConfig
            Default configuration for current mode.
        """
        if self.is_indoor:
            return PositionPIDConfig(
                x=PIDConfig(
                    kp=0.5,
                    output_min=-0.42,
                    output_max=0.42,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
                y=PIDConfig(
                    kp=0.5,
                    output_min=-0.42,
                    output_max=0.42,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
                z=PIDConfig(
                    kp=0.22,
                    output_min=-0.15,
                    output_max=0.1,
                    integral_min=-0.3,
                    integral_max=0.3,
                ),
                yaw=PIDConfig(
                    kp=0.5,
                    ki=0.1,
                    output_min=-0.2,
                    output_max=0.2,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
            )
        return PositionPIDConfig(
            x=PIDConfig(
                kp=0.8,
                output_min=-1.0,
                output_max=1.0,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            y=PIDConfig(
                kp=0.8,
                output_min=-1.0,
                output_max=1.0,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            z=PIDConfig(
                kp=0.5,
                output_min=-0.8,
                output_max=0.8,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            yaw=PIDConfig(
                kp=0.5,
                ki=0.1,
                output_min=-0.3,
                output_max=0.3,
                integral_min=-0.5,
                integral_max=0.5,
            ),
        )

    def _get_driver_name(self) -> str:
        """Return MAVROS driver node name."""
        return "mavros_node"

    def _get_driver_command(self) -> str:
        """Return command to start MAVROS driver."""
        config: MavrosConfig = self._config
        return f"ros2 launch mavros apm.launch fcu_url:={config.connection_string}"

    def _start_driver(self) -> bool:
        """
        Launch MAVROS driver process.

        Checks if driver node is already running before starting. If node exists,
        assumes driver was started manually and returns True.

        Returns
        -------
        bool
            True if driver started or already running, False otherwise.
        """
        driver_name = self._get_driver_name()
        if ProcessUtils.is_node_running(driver_name, timeout=2.0):
            self._node.get_logger().info(f"Driver node {driver_name} already running")
            return True

        cmd = self._get_driver_command()
        return ProcessUtils.start_process(cmd, driver_name)

    def connect(self) -> bool:
        """
        Check MAVROS connection status to FCU.

        Returns
        -------
        bool
            True if connected to flight controller.
        """
        self._connected = self._mavros_state.connected
        return self._connected

    def disconnect(self) -> None:
        """Disconnect from MAVROS and cleanup resources."""
        self.cleanup()

    def arm(self) -> bool:
        """
        Arm motors in GUIDED mode.

        Sets mode to GUIDED, waits 0.5s, sends arm command, waits 1.5s.

        Returns
        -------
        bool
            True if arming successful, False on failure or timeout.
        """
        try:
            if not self.set_mode("GUIDED"):
                return False
            self.delay(0.5)
            req = CommandBool.Request()
            req.value = True
            res = self._call_service(self._arm_srv, req, "Armed", "Arm failed", sync=True)
            if res:
                self.delay(1.5)
                return True
            return False
        except TimeoutError as e:
            self._node.get_logger().error(f"Arm failed: {e}")
            return False

    def disarm(self) -> bool:
        """
        Force disarm motors.

        Sends MAVLink COMMAND_LONG with MAV_CMD_COMPONENT_ARM_DISARM (400)
        and force flag (param2=21196) to bypass safety checks.

        Returns
        -------
        bool
            True if disarming successful, False on failure or timeout.
        """
        try:
            cmd = CommandLong.Request()
            cmd.command = 400  # MAV_CMD_COMPONENT_ARM_DISARM
            cmd.param1 = 0.0
            cmd.param2 = 21196.0  # Force disarm flag
            cmd.param3 = 0.0
            cmd.param4 = 0.0
            cmd.param5 = 0.0
            cmd.param6 = 0.0
            cmd.param7 = 0.0
            res = self._call_service(self._command_srv, cmd, "Disarmed", "Disarm failed", sync=True)
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Disarm failed: {e}")
            return False

    def takeoff(
        self,
        altitude: float,
        max_retries: int = 2,
        adjust_altitude: bool = True,
        precision: float = 0.12,
        timeout: float = 25.0,
    ) -> bool:
        """
        Execute takeoff sequence with retry logic and optional altitude adjustment.

        Arms drone, stores takeoff position, sends takeoff command, and verifies altitude gain.
        If altitude doesn't change significantly, disarms and retries up to max_retries times.
        Optionally fine-tunes altitude using move_to to reach target precisely.

        Parameters
        ----------
        altitude : float
            Target altitude in meters.
        max_retries : int, default=2
            Maximum number of takeoff attempts.
        adjust_altitude : bool, default=True
            If True, fine-tune altitude using move_to after takeoff command.
        precision : float, default=0.12
            Altitude precision in meters for adjustment.
        timeout : float, default=25.0
            Maximum time in seconds for altitude adjustment.

        Returns
        -------
        bool
            True if takeoff successful, False if all retries exhausted or service timeout.
        """
        req = CommandTOL.Request()
        req.altitude = float(altitude)

        for attempt in range(max_retries):
            self._node.get_logger().info(f"Takeoff attempt {attempt + 1}/{max_retries}")

            if not self.arm():
                self._node.get_logger().error("Arm failed, cannot takeoff")
                return False

            self.delay(3.0)

            if attempt == 0:
                if not self._set_takeoff_position():
                    self._node.get_logger().error("Failed to set takeoff position")
                    return False

            takeoff_height = self.get_altitude() or 0.0

            try:
                res = self._call_service(
                    self._takeoff_srv,
                    req,
                    f"Takeoff to {altitude}m",
                    "Takeoff command failed",
                    sync=True,
                )
                if not res:
                    return False
            except TimeoutError as e:
                self._node.get_logger().error(f"Takeoff service timeout: {e}")
                return False

            self.delay(altitude * 3)

            current_alt = self.get_altitude() or 0.0
            height_gain = abs(current_alt - takeoff_height)
            if height_gain >= 0.1:
                self._node.get_logger().info(f"Takeoff successful (gained {height_gain:.2f}m)")

                if adjust_altitude:
                    altitude_diff = altitude - current_alt

                    if abs(altitude_diff) > precision:
                        self._node.get_logger().info(
                            f"Adjusting altitude from {current_alt:.2f}m to {altitude:.2f}m"
                        )
                        adjustment_success = self.move_to(
                            z=altitude_diff,
                            precision=precision,
                            timeout=timeout,
                        )
                        final_alt = self.get_altitude() or 0.0
                        if adjustment_success:
                            self._node.get_logger().info(f"Altitude adjusted to {final_alt:.2f}m")
                        else:
                            self._node.get_logger().warn(
                                f"Altitude adjustment incomplete, current: {final_alt:.2f}m"
                            )

                return True

            if attempt < max_retries - 1:
                self._node.get_logger().warn(
                    f"Takeoff failed (height gain: {height_gain:.2f}m), disarming for retry..."
                )
                self.disarm()
                self.delay(2.0)
            else:
                self._node.get_logger().error(f"Takeoff failed after {max_retries} attempts")

        return False

    def land(self, timeout: float = 30.0) -> bool:
        """
        Execute landing at current position.

        Sends land command and waits for motors to disarm or timeout.

        Parameters
        ----------
        timeout : float, default=30.0
            Maximum time to wait for landing completion.

        Returns
        -------
        bool
            True if motors disarmed (landed), False if still armed after timeout
            or on service timeout.
        """
        try:
            req = CommandTOL.Request()
            req.altitude = 0.0
            res = self._call_service(self._land_srv, req, "Landing", "Land failed", sync=True)
            if not res:
                return False

            duration = Duration(seconds=timeout)
            start = self._node.get_clock().now()

            while self._node.get_clock().now() - start < duration:
                rclpy.spin_once(self._node, timeout_sec=0.1)
                if not self._mavros_state.armed:
                    break

            self.delay(0.1)
            return not self._mavros_state.armed
        except TimeoutError as e:
            self._node.get_logger().error(f"Land service timeout: {e}")
            return False

    def move_velocity(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vz: float = 0.0,
        vyaw: float = 0.0,
        duration: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
    ) -> None:
        """
        Move the drone by sending velocity commands.

        Parameters
        ----------
        vx : float (m/s), default=0.0
            (+) Move forward, (-) Move backward.

        vy : float (m/s), default=0.0
            (+) Move left, (-) Move right.

        vz : float (m/s), default=0.0
            (+) Move up, (-) Move down.

        vyaw : float (rad/s), default=0.0
            (+) Rotate counter-clockwise, (-) Rotate clockwise.

        duration : float (s), optional
            Movement time duration. If None, publishes a single command
            (continuous mode, caller must re-publish).

        reference : MoveReference, default=BODY
            Velocity reference frame:

            - BODY: velocities relative to the drone's current heading.
            - WORLD: velocities relative to the world/local NED frame.
            - TAKEOFF: velocities relative to the takeoff heading.
              Requires takeoff position to be set.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but takeoff position not set.
        SensorNotAvailableError
            If required position sensors are not available.
        """
        msg = PositionTarget()
        msg.coordinate_frame = (
            PositionTarget.FRAME_LOCAL_NED
            if reference == MoveReference.WORLD
            else PositionTarget.FRAME_BODY_NED
        )
        msg.type_mask = 1479

        if reference == MoveReference.TAKEOFF:
            if self._takeoff_position is None:
                raise TakeoffPositionNotSetError("move_velocity with TAKEOFF reference")

            self._validate_position_sensors()

            if self.is_indoor:
                current_yaw = PositionUtils.get_yaw_from_pose(self._vision_pos)
            else:
                current_yaw = np.radians(self.heading)

            takeoff_yaw = PositionUtils.get_yaw_from_pose(self._takeoff_position)

            vx_body, vy_body, vz_body = PositionUtils.transform_takeoff_to_body_velocities(
                vx, vy, vz, current_yaw, takeoff_yaw
            )
            msg.velocity.x = float(vx_body)
            msg.velocity.y = float(vy_body)
            msg.velocity.z = float(vz_body)
        else:
            msg.velocity.x = float(vx)
            msg.velocity.y = float(vy)
            msg.velocity.z = float(vz)

        msg.yaw_rate = float(vyaw)

        self._node.get_logger().debug(
            f"Velocity cmd: vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} vyaw={vyaw:.2f} "
            f"ref={reference.name}"
        )

        if duration is None:
            self._local_pub.publish(msg)
        else:
            rate = 1.0 / 30
            start = self._node.get_clock().now()
            dur = Duration(seconds=duration)

            while self._node.get_clock().now() - start < dur:
                self._local_pub.publish(msg)
                self.delay(rate)

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        yaw: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
        timeout: Optional[float] = 60.0,
        precision: float = 0.2,
        strategy: NavigationStrategy = NavigationStrategy.PID,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
    ) -> bool:
        """
        Move the drone to a position relative to its current location and heading.

        The movement is relative to the drone's current orientation (BODY) or
        the takeoff position and heading (TAKEOFF).

        Parameters
        ----------
        x : float, optional
            Distance to move forward (+) or backward (-) in meters,
            relative to the reference heading.

            If None, disables control in the X axis.

        y : float, optional
            Distance to move left (+) or right (-) in meters,
            relative to the reference heading.

            If None, disables control in the Y axis.

        z : float, optional
            Distance to move up (+) or down (-) in meters,
            relative to the reference altitude.

            If None, disables altitude control.

        yaw : float, optional
            Desired yaw angle in degrees.

            If None, maintains current yaw.

        reference : MoveReference, default=BODY
            Movement reference frame:

            - BODY: x, y, z are relative distances from the current position
              and heading.
            - TAKEOFF: x, y, z are absolute coordinates from the takeoff
              position and heading. Requires takeoff position to be set.

            Note: WORLD reference is not supported in move_to.

        timeout : float, optional, default=60.0
            Maximum navigation time in seconds. None for no timeout.

        precision : float, default=0.2
            Acceptable radius in meters for reaching the target position.

        strategy : NavigationStrategy, default=PID
            PID: closed-loop velocity control to reach the target.
            SETPOINT: direct position setpoint publishing (indoor only).

        altitude_source : AltitudeSource, default=AUTO
            Altitude sensor source for PID navigation:

            - AUTO: best available (lidar > vision Z > relative altitude).
            - LIDAR: lidar rangefinder for ground-relative altitude control.
              With BODY reference, z is relative offset from current lidar reading.
              With TAKEOFF reference, z is absolute altitude above ground.

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but takeoff position not set.
        CapabilityNotSupportedError
            If reference=WORLD in position control.
        SensorNotAvailableError
            If altitude_source=LIDAR but lidar is not available.
        """
        if reference == MoveReference.TAKEOFF and self._takeoff_position is None:
            raise TakeoffPositionNotSetError("move_to with TAKEOFF reference")

        if reference == MoveReference.WORLD:
            raise CapabilityNotSupportedError(
                "WORLD reference in position control", self._config.name
            )

        self._validate_position_sensors()

        self._node.get_logger().info(
            f"move_to: x={x} y={y} z={z} yaw={yaw} ref={reference.name} "
            f"strategy={strategy.name} precision={precision}m "
            f"alt_source={altitude_source.name}"
        )

        self.delay(0.05)

        if strategy == NavigationStrategy.SETPOINT:
            target = self._compute_setpoint_target(x, y, z, yaw, reference)
            check_alt = None
            if isinstance(target, GeoPoseStamped):
                check_alt = self._compute_target_rel_alt(z, reference)
            return self._navigator.navigate_setpoint(target, timeout, precision, check_alt)

        # PID navigation
        target = self._compute_target(x, y, z, yaw, reference)
        active_axes = (x is not None, y is not None, z is not None)
        alt_target = self._navigator.resolve_altitude_target(z, reference, altitude_source)

        return self._navigator.navigate_pid(
            target=target,
            active_axes=active_axes,
            yaw=yaw,
            timeout=timeout,
            precision=precision,
            altitude_source=altitude_source,
            altitude_target=alt_target,
        )

    def move_to_gps(
        self,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        heading: Optional[float] = None,
        timeout: Optional[float] = 60.0,
        precision: float = 0.5,
        strategy: NavigationStrategy = NavigationStrategy.PID,
    ) -> bool:
        """
        Move the drone to a specified GPS coordinate.

        Parameters
        ----------
        latitude : float
            Target latitude in degrees (WGS84).

        longitude : float
            Target longitude in degrees (WGS84).

        altitude : float, optional
            Target altitude above ground in meters (relative, not AMSL).

            If None, maintains current altitude.

        heading : float, optional
            Desired heading in degrees (0 = North, clockwise positive).

            If None, maintains current heading.

        timeout : float, optional, default=60.0
            Maximum time allowed in seconds to reach the target.

            If None, no timeout is applied.

        precision : float, default=0.5
            Acceptable radius in meters for reaching the target position.

        strategy : NavigationStrategy, default=PID
            PID: closed-loop velocity control to reach the target.
            SETPOINT: direct GPS position setpoint publishing.

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.

        Raises
        ------
        CapabilityNotSupportedError
            If called in indoor mode (pose_source=VISION).
        """
        if self.is_indoor:
            raise CapabilityNotSupportedError("GPS navigation", "indoor mode")

        self._validate_position_sensors()

        alt = altitude if altitude is not None else self.rel_alt
        hdg = heading if heading is not None else self.heading

        self._node.get_logger().info(
            f"move_to_gps: lat={latitude:.6f} lon={longitude:.6f} alt={alt:.1f}m "
            f"hdg={hdg:.1f}\u00b0 strategy={strategy.name} precision={precision}m"
        )

        target = GPSUtils.create_gps_setpoint(latitude, longitude, alt, hdg, self._initial_altitude)

        if strategy == NavigationStrategy.SETPOINT:
            return self._navigator.navigate_setpoint(target, timeout, precision, check_alt=alt)

        return self._navigator.navigate_pid(
            target=target,
            active_axes=(True, True, True),
            yaw=None,
            timeout=timeout,
            precision=precision,
            altitude_source=AltitudeSource.REL_ALT,
            altitude_target=alt,
        )

    def _compute_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> Union[PositionTarget, GeoPoseStamped]:
        if self.is_indoor:
            return self._compute_local_target(x, y, z, yaw, reference)
        return self._compute_gps_target(x, y, z, yaw, reference)

    def _compute_local_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> PositionTarget:
        if reference == MoveReference.BODY:
            pos = self._vision_pos.pose.pose.position
            current_yaw = PositionUtils.get_yaw_from_pose(self._vision_pos)
        else:
            pos = self._takeoff_position.position
            current_yaw = self._takeoff_position.yaw

        dx = (x or 0) * np.cos(current_yaw) - (y or 0) * np.sin(current_yaw)
        dy = (x or 0) * np.sin(current_yaw) + (y or 0) * np.cos(current_yaw)
        dz = z or 0

        msg = PositionTarget()
        msg.header.frame_id = "map"
        msg.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        msg.type_mask = (
            PositionTarget.IGNORE_AFX
            | PositionTarget.IGNORE_AFY
            | PositionTarget.IGNORE_AFZ
            | PositionTarget.IGNORE_YAW_RATE
            | PositionTarget.IGNORE_VX
            | PositionTarget.IGNORE_VY
            | PositionTarget.IGNORE_VZ
        )
        msg.position.x = float(pos.x + dx)
        msg.position.y = float(pos.y + dy)
        msg.position.z = float(pos.z + dz)
        msg.yaw = float(current_yaw + np.radians(yaw) if yaw is not None else current_yaw)
        return msg

    def _compute_gps_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> GeoPoseStamped:
        if reference == MoveReference.BODY:
            hdg = self.heading
            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                z or 0,
                self._gps.latitude,
                self._gps.longitude,
                self._gps.altitude,
                hdg,
            )
        else:
            hdg = np.degrees(PositionUtils.get_yaw_from_pose(self._takeoff_position))
            lat, lon, alt = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                z or 0,
                self._takeoff_position.pose.position.latitude,
                self._takeoff_position.pose.position.longitude,
                self._takeoff_position.pose.position.altitude,
                hdg,
            )

        target_yaw = hdg + (yaw if yaw is not None else 0)
        quat = quaternion_from_euler(0, 0, np.radians(target_yaw))

        msg = GeoPoseStamped()
        msg.pose.position.latitude = float(lat)
        msg.pose.position.longitude = float(lon)
        msg.pose.position.altitude = float(alt)
        msg.pose.orientation.x = float(quat[0])
        msg.pose.orientation.y = float(quat[1])
        msg.pose.orientation.z = float(quat[2])
        msg.pose.orientation.w = float(quat[3])
        return msg

    def _compute_setpoint_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> Union[PositionTarget, GeoPoseStamped]:
        """
        Compute target for SETPOINT navigation.

        Parameters
        ----------
        x, y, z, yaw, reference
            Same as ``_compute_target``.

        Returns
        -------
        PositionTarget | GeoPoseStamped
            Setpoint-ready target message.
        """
        if self.is_indoor:
            return self._compute_local_target(x, y, z, yaw, reference)
        return self._compute_gps_setpoint_target(x, y, z, yaw, reference)

    def _compute_gps_setpoint_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> GeoPoseStamped:
        """
        Compute GPS target with AMSL altitude correction for SETPOINT publishing.

        Uses ``GPSUtils.create_gps_setpoint`` to apply EGM96 geoid correction
        so the altitude published to MAVROS is in AMSL as required.

        Parameters
        ----------
        x, y, z, yaw, reference
            Same as ``_compute_gps_target``.

        Returns
        -------
        GeoPoseStamped
            GPS target with AMSL-corrected altitude.
        """
        if reference == MoveReference.BODY:
            hdg = self.heading
            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                0,
                self._gps.latitude,
                self._gps.longitude,
                self._gps.altitude,
                hdg,
            )
        else:
            hdg = np.degrees(PositionUtils.get_yaw_from_pose(self._takeoff_position))
            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                x or 0,
                -(y or 0),
                0,
                self._takeoff_position.pose.position.latitude,
                self._takeoff_position.pose.position.longitude,
                self._takeoff_position.pose.position.altitude,
                hdg,
            )

        target_rel_alt = self._compute_target_rel_alt(z, reference)
        target_hdg = hdg + (yaw if yaw is not None else 0)

        return GPSUtils.create_gps_setpoint(
            lat, lon, target_rel_alt, target_hdg, self._initial_altitude
        )

    def _compute_target_rel_alt(self, z: Optional[float], reference: MoveReference) -> float:
        """
        Compute target relative altitude for GPS setpoint navigation.

        Parameters
        ----------
        z : float, optional
            Altitude offset in meters. None treated as 0.
        reference : MoveReference
            BODY: offset from current rel_alt. TAKEOFF: absolute rel_alt.

        Returns
        -------
        float
            Target relative altitude in meters.
        """
        if reference == MoveReference.TAKEOFF:
            return z or 0
        return self.rel_alt + (z or 0)

    def _validate_position_sensors(self) -> None:
        """
        Validate that position sensors are available for navigation.

        Raises
        ------
        SensorNotAvailableError
            If required position sensor data is missing.
        """
        if self.is_indoor:
            if self._vision_pos is None:
                raise SensorNotAvailableError("Vision pose", "navigation requires sensor data")
        else:
            if self._gps is None:
                raise SensorNotAvailableError("GPS", "navigation requires sensor data")

    def emergency_stop(self) -> None:
        """Execute emergency stop via force disarm."""
        self._node.get_logger().warn("Emergency stop triggered")
        self.disarm()

    def set_home(self) -> bool:
        """
        Set current GPS position as home.

        Returns
        -------
        bool
            True if home position set successfully, False on failure or timeout.
        """
        try:
            req = CommandHome.Request()
            req.current_gps = True
            res = self._call_service(self._home_srv, req, "Home set", "Set home failed", sync=True)
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Set home failed: {e}")
            return False

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        strategy: RTLStrategy = RTLStrategy.PID,
        land: bool = True,
    ) -> bool:
        """
        Return to launch position.

        Parameters
        ----------
        altitude : float, optional
            Transit altitude in meters. If specified, climbs/descends before navigating.
        precision : float, default=0.2
            Arrival threshold for PID strategy in meters.
        strategy : RTLStrategy, default=PID
            PID: navigate to takeoff position using velocity control,
            ARDUPILOT: trigger FCU's native RTL mode.
        land : bool, default=True
            Execute landing after reaching home.

        Returns
        -------
        bool
            True if RTL successful.

        Raises
        ------
        TakeoffPositionNotSetError
            If strategy=PID but takeoff position not set.
        """
        self._node.get_logger().info(f"RTL using strategy: {strategy.name}")

        if strategy == RTLStrategy.ARDUPILOT:
            return self._rtl_ardupilot(altitude, land)
        return self._rtl_pid(altitude, precision, land)

    def _rtl_ardupilot(self, altitude: Optional[float], land: bool) -> bool:
        try:
            if altitude is not None:
                param = Parameter()
                param.name = "RTL_ALT"
                param.value.integer_value = int(altitude * 100)

                req = SetParameters.Request()
                req.parameters.append(param)
                self._call_service(self._param_srv, req, "RTL_ALT set", "RTL_ALT failed", sync=True)
                self.delay(1.0)

            if not self.set_mode("RTL"):
                return False

            if not land:
                self.delay(5.0)

            return True
        except TimeoutError as e:
            self._node.get_logger().error(f"RTL ArduPilot failed: {e}")
            return False

    def _rtl_pid(self, altitude: Optional[float], precision: float, land: bool) -> bool:
        if self._takeoff_position is None:
            raise TakeoffPositionNotSetError("RTL")

        if altitude is not None:
            target_z = altitude - (self.get_altitude() or 0.0)
            self._node.get_logger().info(f"Moving to RTL altitude: {altitude}m")
            self.move_to(x=0, y=0, z=target_z, precision=precision)

        self._node.get_logger().info("Navigating to takeoff position")
        self.move_to(x=0, y=0, z=0, reference=MoveReference.TAKEOFF, precision=precision)

        if land:
            self._node.get_logger().info("Landing")
            self.land()

        return True

    def set_mode(self, mode: str) -> bool:
        """
        Set FCU flight mode.

        Parameters
        ----------
        mode : str
            Flight mode name (e.g., 'GUIDED', 'STABILIZE', 'LOITER', 'RTL', 'LAND').

        Returns
        -------
        bool
            True if mode set successfully, False on failure or timeout.

        See Also
        --------
        https://ardupilot.org/copter/docs/flight-modes.html
        """
        try:
            req = SetMode.Request()
            req.custom_mode = mode
            res = self._call_service(
                self._mode_srv, req, f"Mode: {mode}", f"Mode {mode} failed", sync=True
            )
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Set mode failed: {e}")
            return False

    def set_param(self, param_id: str, param_value: int) -> bool:
        """
        Set ArduPilot parameter.

        Parameters
        ----------
        param_id : str
            Parameter name (e.g., 'RTL_ALT').
        param_value : int
            Integer parameter value.

        Returns
        -------
        bool
            True if parameter set successfully, False on failure or timeout.
        """
        try:
            param = Parameter()
            param.name = param_id
            param.value.integer_value = param_value

            req = SetParameters.Request()
            req.parameters.append(param)
            res = self._call_service(
                self._param_srv, req, f"{param_id} set", f"{param_id} failed", sync=True
            )
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Set param {param_id} failed: {e}")
            return False

    def do_servo(self, aux_out: int, pwm_value: int) -> bool:
        """
        Control auxiliary servo output.

        Parameters
        ----------
        aux_out : int
            Servo channel (0-7 maps to AUX outputs 1-8, FCU channels 9-16).
        pwm_value : int
            PWM value (typically 1000-2000 µs).

        Returns
        -------
        bool
            True if servo command sent successfully, False on failure or timeout.
        """
        try:
            cmd = CommandLong.Request()
            cmd.command = 183
            cmd.param1 = float(aux_out + 8)
            cmd.param2 = float(pwm_value)
            res = self._call_service(
                self._command_srv,
                cmd,
                f"Servo {aux_out} set",
                "Servo failed",
                sync=True,
            )
            return bool(res)
        except TimeoutError as e:
            self._node.get_logger().error(f"Servo command failed: {e}")
            return False

    def _set_takeoff_position(self) -> bool:
        """
        Store current position as takeoff reference.

        Returns
        -------
        bool
            True if position set successfully, False if sensor data missing.
        """
        try:
            pos = self.position_as_target
            if pos is None:
                self._node.get_logger().error("Cannot set takeoff position: No position data")
                return False
            self._takeoff_position = pos
            self._node.get_logger().info("Takeoff position set")
            return True
        except (SensorNotAvailableError, ValueError, AttributeError) as e:
            self._node.get_logger().error(f"Cannot set takeoff position: {e}")
            return False

    def set_takeoff_position(self, pose=None, heading: Optional[float] = None) -> None:
        """
        Manually set takeoff position for TAKEOFF reference frame and RTL.

        Parameters
        ----------
        pose : PoseWithCovarianceStamped | NavSatFix | PositionTarget | GeoPoseStamped, optional
            Position to use as takeoff reference. If None, uses current position.

            - PoseWithCovarianceStamped: See:
              https://docs.ros.org/en/humble/p/geometry_msgs/msg/PoseWithCovarianceStamped.html
            - NavSatFix: See:
              https://docs.ros.org/en/humble/p/sensor_msgs/msg/NavSatFix.html
            - PositionTarget: See:
              https://docs.ros.org/en/humble/p/mavros_msgs/msg/PositionTarget.html
            - GeoPoseStamped: See:
              https://docs.ros.org/en/humble/p/geographic_msgs/msg/GeoPoseStamped.html
        heading : float, optional
            Heading in degrees for NavSatFix. Required if pose is NavSatFix.

        Raises
        ------
        ValueError
            If pose type invalid for current mode.
        """
        if pose is None:
            self._takeoff_position = self.position_as_target
        elif self.is_indoor:
            if isinstance(pose, PoseWithCovarianceStamped):
                self._takeoff_position = PositionUtils.convert_position_to_target(pose)
            elif isinstance(pose, PositionTarget):
                self._takeoff_position = pose
            else:
                raise ValueError("Invalid pose type for indoor mode")
        else:
            if isinstance(pose, NavSatFix) and heading is not None:
                self._takeoff_position = PositionUtils.convert_position_to_target(pose, heading)
            elif isinstance(pose, GeoPoseStamped):
                self._takeoff_position = pose
            else:
                raise ValueError("Invalid pose type for outdoor mode")
        self._node.get_logger().info("Takeoff position set")

    def set_pid_config(self, config) -> None:
        """
        Update PID configuration.

        Parameters
        ----------
        config : str | dict | PositionPIDConfig
            YAML file path, configuration dictionary, or PositionPIDConfig object.

        Raises
        ------
        TypeError
            If config type not supported.
        """
        if isinstance(config, str):
            self._pid_config = PositionPIDConfig.from_yaml(config)
        elif isinstance(config, dict):
            self._pid_config = PositionPIDConfig(
                x=PIDConfig.from_dict(config.get("x", {})),
                y=PIDConfig.from_dict(config.get("y", {})),
                z=PIDConfig.from_dict(config.get("z", {})),
                yaw=PIDConfig.from_dict(config.get("yaw", {})),
            )
        elif isinstance(config, PositionPIDConfig):
            self._pid_config = config
        else:
            raise TypeError(f"Invalid config type: {type(config)}")
        self._node.get_logger().info("PID configuration updated")

    def _validate_service_response(self, response, service_name: str) -> bool:
        """
        Validate service response based on message type.

        Checks MAVROS-specific fields (mode_sent, success, result) and
        rcl_interfaces SetParameters results.

        Note: MAVLink commands may return ACCEPTED (result=0) while execution
        is asynchronous. The service response indicates command acceptance, not
        completion. See: https://mavlink.io/en/messages/common.html#MAV_RESULT

        Parameters
        ----------
        response : Any
            Service response object.
        service_name : str
            Service name for logging (e.g., "/mavros/cmd/arming").

        Returns
        -------
        bool
            True if response indicates success, False otherwise.
        """
        # MAV_RESULT
        mav_results = {
            0: "ACCEPTED",
            1: "TEMPORARILY_REJECTED",
            2: "DENIED",
            3: "UNSUPPORTED",
            4: "FAILED",
            5: "IN_PROGRESS",
        }

        # SetMode response
        if hasattr(response, "mode_sent"):
            if response.mode_sent:
                self._node.get_logger().info(f"{service_name}: Mode sent")
            else:
                self._node.get_logger().warn(f"{service_name}: Mode not sent")
            return response.mode_sent

        # MAVROS Commands (CommandBool, CommandTOL, CommandLong, CommandHome)
        if hasattr(response, "success") and hasattr(response, "result"):
            res_str = mav_results.get(response.result, f"UNKNOWN={response.result}")
            if response.success:
                self._node.get_logger().info(f"{service_name}: Success (Result: {res_str})")
            else:
                self._node.get_logger().warn(f"{service_name}: Failed (Result: {res_str})")
            return response.success

        # Generic success check
        if hasattr(response, "success"):
            if response.success:
                self._node.get_logger().info(f"{service_name}: Success")
            else:
                self._node.get_logger().warn(f"{service_name}: Failed")
            return response.success

        # SetParameters (rcl_interfaces)
        if hasattr(response, "results"):
            all_success = all(r.successful for r in response.results)
            if all_success:
                param_names = [r.name for r in response.results]
                self._node.get_logger().info(
                    f"{service_name}: Parameters set: {', '.join(param_names)}"
                )
            else:
                reasons = [f"{r.name}: {r.reason}" for r in response.results if not r.successful]
                self._node.get_logger().warn(
                    f"{service_name}: Parameters failed: {', '.join(reasons)}"
                )
            return all_success

        # Unknown response type - log and assume success
        self._node.get_logger().debug(f"{service_name}: Unknown response type, assuming success")
        return True

    def _call_service(
        self,
        service,
        request,
        success_msg: str,
        fail_msg: str,
        sync: bool = False,
        timeout: float = 10.0,
    ):
        """
        Call a ROS2 service with timeout and optional async execution.

        Parameters
        ----------
        service : Client
            ROS2 service client.
        request : SrvTypeRequest
            Service request message.
        success_msg : str
            Message to log on success.
        fail_msg : str
            Message to log on failure.
        sync : bool, default=False
            If True, blocks (spins) until service completes.
            If False, returns immediately (non-blocking).
        timeout : float, default=10.0
            Maximum time in seconds to wait for service availability.

        Returns
        -------
        Any or None
            Service response if sync=True, None if async or on failure.

        Raises
        ------
        TimeoutError
            If service not available within timeout.
        """
        elapsed = 0.0
        wait_interval = 1.0

        while not service.wait_for_service(timeout_sec=wait_interval):
            elapsed += wait_interval
            self._node.get_logger().info(
                f"Service {service.srv_name} not available, waiting... ({elapsed:.0f}s)"
            )
            if elapsed >= timeout:
                self._node.get_logger().error(
                    f"\033[31;1m{fail_msg} - Service {service.srv_name} not available after {timeout}s\033[0m"
                )
                raise TimeoutError(f"Service {service.srv_name} not available after {timeout}s")

        self._node.get_logger().debug(f"Calling service {service.srv_name} | sync={sync}")

        if sync:
            # Use call_async + spin loop to avoid deadlocks
            future = service.call_async(request)
            start_time = self._node.get_clock().now()

            while not future.done():
                rclpy.spin_once(self._node, timeout_sec=0.05)
                if (self._node.get_clock().now() - start_time).nanoseconds / 1e9 > timeout:
                    self._node.get_logger().error(
                        f"\033[31;1m{fail_msg}: Timeout waiting for response\033[0m"
                    )
                    return None

            try:
                result = future.result()
                if result is not None:
                    self._validate_service_response(
                        result, service.srv_name
                    )  # TODO: test the responses from mavros to include in the verification of service
                    self._node.get_logger().info(f"\033[32;1m{success_msg}\033[0m")
                    return result
                else:
                    self._node.get_logger().error(f"\033[31;1m{fail_msg}\033[0m")
                    return None
            except Exception as e:
                self._node.get_logger().error(f"\033[31;1m{fail_msg}: {e}\033[0m")
                return None
        else:
            future = service.call_async(request)

            def _handle_response(future):
                try:
                    result = future.result()
                    if result is not None and self._validate_service_response(
                        result, service.srv_name
                    ):
                        self._node.get_logger().info(f"\033[32;1m{success_msg}\033[0m")
                    else:
                        self._node.get_logger().error(f"\033[31;1m{fail_msg}\033[0m")
                except Exception as e:
                    self._node.get_logger().error(f"\033[31;1m{fail_msg}: {e}\033[0m")

            future.add_done_callback(_handle_response)
            return None


DroneFactory.register("mavros", MavrosDrone.from_config)
