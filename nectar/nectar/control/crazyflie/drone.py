import math
from typing import List, Optional

import rclpy
from geometry_msgs.msg import Point, PoseStamped
from rclpy.duration import Duration
from rclpy.node import Node
from std_srvs.srv import Empty
from tf2_msgs.msg import TFMessage

from nectar.control.base import BaseDrone
from nectar.control.config import CrazyflieConfig, DroneConfig
from nectar.control.exceptions import (
    CapabilityNotSupportedError,
    TakeoffPositionNotSetError,
)
from nectar.control.factory import DroneFactory
from nectar.control.types import (
    AltitudeSource,
    MoveReference,
    NavigationMethod,
    RTLMethod,
)
from nectar.utils.process import ProcessUtils

try:
    from crazyflie_interfaces.msg import FullState, Position, Status
    from crazyflie_interfaces.srv import (
        Arm,
        GoTo,
        Land,
        NotifySetpointsStop,
        StartTrajectory,
        Takeoff,
        UploadTrajectory,
    )

    _CF_INTERFACES_AVAILABLE = True
except ImportError:
    _CF_INTERFACES_AVAILABLE = False

try:
    from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
    from rcl_interfaces.srv import GetParameters, SetParameters

    _RCL_INTERFACES_AVAILABLE = True
except ImportError:
    _RCL_INTERFACES_AVAILABLE = False


class CrazyflieDrone(BaseDrone):
    """
    Crazyflie 2.x drone implementation via Crazyswarm2.

    Communicates with the Crazyflie through the crazyflie_server ROS 2 node,
    which handles radio communication, parameter syncing, and logging. Supports
    the high-level commander (takeoff, land, goTo) and streaming setpoints
    (cmdFullState, cmdPosition).

    Parameters
    ----------
    config : CrazyflieConfig
        Crazyflie-specific configuration.
    node : Node
        ROS2 node for communication.
    """

    # Status supervisor_info bitmask constants
    SUPERVISOR_CAN_BE_ARMED = 1
    SUPERVISOR_IS_ARMED = 2
    SUPERVISOR_AUTO_ARM = 4
    SUPERVISOR_CAN_FLY = 8
    SUPERVISOR_IS_FLYING = 16
    SUPERVISOR_IS_TUMBLED = 32
    SUPERVISOR_IS_LOCKED = 64

    def __init__(self, config: CrazyflieConfig, node: Node) -> None:
        if not _CF_INTERFACES_AVAILABLE:
            raise ImportError(
                "crazyflie_interfaces not found. Install Crazyswarm2: "
                "sudo apt install ros-${ROS_DISTRO}-crazyflie ros-${ROS_DISTRO}-crazyflie-interfaces"
            )

        super().__init__(config, node)

        self._status: Optional[Status] = None
        self._pose: Optional[PoseStamped] = None
        self._position: List[float] = [0.0, 0.0, 0.0]
        self._takeoff_position: Optional[List[float]] = None
        self._takeoff_yaw: float = 0.0
        self._in_streaming_mode = False
        self._tf_received = False

        prefix = f"/{config.cf_name}"
        self._prefix = prefix

        self._setup_services(prefix)
        self._setup_subscribers(prefix)
        self._setup_publishers(prefix)
        self._setup_param_services()

        self._node.get_logger().info(f"CrazyflieDrone initialized: {config.cf_name} ({config.uri})")

    @classmethod
    def from_config(cls, config: DroneConfig, node: Node) -> "CrazyflieDrone":
        """
        Factory method for DroneFactory registration.

        Parameters
        ----------
        config : DroneConfig
            Configuration (converted to CrazyflieConfig if needed).
        node : Node
            ROS2 node.

        Returns
        -------
        CrazyflieDrone
            Configured drone instance.
        """
        if not isinstance(config, CrazyflieConfig):
            config = CrazyflieConfig()
        return cls(config, node)

    # Properties

    @property
    def is_armed(self) -> Optional[bool]:
        """Check if motors are armed."""
        if self._status is None:
            return None
        return bool(self._status.supervisor_info & self.SUPERVISOR_IS_ARMED)

    @property
    def is_flying(self) -> bool:
        """Whether the Crazyflie is currently in flight."""
        if self._status is None:
            return False
        return bool(self._status.supervisor_info & self.SUPERVISOR_IS_FLYING)

    @property
    def is_tumbled(self) -> bool:
        """Whether the Crazyflie has detected a tumble (crash)."""
        if self._status is None:
            return False
        return bool(self._status.supervisor_info & self.SUPERVISOR_IS_TUMBLED)

    @property
    def can_fly(self) -> bool:
        """Whether the Crazyflie is ready for flight commands."""
        if self._status is None:
            return False
        return bool(self._status.supervisor_info & self.SUPERVISOR_CAN_FLY)

    @property
    def battery_voltage(self) -> Optional[float]:
        """Battery voltage in volts."""
        if self._status is None:
            return None
        return self._status.battery_voltage

    @property
    def rssi(self) -> Optional[int]:
        """Radio signal strength indicator (dBm)."""
        if self._status is None:
            return None
        return self._status.rssi

    @property
    def pose(self) -> Optional[PoseStamped]:
        """Current estimated pose from the Crazyflie's state estimator."""
        return self._pose

    @property
    def position(self) -> List[float]:
        """Current position as [x, y, z] in meters."""
        return self._position

    @property
    def height(self) -> float:
        """Current height above ground in meters."""
        return self._position[2]

    # Setup

    def _setup_services(self, prefix: str) -> None:
        self._emergency_srv = self._create_client(Empty, f"{prefix}/emergency")
        self._takeoff_srv = self._create_client(Takeoff, f"{prefix}/takeoff")
        self._land_srv = self._create_client(Land, f"{prefix}/land")
        self._goto_srv = self._create_client(GoTo, f"{prefix}/go_to")
        self._upload_traj_srv = self._create_client(UploadTrajectory, f"{prefix}/upload_trajectory")
        self._start_traj_srv = self._create_client(StartTrajectory, f"{prefix}/start_trajectory")
        self._notify_stop_srv = self._create_client(
            NotifySetpointsStop, f"{prefix}/notify_setpoints_stop"
        )
        self._arm_srv = self._create_client(Arm, f"{prefix}/arm")

    def _setup_subscribers(self, prefix: str) -> None:
        self._create_subscriber(Status, f"{prefix}/status", self._on_status, 10)
        self._create_subscriber(PoseStamped, f"{prefix}/pose", self._on_pose, 10)
        self._create_subscriber(TFMessage, "/tf", self._on_tf, 10)

    def _setup_publishers(self, prefix: str) -> None:
        self._cmd_full_state_pub = self._create_publisher(FullState, f"{prefix}/cmd_full_state", 1)
        self._cmd_position_pub = self._create_publisher(Position, f"{prefix}/cmd_position", 1)

    def _setup_param_services(self) -> None:
        if _RCL_INTERFACES_AVAILABLE:
            self._set_params_srv = self._create_client(
                SetParameters, "/crazyflie_server/set_parameters"
            )
            self._get_params_srv = self._create_client(
                GetParameters, "/crazyflie_server/get_parameters"
            )

    def _on_status(self, msg: "Status") -> None:
        self._status = msg

    def _on_pose(self, msg: PoseStamped) -> None:
        self._pose = msg
        self._position = [
            msg.pose.position.x,
            msg.pose.position.y,
            msg.pose.position.z,
        ]

    def _on_tf(self, msg: TFMessage) -> None:
        cf_name = self._config.cf_name
        for transform in msg.transforms:
            if transform.child_frame_id == cf_name:
                t = transform.transform.translation
                self._position = [t.x, t.y, t.z]
                if self._pose is None:
                    self._pose = PoseStamped()
                    self._pose.header = transform.header
                self._pose.pose.position.x = t.x
                self._pose.pose.position.y = t.y
                self._pose.pose.position.z = t.z
                self._pose.pose.orientation = transform.transform.rotation
                self._tf_received = True
                break

    # Driver

    def _get_driver_name(self) -> str:
        return "crazyflie_server"

    def _get_driver_command(self) -> str:
        config: CrazyflieConfig = self._config
        cmd = "ros2 launch crazyflie launch.py"
        if config.backend:
            cmd += f" backend:={config.backend}"
        if not config.mocap:
            cmd += " mocap:=False"
        return cmd

    def _start_driver(self) -> bool:
        driver_name = self._get_driver_name()
        if ProcessUtils.is_node_running(driver_name, timeout=2.0):
            self._node.get_logger().info(f"Driver node {driver_name} already running")
            return True
        cmd = self._get_driver_command()
        return ProcessUtils.start_process(cmd, driver_name)

    # Operations

    def connect(self) -> bool:
        """
        Verify connection to the Crazyflie via the server.

        Waits for status messages to confirm the server is communicating
        with the Crazyflie hardware.

        Returns
        -------
        bool
            True if status messages are being received.
        """
        timeout = Duration(seconds=self._config.sensor_timeout)
        start = self._node.get_clock().now()

        while self._node.get_clock().now() - start < timeout:
            self._wait(0.1)
            if self._status is not None:
                self._connected = True
                self._node.get_logger().info(
                    f"Connected to {self._config.cf_name} "
                    f"(battery: {self._status.battery_voltage:.2f}V)"
                )
                return True
            if self._tf_received:
                self._connected = True
                self._node.get_logger().info(
                    f"Connected to {self._config.cf_name} (simulation via /tf)"
                )
                return True

        self._node.get_logger().warn("Connection timeout: no status or tf received")
        return False

    def disconnect(self) -> None:
        """Disconnect and cleanup resources."""
        self.cleanup()

    def arm(self) -> bool:
        """
        Arm the Crazyflie.

        For CF 2.1 (brushed), arming happens automatically on takeoff.
        For Bolt-based (brushless), this starts the motors.

        Returns
        -------
        bool
            True if arm command sent.
        """
        req = Arm.Request()
        req.arm = True
        self._call_service(self._arm_srv, req, success_msg="Armed", sync=False)
        return True

    def disarm(self) -> bool:
        """
        Disarm the Crazyflie.

        Returns
        -------
        bool
            True if disarm command sent.
        """
        req = Arm.Request()
        req.arm = False
        self._call_service(self._arm_srv, req, success_msg="Disarmed", sync=False)
        return True

    def takeoff(
        self,
        altitude: float,
        duration: Optional[float] = None,
        timeout: float = 30.0,
        precision: float = 0.12,
    ) -> bool:
        """
        Execute takeoff to specified altitude.

        Parameters
        ----------
        altitude : float
            Target height in meters (must be > 0).
        duration : float, optional
            Time to reach target height in seconds.
            If None, estimated from altitude and default_velocity.
        timeout : float, default=30.0
            Maximum time to wait for altitude convergence.
        precision : float, default=0.12
            Altitude precision in meters. Takeoff succeeds when
            height >= altitude - precision.

        Returns
        -------
        bool
            True if takeoff command sent and altitude reached.
        """
        config: CrazyflieConfig = self._config

        if altitude <= 0.0:
            self._node.get_logger().error(
                f"Invalid takeoff altitude: {altitude:.2f}m (must be > 0)"
            )
            return False

        if altitude > config.max_height:
            self._node.get_logger().warn(
                f"Altitude {altitude:.2f}m exceeds max_height {config.max_height:.2f}m, clamping"
            )
            altitude = config.max_height

        if duration is None:
            duration = max(altitude / config.default_velocity, 2.0)

        initial_height = self.height
        self._takeoff_position = list(self._position)
        self._takeoff_yaw = self._get_yaw()

        self._node.get_logger().info(
            f"Takeoff to {altitude:.2f}m over {duration:.1f}s "
            f"(initial height={initial_height:.2f}m)"
        )

        req = Takeoff.Request()
        req.group_mask = 0
        req.height = float(altitude)
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service(
            self._takeoff_srv,
            req,
            fail_msg="Takeoff command failed",
            sync=True,
        )

        threshold = altitude - precision
        start = self._node.get_clock().now()
        deadline = Duration(seconds=timeout)

        while self._node.get_clock().now() - start < deadline:
            self._wait(0.05)
            if self.height >= threshold:
                self.delay(1.0)
                self._node.get_logger().info(
                    f"Takeoff complete (height={self.height:.2f}m, target={altitude:.2f}m)"
                )
                return True

        height_gain = self.height - initial_height
        self._node.get_logger().warn(
            f"Takeoff timeout (height={self.height:.2f}m, target={altitude:.2f}m, "
            f"gained={height_gain:.2f}m)"
        )
        return height_gain >= altitude * 0.5

    def land(self, timeout: float = 30.0, duration: Optional[float] = None) -> bool:
        """
        Execute landing at current position.

        Parameters
        ----------
        timeout : float, default=30.0
            Maximum time for operation in seconds.
        duration : float, optional
            Time for descent in seconds.
            If None, estimated from current height and default_velocity.

        Returns
        -------
        bool
            True if landing completed (height near ground).
        """
        config: CrazyflieConfig = self._config

        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        current_height = self.height
        landed_threshold = config.landing_height + 0.05

        if current_height <= landed_threshold:
            self._node.get_logger().info(
                f"Already near ground (height={current_height:.3f}m), skipping land"
            )
            return True

        if duration is None:
            duration = max(current_height / config.default_velocity, 1.0)

        self._node.get_logger().info(f"Landing from {current_height:.2f}m over {duration:.1f}s")

        req = Land.Request()
        req.group_mask = 0
        req.height = config.landing_height
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service(
            self._land_srv,
            req,
            fail_msg="Land command failed",
            sync=True,
        )

        start = self._node.get_clock().now()
        deadline = Duration(seconds=timeout)

        while self._node.get_clock().now() - start < deadline:
            self._wait(0.05)
            if self.height <= landed_threshold:
                self.delay(0.5)
                self._node.get_logger().info(f"Landing complete (height={self.height:.3f}m)")
                return True

        self._node.get_logger().warn(f"Landing timeout (height={self.height:.3f}m)")
        return self.height <= 0.1

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
        Command velocity-based movement via full-state streaming setpoints.

        Publishes to cmd_full_state with the desired velocity. Switches the
        Crazyflie to low-level streaming mode. Call notify_setpoints_stop()
        before using high-level commands (takeoff, land, goTo) again.

        Parameters
        ----------
        vx : float (m/s), default=0.0
            Forward (+) / backward (-) velocity.
        vy : float (m/s), default=0.0
            Left (+) / right (-) velocity.
        vz : float (m/s), default=0.0
            Up (+) / down (-) velocity.
        vyaw : float (rad/s), default=0.0
            Yaw rate. Counter-clockwise positive.
        duration : float (s), optional
            If specified, sends commands for this duration at ~50Hz.
            If None, publishes a single command.
        reference : MoveReference, default=BODY
            BODY: velocities relative to current heading.
            TAKEOFF: velocities in takeoff heading frame.
            WORLD: velocities in world frame.
        """
        self._in_streaming_mode = True

        if reference == MoveReference.BODY:
            yaw = self._get_yaw()
            world_vx = vx * math.cos(yaw) - vy * math.sin(yaw)
            world_vy = vx * math.sin(yaw) + vy * math.cos(yaw)
        elif reference == MoveReference.TAKEOFF:
            if self._takeoff_position is None:
                raise TakeoffPositionNotSetError("move_velocity with TAKEOFF reference")
            yaw = self._takeoff_yaw
            world_vx = vx * math.cos(yaw) - vy * math.sin(yaw)
            world_vy = vx * math.sin(yaw) + vy * math.cos(yaw)
        else:
            world_vx = vx
            world_vy = vy

        if duration is None:
            self._publish_full_state_velocity(world_vx, world_vy, vz, vyaw)
        else:
            rate = 1.0 / 50
            start = self._node.get_clock().now()
            dur = Duration(seconds=duration)
            while self._node.get_clock().now() - start < dur:
                if reference == MoveReference.BODY:
                    yaw = self._get_yaw()
                    world_vx = vx * math.cos(yaw) - vy * math.sin(yaw)
                    world_vy = vx * math.sin(yaw) + vy * math.cos(yaw)
                self._publish_full_state_velocity(world_vx, world_vy, vz, vyaw)
                self.delay(rate)
            self._publish_full_state_velocity(0.0, 0.0, 0.0, 0.0)

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        yaw: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
        timeout: Optional[float] = 60.0,
        precision: float = 0.1,
        method: NavigationMethod = NavigationMethod.POSITION,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
    ) -> bool:
        """
        Navigate to target position using the onboard high-level commander.

        Uses the Crazyflie's goTo service which plans a smooth degree-7
        polynomial trajectory from current state to target.

        Coordinate semantics:

        - BODY: offsets relative to current position and heading.
          x/y=None disables that axis (no offset). z=None maintains current
          height. yaw is degrees relative to current heading.
        - TAKEOFF: offsets relative to takeoff position and heading.
          x/y=None preserves current position on that axis (does NOT go to
          takeoff position). z is absolute height above ground (z=None
          maintains current height, z <= 0 is rejected for safety). yaw is
          degrees relative to takeoff heading.
        - WORLD: absolute world-frame coordinates.
          None values preserve current position/yaw on that axis.

        Parameters
        ----------
        x : float, optional
            Forward (+) / backward (-) offset in meters.
        y : float, optional
            Left (+) / right (-) offset in meters.
        z : float, optional
            Up (+) / down (-) offset in meters (BODY) or absolute height (TAKEOFF).
        yaw : float, optional
            Target yaw in degrees relative to reference heading.
            None maintains current yaw.
        reference : MoveReference, default=BODY
            Reference frame for movement.
        timeout : float, optional, default=60.0
            Maximum time for navigation.
        precision : float, default=0.1
            Arrival threshold in meters.
        method : NavigationMethod, default=POSITION
            Only POSITION is supported (onboard polynomial planner).
            PID, PID_EKF, POSITION_GLOBAL raise CapabilityNotSupportedError.
        altitude_source : AltitudeSource, default=AUTO
            Ignored -- Crazyflie uses fused ToF/flow altitude.

        Returns
        -------
        bool
            True if target reached within precision.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but takeoff position not set.
        CapabilityNotSupportedError
            If method is not POSITION.
        """
        if method != NavigationMethod.POSITION:
            raise CapabilityNotSupportedError(f"{method.name} navigation", self._config.name)
        config: CrazyflieConfig = self._config

        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        if reference == MoveReference.TAKEOFF and self._takeoff_position is None:
            raise TakeoffPositionNotSetError("move_to with TAKEOFF reference")

        if z is not None:
            z = self._check_altitude_safety(z, reference)

        goal, target_yaw = self._compute_goal(x, y, z, yaw, reference)
        goal.z = max(0.0, min(goal.z, config.max_height))

        distance = self._distance_to(goal)
        yaw_diff = abs(self._normalize_angle(target_yaw - self._get_yaw()))

        if distance < precision * 0.5 and yaw_diff < math.radians(3):
            self._node.get_logger().info(
                f"Already at target (distance={distance:.3f}m, "
                f"yaw_diff={math.degrees(yaw_diff):.1f} deg)"
            )
            return True

        yaw_duration = yaw_diff / math.radians(60)
        duration = max(distance / config.default_velocity, yaw_duration, 1.0)

        self._node.get_logger().info(
            f"move_to: x={x} y={y} z={z} yaw={yaw} ref={reference.name} "
            f"precision={precision}m | goal=({goal.x:.2f}, {goal.y:.2f}, {goal.z:.2f}) "
            f"distance={distance:.2f}m duration={duration:.1f}s"
        )

        req = GoTo.Request()
        req.group_mask = 0
        req.relative = False
        req.goal = goal
        req.yaw = float(target_yaw)
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service(
            self._goto_srv,
            req,
            fail_msg="GoTo command failed",
            sync=True,
        )

        return self._wait_for_position(goal, duration, timeout, precision)

    def emergency_stop(self) -> None:
        """
        Emergency stop. Cuts power and locks the Crazyflie.

        After emergency stop, the Crazyflie must be physically rebooted.
        All future commands are ignored until reboot.
        """
        req = Empty.Request()
        self._call_service(self._emergency_srv, req, sync=False)
        self._node.get_logger().warn("Emergency stop -- reboot required")

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        method: RTLMethod = RTLMethod.NAVIGATE,
        land: bool = True,
    ) -> bool:
        """
        Return to takeoff position.

        Parameters
        ----------
        altitude : float, optional
            Transit height in meters. If specified, adjusts height first.
        precision : float, default=0.2
            Arrival threshold in meters.
        method : RTLMethod, default=NAVIGATE
            Only NAVIGATE supported. NATIVE raises CapabilityNotSupportedError.
        land : bool, default=True
            Execute landing after reaching takeoff position.

        Returns
        -------
        bool
            True if RTL successful.
        """
        if method == RTLMethod.NATIVE:
            raise CapabilityNotSupportedError("NATIVE RTL", self._config.name)

        if self._takeoff_position is None:
            raise TakeoffPositionNotSetError("RTL")

        if altitude is not None:
            self._node.get_logger().info(f"RTL: adjusting height to {altitude:.2f}m")
            self.move_to(z=altitude, reference=MoveReference.TAKEOFF, precision=precision)

        self._node.get_logger().info("RTL: navigating to takeoff position")
        self.move_to(
            x=0.0,
            y=0.0,
            z=0.0,
            reference=MoveReference.TAKEOFF,
            precision=precision,
        )

        if land:
            self._node.get_logger().info("RTL: landing")
            self.land()

        return True

    # specific features

    def go_to(
        self,
        goal: List[float],
        yaw: float,
        duration: float,
        relative: bool = False,
    ) -> None:
        """
        Direct access to the Crazyflie goTo high-level command.

        Plans a smooth polynomial trajectory to the goal position.

        Parameters
        ----------
        goal : list of 3 floats
            Target position [x, y, z] in meters.
        yaw : float
            Target yaw angle in radians.
        duration : float
            Time to reach the goal in seconds.
        relative : bool, default=False
            If True, goal is relative to current position.
        """
        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        req = GoTo.Request()
        req.group_mask = 0
        req.relative = relative
        req.goal = Point(x=float(goal[0]), y=float(goal[1]), z=float(goal[2]))
        req.yaw = float(yaw)
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service(self._goto_srv, req, success_msg="GoTo sent", sync=True)

    def cmd_full_state(
        self,
        pos: List[float],
        vel: List[float],
        acc: List[float],
        yaw: float,
        omega: List[float],
    ) -> None:
        """
        Send a streaming full-state setpoint.

        Switches to low-level mode. Call notify_setpoints_stop() before
        using high-level commands again.

        Parameters
        ----------
        pos : list of 3 floats
            Position [x, y, z] in meters.
        vel : list of 3 floats
            Velocity [vx, vy, vz] in m/s.
        acc : list of 3 floats
            Acceleration [ax, ay, az] in m/s^2.
        yaw : float
            Yaw angle in radians.
        omega : list of 3 floats
            Angular velocity [wx, wy, wz] in rad/s.
        """
        try:
            import rowan
        except ImportError as exc:
            raise ImportError("rowan is required for cmd_full_state: pip install rowan") from exc

        self._in_streaming_mode = True
        msg = FullState()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = "/world"
        msg.pose.position.x = pos[0]
        msg.pose.position.y = pos[1]
        msg.pose.position.z = pos[2]
        msg.twist.linear.x = vel[0]
        msg.twist.linear.y = vel[1]
        msg.twist.linear.z = vel[2]
        msg.acc.x = acc[0]
        msg.acc.y = acc[1]
        msg.acc.z = acc[2]
        q = rowan.from_euler(0, 0, yaw)
        msg.pose.orientation.w = q[0]
        msg.pose.orientation.x = q[1]
        msg.pose.orientation.y = q[2]
        msg.pose.orientation.z = q[3]
        msg.twist.angular.x = omega[0]
        msg.twist.angular.y = omega[1]
        msg.twist.angular.z = omega[2]
        self._cmd_full_state_pub.publish(msg)

    def cmd_position(self, pos: List[float], yaw: float = 0.0) -> None:
        """
        Send a streaming position setpoint.

        Switches to low-level mode. Call notify_setpoints_stop() before
        using high-level commands again.

        Parameters
        ----------
        pos : list of 3 floats
            Position [x, y, z] in meters.
        yaw : float, default=0.0
            Yaw angle in radians.
        """
        self._in_streaming_mode = True
        msg = Position()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = "/world"
        msg.x = float(pos[0])
        msg.y = float(pos[1])
        msg.z = float(pos[2])
        msg.yaw = float(yaw)
        self._cmd_position_pub.publish(msg)

    def notify_setpoints_stop(self, remain_valid_ms: int = 100) -> None:
        """
        Signal end of streaming setpoints.

        Must be called after streaming commands (cmd_full_state, cmd_position,
        move_velocity) and before using high-level commands (takeoff, land,
        move_to, go_to).

        Parameters
        ----------
        remain_valid_ms : int, default=100
            Milliseconds the last setpoint remains valid.
        """
        req = NotifySetpointsStop.Request()
        req.remain_valid_millisecs = remain_valid_ms
        req.group_mask = 0
        self._call_service(self._notify_stop_srv, req, sync=False)
        self._in_streaming_mode = False
        self.delay(0.1)

    def upload_trajectory(self, trajectory_id: int, pieces: list) -> None:
        """
        Upload a piecewise polynomial trajectory.

        Parameters
        ----------
        trajectory_id : int
            ID number for this trajectory.
        pieces : list
            List of TrajectoryPolynomialPiece messages.
        """
        req = UploadTrajectory.Request()
        req.trajectory_id = trajectory_id
        req.piece_offset = 0
        req.pieces = pieces

        future = self._upload_traj_srv.call_async(req)
        start = self._node.get_clock().now()
        timeout = Duration(seconds=10.0)
        while not future.done():
            self._wait(0.05)
            if self._node.get_clock().now() - start > timeout:
                self._node.get_logger().error("Upload trajectory timeout")
                return
        self._node.get_logger().info(f"Trajectory {trajectory_id} uploaded")

    def start_trajectory(
        self,
        trajectory_id: int,
        timescale: float = 1.0,
        reverse: bool = False,
        relative: bool = True,
    ) -> None:
        """
        Begin executing a previously uploaded trajectory.

        Parameters
        ----------
        trajectory_id : int
            ID number from upload_trajectory().
        timescale : float, default=1.0
            Duration scale factor (2.0 = twice as slow).
        reverse : bool, default=False
            Execute trajectory backwards in time.
        relative : bool, default=True
            Shift trajectory to begin at current position.
        """
        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        req = StartTrajectory.Request()
        req.group_mask = 0
        req.trajectory_id = trajectory_id
        req.timescale = float(timescale)
        req.reversed = reverse
        req.relative = relative
        self._call_service(
            self._start_traj_srv,
            req,
            success_msg=f"Trajectory {trajectory_id} started (timescale={timescale})",
            sync=False,
        )

    def set_firmware_param(self, name: str, value) -> None:
        """
        Set a Crazyflie firmware parameter via the server.

        Parameters
        ----------
        name : str
            Parameter name (e.g., "stabilizer.controller", "ring.effect").
        value : int or float
            Parameter value.
        """
        if not _RCL_INTERFACES_AVAILABLE:
            self._node.get_logger().error("rcl_interfaces not available")
            return

        config: CrazyflieConfig = self._config
        param_name = f"{config.cf_name}.params.{name}"

        if isinstance(value, float):
            param_value = ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=value)
        else:
            param_value = ParameterValue(
                type=ParameterType.PARAMETER_INTEGER, integer_value=int(value)
            )

        req = SetParameters.Request()
        req.parameters = [Parameter(name=param_name, value=param_value)]
        self._call_service(self._set_params_srv, req, sync=False)

    def get_firmware_param(self, name: str):
        """
        Get a Crazyflie firmware parameter value.

        Parameters
        ----------
        name : str
            Parameter name (e.g., "stabilizer.controller").

        Returns
        -------
        int or float or None
            Parameter value, or None on failure.
        """
        if not _RCL_INTERFACES_AVAILABLE:
            self._node.get_logger().error("rcl_interfaces not available")
            return None

        config: CrazyflieConfig = self._config
        param_name = f"{config.cf_name}.params.{name}"

        req = GetParameters.Request()
        req.names = [param_name]

        future = self._get_params_srv.call_async(req)
        start = self._node.get_clock().now()
        timeout = Duration(seconds=5.0)
        while not future.done():
            self._wait(0.05)
            if self._node.get_clock().now() - start > timeout:
                self._node.get_logger().error(f"Get param {name} timeout")
                return None

        try:
            result = future.result()
            val = result.values[0]
            if val.type == ParameterType.PARAMETER_INTEGER:
                return val.integer_value
            elif val.type == ParameterType.PARAMETER_DOUBLE:
                return val.double_value
            return None
        except (RuntimeError, IndexError, AttributeError) as e:
            self._node.get_logger().error(f"Get param {name} failed: {e}")
            return None

    def set_group_mask(self, group_mask: int) -> None:
        """
        Set group mask for broadcast commands (swarm coordination).

        Parameters
        ----------
        group_mask : int
            8-bit bitmask for group membership (0 = respond to all broadcasts).
        """
        self.set_firmware_param("hlCommander.groupmask", group_mask)

    # Internal helpers

    def _get_yaw(self) -> float:
        """Extract yaw from current pose quaternion."""
        if self._pose is None:
            return 0.0
        q = self._pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def _publish_full_state_velocity(self, vx: float, vy: float, vz: float, vyaw: float) -> None:
        """Publish a full-state setpoint with velocity only (hold current position concept via velocity)."""
        msg = FullState()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.header.frame_id = "/world"
        msg.pose.position.x = self._position[0]
        msg.pose.position.y = self._position[1]
        msg.pose.position.z = self._position[2]
        msg.twist.linear.x = vx
        msg.twist.linear.y = vy
        msg.twist.linear.z = vz
        yaw = self._get_yaw()
        msg.pose.orientation.w = math.cos(yaw / 2.0)
        msg.pose.orientation.x = 0.0
        msg.pose.orientation.y = 0.0
        msg.pose.orientation.z = math.sin(yaw / 2.0)
        msg.twist.angular.x = 0.0
        msg.twist.angular.y = 0.0
        msg.twist.angular.z = vyaw
        self._cmd_full_state_pub.publish(msg)

    def _wait_for_position(
        self,
        goal: Point,
        duration: float,
        timeout: Optional[float],
        precision: float,
    ) -> bool:
        """Wait for the drone to reach the goal position.

        Spins during the polynomial trajectory execution (``duration``), then
        actively polls until the target is reached or ``timeout`` expires.
        """
        effective_timeout = timeout if timeout else duration + 10.0
        start = self._node.get_clock().now()
        deadline = Duration(seconds=effective_timeout)
        duration_deadline = Duration(seconds=duration)
        last_log = start
        log_interval = Duration(seconds=2.0)

        while self._node.get_clock().now() - start < duration_deadline:
            self._wait(0.05)

        while self._node.get_clock().now() - start < deadline:
            self._wait(0.05)
            dist = self._distance_to(goal)

            if dist <= precision:
                self.delay(0.3)
                self._node.get_logger().info(
                    f"Target reached (distance={dist:.3f}m) at "
                    f"({self._position[0]:.2f}, {self._position[1]:.2f}, {self._position[2]:.2f})"
                )
                return True

            now = self._node.get_clock().now()
            if now - last_log >= log_interval:
                elapsed = (now - start).nanoseconds / 1e9
                self._node.get_logger().debug(
                    f"Navigating... distance={dist:.3f}m elapsed={elapsed:.1f}s"
                )
                last_log = now

        dist = self._distance_to(goal)
        self._node.get_logger().warn(
            f"GoTo timeout (distance={dist:.3f}m, precision={precision}m) at "
            f"({self._position[0]:.2f}, {self._position[1]:.2f}, {self._position[2]:.2f})"
        )
        return dist <= precision * 3

    def _distance_to(self, goal: Point) -> float:
        """Euclidean distance from current position to goal."""
        return math.sqrt(
            (goal.x - self._position[0]) ** 2
            + (goal.y - self._position[1]) ** 2
            + (goal.z - self._position[2]) ** 2
        )

    def _compute_goal(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
    ) -> tuple:
        """Compute absolute goal position and yaw for the goTo command.

        Follows the same coordinate semantics as MAVROS
        ``TargetComputer.compute_local_target``:

        - BODY: offsets rotated by current yaw, added to current position.
          None axes produce zero offset (hold current).
        - TAKEOFF: offsets rotated by takeoff yaw, added to takeoff position.
          None axes preserve the drone's current position on that axis by
          computing the equivalent offset from takeoff.
        - WORLD: absolute coordinates. None axes preserve current position.

        Parameters
        ----------
        x, y, z : float, optional
            Movement offsets or absolute coordinates depending on reference.
        yaw : float, optional
            Yaw in degrees relative to the reference heading.
        reference : MoveReference
            Coordinate frame.

        Returns
        -------
        tuple[Point, float]
            (goal, target_yaw) in world frame.
        """
        current_yaw = self._get_yaw()

        if reference == MoveReference.BODY:
            ref_yaw = current_yaw
            dx = x if x is not None else 0.0
            dy = y if y is not None else 0.0
            world_dx = dx * math.cos(ref_yaw) - dy * math.sin(ref_yaw)
            world_dy = dx * math.sin(ref_yaw) + dy * math.cos(ref_yaw)
            goal = Point(
                x=self._position[0] + world_dx,
                y=self._position[1] + world_dy,
                z=self._position[2] + (z if z is not None else 0.0),
            )
            target_yaw = ref_yaw + math.radians(yaw) if yaw is not None else current_yaw

        elif reference == MoveReference.TAKEOFF:
            ref_yaw = self._takeoff_yaw
            tkp = self._takeoff_position
            cos_r = math.cos(ref_yaw)
            sin_r = math.sin(ref_yaw)

            if x is not None:
                x_off = x
            else:
                dxw = self._position[0] - tkp[0]
                dyw = self._position[1] - tkp[1]
                x_off = cos_r * dxw + sin_r * dyw

            if y is not None:
                y_off = y
            else:
                dxw = self._position[0] - tkp[0]
                dyw = self._position[1] - tkp[1]
                y_off = -sin_r * dxw + cos_r * dyw

            world_dx = x_off * cos_r - y_off * sin_r
            world_dy = x_off * sin_r + y_off * cos_r

            goal = Point(
                x=tkp[0] + world_dx,
                y=tkp[1] + world_dy,
                z=z if z is not None else self._position[2],
            )
            target_yaw = ref_yaw + math.radians(yaw) if yaw is not None else current_yaw

        else:  # WORLD
            goal = Point(
                x=x if x is not None else self._position[0],
                y=y if y is not None else self._position[1],
                z=z if z is not None else self._position[2],
            )
            target_yaw = math.radians(yaw) if yaw is not None else current_yaw

        return goal, self._normalize_angle(target_yaw)

    def _check_altitude_safety(self, z: float, reference: MoveReference) -> Optional[float]:
        """Reject z values that would produce a target altitude at or below ground.

        Mirrors MAVROS ``MavrosDrone._check_altitude_safety``.

        Parameters
        ----------
        z : float
            Altitude parameter from ``move_to``.
        reference : MoveReference
            Movement reference frame.

        Returns
        -------
        float or None
            Original z if safe, None if target altitude would be <= 0.
        """
        if reference == MoveReference.TAKEOFF:
            if z <= 0:
                self._node.get_logger().warn(
                    f"z={z} with TAKEOFF reference targets altitude <= 0. "
                    "Ignoring z to prevent ground collision."
                )
                return None
        else:
            if self.height + z <= 0:
                self._node.get_logger().warn(
                    f"z={z} from current height {self.height:.2f}m targets "
                    f"{self.height + z:.2f}m (<= 0). Ignoring z to prevent ground collision."
                )
                return None
        return z

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        return (angle + math.pi) % (2 * math.pi) - math.pi


DroneFactory.register("crazyflie", CrazyflieDrone.from_config)
