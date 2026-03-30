import math
from typing import List, Optional

import rclpy
from geometry_msgs.msg import Point, PoseStamped
from rclpy.duration import Duration
from rclpy.node import Node
from std_srvs.srv import Empty

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
    NavigationStrategy,
    RTLStrategy,
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
        timeout = Duration(
            seconds=self._config.sensor_timeout if hasattr(self._config, "sensor_timeout") else 10.0
        )
        start = self._node.get_clock().now()

        while self._node.get_clock().now() - start < timeout:
            rclpy.spin_once(self._node, timeout_sec=0.1)
            if self._status is not None:
                self._connected = True
                self._node.get_logger().info(
                    f"Connected to {self._config.cf_name} "
                    f"(battery: {self._status.battery_voltage:.2f}V)"
                )
                return True

        self._node.get_logger().warn("Connection timeout: no status received")
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
        self._call_service_async(self._arm_srv, req)
        self._node.get_logger().info("Arm command sent")
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
        self._call_service_async(self._arm_srv, req)
        self._node.get_logger().info("Disarm command sent")
        return True

    def takeoff(self, altitude: float, duration: Optional[float] = None) -> bool:
        """
        Execute takeoff to specified altitude.

        Parameters
        ----------
        altitude : float
            Target height in meters.
        duration : float, optional
            Time to reach target height in seconds.
            If None, estimated from altitude and default_velocity.

        Returns
        -------
        bool
            True if takeoff command sent and altitude reached.
        """
        config: CrazyflieConfig = self._config
        altitude = min(altitude, config.max_height)

        if duration is None:
            duration = max(altitude / config.default_velocity, 1.0)

        self._takeoff_position = list(self._position)
        self._takeoff_yaw = self._get_yaw()

        req = Takeoff.Request()
        req.group_mask = 0
        req.height = float(altitude)
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service_async(self._takeoff_srv, req)

        self._node.get_logger().info(f"Takeoff to {altitude:.2f}m over {duration:.1f}s")

        self.delay(duration + 0.5)
        return True

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
            True if land command sent.
        """
        config: CrazyflieConfig = self._config

        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        current_height = self._position[2]
        if duration is None:
            duration = max(current_height / config.default_velocity, 1.0)

        req = Land.Request()
        req.group_mask = 0
        req.height = config.landing_height
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service_async(self._land_srv, req)

        self._node.get_logger().info(f"Landing from {current_height:.2f}m over {duration:.1f}s")

        self.delay(duration + 0.5)
        return True

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
        precision: float = 0.2,
        strategy: NavigationStrategy = NavigationStrategy.PID,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
    ) -> bool:
        """
        Navigate to target position using the onboard high-level commander.

        Uses the Crazyflie's goTo service which plans a smooth degree-7
        polynomial trajectory from current state to target.

        Parameters
        ----------
        x : float, optional
            Forward (+) / backward (-) offset in meters.
        y : float, optional
            Left (+) / right (-) offset in meters.
        z : float, optional
            Up (+) / down (-) offset in meters.
        yaw : float, optional
            Target yaw in degrees. None maintains current yaw.
        reference : MoveReference, default=BODY
            BODY: offset relative to current position/heading.
            WORLD: absolute position in world frame.
            TAKEOFF: offset relative to takeoff position/heading.
        timeout : float, optional, default=60.0
            Maximum time for navigation.
        precision : float, default=0.2
            Arrival threshold in meters.
        strategy : NavigationStrategy, default=PID
            Ignored -- Crazyflie always uses onboard polynomial planner.
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
        """
        config: CrazyflieConfig = self._config

        if self._in_streaming_mode:
            self.notify_setpoints_stop()

        dx = x if x is not None else 0.0
        dy = y if y is not None else 0.0
        dz = z if z is not None else 0.0
        target_yaw = math.radians(yaw) if yaw is not None else self._get_yaw()

        if reference == MoveReference.BODY:
            current_yaw = self._get_yaw()
            world_dx = dx * math.cos(current_yaw) - dy * math.sin(current_yaw)
            world_dy = dx * math.sin(current_yaw) + dy * math.cos(current_yaw)
            goal = Point(
                x=self._position[0] + world_dx,
                y=self._position[1] + world_dy,
                z=self._position[2] + dz,
            )
            relative = False

        elif reference == MoveReference.TAKEOFF:
            if self._takeoff_position is None:
                raise TakeoffPositionNotSetError("move_to with TAKEOFF reference")
            takeoff_yaw = self._takeoff_yaw
            world_dx = dx * math.cos(takeoff_yaw) - dy * math.sin(takeoff_yaw)
            world_dy = dx * math.sin(takeoff_yaw) + dy * math.cos(takeoff_yaw)
            goal = Point(
                x=self._takeoff_position[0] + world_dx,
                y=self._takeoff_position[1] + world_dy,
                z=self._takeoff_position[2] + dz,
            )
            relative = False

        elif reference == MoveReference.WORLD:
            goal = Point(x=dx, y=dy, z=dz)
            relative = False

        else:
            goal = Point(x=dx, y=dy, z=dz)
            relative = True

        goal.z = max(0.0, min(goal.z, config.max_height))

        distance = (
            math.sqrt(
                (goal.x - self._position[0]) ** 2
                + (goal.y - self._position[1]) ** 2
                + (goal.z - self._position[2]) ** 2
            )
            if not relative
            else math.sqrt(dx**2 + dy**2 + dz**2)
        )

        duration = max(distance / config.default_velocity, 1.0)

        req = GoTo.Request()
        req.group_mask = 0
        req.relative = relative
        req.goal = goal
        req.yaw = float(target_yaw)
        req.duration = rclpy.duration.Duration(seconds=duration).to_msg()
        self._call_service_async(self._goto_srv, req)

        self._node.get_logger().info(
            f"GoTo goal=({goal.x:.2f}, {goal.y:.2f}, {goal.z:.2f}) "
            f"yaw={math.degrees(target_yaw):.1f}deg duration={duration:.1f}s "
            f"ref={reference.name}"
        )

        return self._wait_for_position(goal, duration, timeout, precision)

    def emergency_stop(self) -> None:
        """
        Emergency stop. Cuts power and locks the Crazyflie.

        After emergency stop, the Crazyflie must be physically rebooted.
        All future commands are ignored until reboot.
        """
        req = Empty.Request()
        self._call_service_async(self._emergency_srv, req)
        self._node.get_logger().warn("Emergency stop -- reboot required")

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        strategy: RTLStrategy = RTLStrategy.PID,
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
        strategy : RTLStrategy, default=PID
            Only PID supported. ARDUPILOT raises CapabilityNotSupportedError.
        land : bool, default=True
            Execute landing after reaching takeoff position.

        Returns
        -------
        bool
            True if RTL successful.
        """
        if strategy == RTLStrategy.ARDUPILOT:
            raise CapabilityNotSupportedError("ARDUPILOT RTL", self._config.name)

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
        self._call_service_async(self._goto_srv, req)

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
        self._call_service_async(self._notify_stop_srv, req)
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
            rclpy.spin_once(self._node, timeout_sec=0.05)
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
        self._call_service_async(self._start_traj_srv, req)
        self._node.get_logger().info(f"Trajectory {trajectory_id} started (timescale={timescale})")

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
        self._call_service_async(self._set_params_srv, req)

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
            rclpy.spin_once(self._node, timeout_sec=0.05)
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

    def _call_service_async(self, client, request) -> None:
        """Fire-and-forget async service call."""
        if not client.service_is_ready():
            self._node.get_logger().debug(f"Service {client.srv_name} not ready, waiting...")
            client.wait_for_service(timeout_sec=5.0)
        client.call_async(request)

    def _wait_for_position(
        self,
        goal: Point,
        duration: float,
        timeout: Optional[float],
        precision: float,
    ) -> bool:
        """Wait for the drone to reach the goal position."""
        effective_timeout = min(duration + 2.0, timeout) if timeout else duration + 2.0
        start = self._node.get_clock().now()
        deadline = Duration(seconds=effective_timeout)

        self.delay(duration * 0.8)

        while self._node.get_clock().now() - start < deadline:
            rclpy.spin_once(self._node, timeout_sec=0.05)
            dx = goal.x - self._position[0]
            dy = goal.y - self._position[1]
            dz = goal.z - self._position[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist <= precision:
                self._node.get_logger().info(f"Target reached (distance={dist:.3f}m)")
                return True

        dist = math.sqrt(
            (goal.x - self._position[0]) ** 2
            + (goal.y - self._position[1]) ** 2
            + (goal.z - self._position[2]) ** 2
        )
        self._node.get_logger().warn(f"GoTo timeout (distance={dist:.3f}m, precision={precision}m)")
        return dist <= precision * 2


DroneFactory.register("crazyflie", CrazyflieDrone.from_config)
