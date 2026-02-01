from abc import ABC, abstractmethod
from typing import Optional, List

import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.publisher import Publisher
from rclpy.subscription import Subscription
from rclpy.client import Client
from rclpy.callback_groups import ReentrantCallbackGroup

from mirela_sdk.control.types import (
    MoveReference,
    NavigationStrategy,
    RTLStrategy,
)
from mirela_sdk.control.config import DroneConfig
from mirela_sdk.control.exceptions import (
    DriverNotFoundError,
    CapabilityNotSupportedError,
)
from mirela_sdk.control.obstacles.handler import ObstacleManager, ObstacleHandler
from mirela_sdk.control.obstacles.types import ObstacleHandlerConfig
from mirela_sdk.control.protocols import ObstacleDetector
from mirela_sdk.utils.process import ProcessUtils


class BaseDrone(ABC):
    """
    Abstract base class for drone implementations.

    Parameters
    ----------
    config : DroneConfig
        Drone configuration dataclass.
    node : Node
        ROS2 node for communication.

    """

    def __init__(self, config: DroneConfig, node: Node) -> None:
        self._config = config
        self._node = node
        self._connected = False
        self._subscribers: List[Subscription] = []
        self._publishers: List[Publisher] = []
        self._clients: List[Client] = []
        self._callback_group = ReentrantCallbackGroup()
        self._driver_running = False
        self._obstacle_manager = ObstacleManager()

        if config.start_driver:
            self._init_driver()

    @property
    def config(self) -> DroneConfig:
        """Drone configuration object."""
        return self._config

    @property
    def node(self) -> Node:
        """ROS2 node instance used for communication."""
        return self._node

    @property
    def is_ready(self) -> bool:
        """Check if drone is ready for operation (connected and driver running)."""
        return self._connected and self._driver_running

    @property
    def driver_running(self) -> bool:
        """Whether the driver process is currently running."""
        return self._driver_running

    @property
    def driver_session_name(self) -> str:
        """Tmux session name used for the driver process."""
        return self._get_driver_name()

    @property
    def obstacle_manager(self) -> ObstacleManager:
        """Obstacle detection manager for this drone instance."""
        return self._obstacle_manager

    def add_obstacle_detector(
        self,
        name: str,
        detector: ObstacleDetector,
        strategy,
        config: Optional[ObstacleHandlerConfig] = None,
    ) -> None:
        """
        Add obstacle detector with avoidance strategy.

        Creates handler with independent timer for detection updates. Strategy determines
        how drone responds to detected obstacles during navigation.

        Parameters
        ----------
        name : str
            Unique identifier for this detector.
        detector : ObstacleDetector
            Detector implementation (e.g., DepthObstacleDetector).
        strategy : AvoidanceStrategy
            Strategy for obstacle response (e.g., PauseStrategy, SequenceStrategy).
        config : ObstacleHandlerConfig, optional
            Handler configuration including update rate. If None, uses defaults.
        """
        handler = ObstacleHandler(detector, strategy, self._node, config)
        self._obstacle_manager.add(name, handler)
        self._node.get_logger().info(f"Added obstacle detector: {name}")

    def remove_obstacle_detector(self, name: str) -> None:
        """
        Remove obstacle detector and cleanup resources.

        Parameters
        ----------
        name : str
            Detector identifier.
        """
        if self._obstacle_manager.remove(name):
            self._node.get_logger().info(f"Removed obstacle detector: {name}")

    def enable_obstacle_detector(self, name: str) -> None:
        """
        Enable obstacle detector.

        Starts timer-based updates and activates avoidance strategy during navigation.

        Parameters
        ----------
        name : str
            Detector identifier.
        """
        self._obstacle_manager.enable(name)
        self._node.get_logger().info(f"Enabled obstacle detector: {name}")

    def disable_obstacle_detector(self, name: str) -> None:
        """
        Disable obstacle detector.

        Stops timer-based updates and deactivates avoidance strategy.

        Parameters
        ----------
        name : str
            Detector identifier.
        """
        self._obstacle_manager.disable(name)
        self._node.get_logger().info(f"Disabled obstacle detector: {name}")

    def enable_all_obstacle_detectors(self) -> None:
        """Enable all registered obstacle detectors."""
        self._obstacle_manager.enable_all()

    def disable_all_obstacle_detectors(self) -> None:
        """Disable all registered obstacle detectors."""
        self._obstacle_manager.disable_all()

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to drone hardware or driver.

        Returns
        -------
        bool
            True if connection successful.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and cleanup resources."""
        pass

    @abstractmethod
    def arm(self) -> bool:
        """
        Arm motors for flight.

        Returns
        -------
        bool
            True if arming successful.
        """
        pass

    @abstractmethod
    def disarm(self) -> bool:
        """
        Force disarm motors.

        Always sends force disarm command to bypass safety checks.

        Returns
        -------
        bool
            True if disarming successful.
        """
        pass

    @abstractmethod
    def takeoff(self, altitude: float) -> bool:
        """
        Execute takeoff to specified altitude.

        Parameters
        ----------
        altitude : float
            Target altitude in meters.

        Returns
        -------
        bool
            True if takeoff successful.
        """
        pass

    @abstractmethod
    def land(self, timeout: float = 30.0) -> bool:
        """
        Execute landing at current position.

        Parameters
        ----------
        timeout : float, default=30.0
            Maximum time for operation in seconds.

        Returns
        -------
        bool
            True if landing successful (motors disarmed).
        """
        pass

    @abstractmethod
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
        Command velocity-based movement.

        Parameters
        ----------
        vx : float (m/s), default=0.0
            (+) Move forward
            (-) Move backward
        vy : float (m/s), default=0.0
            (+) Move left
            (-) Move right
        vz : float (m/s), default=0.0
            (+) Move up
            (-) Move down
        vyaw : float (rad/s), default=0.0
            (+) Rotate counter clockwise
            (-) Rotate clockwise
        duration : float (s), optional
            Execution time. If None, command is continuous.
        reference : MoveReference (enum), default=BODY
            BODY: relative to current orientation (body-fixed frame)
            WORLD: relative to world frame (NED frame)

            Note: TAKEOFF reference is not applicable for velocity control.
        """
        pass

    @abstractmethod
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
    ) -> bool:
        """
        Navigate to target position.

        The movement is relative to the drone's current orientation:
        - x-axis: forward/backward relative to drone's heading
        - y-axis: right/left relative to drone's heading
        - z-axis: up/down relative to current altitude

        Parameters
        ----------
        x : Optional[float]
            Distance to move forward (+) or backward (-) in meters.

            If None, disables movement in x direction.

        y : Optional[float]
            Distance to move left (+) or right (-) in meters.

            If None, disables movement in y direction.

        z : Optional[float]
            Distance to move up (+) or down (-) in meters.

            If None altitude control is disabled.

        yaw : Optional[float]
            Target yaw in degrees.

            If None, disables yaw control.

        reference : MoveReference (enum), default=BODY
            Reference frame for movement:
            - BODY: relative to current orientation
            - WORLD: relative to world frame (NED frame)
            - TAKEOFF: relative to takeoff position

        timeout : Optional[float], default=60.0
            Maximum navigation time in seconds. None for no timeout.

        precision : float, default=0.2
            Arrival threshold in meters.

        strategy : NavigationStrategy (enum), default=PID
            Navigation algorithm:
            - PID: velocity-based control with feedback loop
            - SETPOINT: direct position setpoint publishing

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but takeoff position not set.
        """
        pass

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
        Navigate to GPS coordinates.

        Parameters
        ----------
        latitude : float
            Target latitude in degrees (WGS84).
        longitude : float
            Target longitude in degrees (WGS84).
        altitude : float, optional
            Target altitude above ground in meters. None uses current altitude.
        heading : float, optional
            Target heading in degrees (0 = North, clockwise). None uses current heading.
        timeout : float, optional, default=60.0
            Maximum navigation time in seconds.
        precision : float, default=0.5
            Arrival threshold in meters.
        strategy : NavigationStrategy, default=PID
            Navigation algorithm.

        Returns
        -------
        bool
            True if waypoint reached.

        Raises
        ------
        CapabilityNotSupportedError
            If drone doesn't support GPS navigation.
        """
        raise CapabilityNotSupportedError("GPS navigation", self._config.name)

    @abstractmethod
    def emergency_stop(self) -> None:
        """Execute emergency stop (force motor shutdown)."""
        pass

    def set_home(self) -> bool:
        """
        Set current position as home.

        Returns
        -------
        bool
            True if successful.
        """
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
            Transit altitude in meters. None uses current altitude.
        precision : float, default=0.2
            Arrival threshold for PID strategy in meters.
        strategy : RTLStrategy, default=PID
            RTL algorithm (PID navigates to takeoff, ARDUPILOT triggers FCU RTL mode).
        land : bool, default=True
            Execute landing after reaching home.

        Returns
        -------
        bool
            True if RTL successful.
        """
        return False

    @abstractmethod
    def _get_driver_name(self) -> str:
        """
        Return driver node name for status checking.

        Returns
        -------
        str
            ROS2 node name of the driver.
        """
        pass

    @abstractmethod
    def _start_driver(self) -> bool:
        """
        Start driver process for this drone.

        Returns
        -------
        bool
            True if driver started successfully.
        """
        pass

    @abstractmethod
    def _get_driver_command(self) -> str:
        """
        Return command to start the driver process.

        Returns
        -------
        str
            Shell command to start the driver.
        """
        pass

    def _init_driver(self) -> None:
        """
        Initialize driver lifecycle.

        Checks if driver is already running, starts if needed, and waits for driver node
        to appear in ROS2 graph.

        Raises
        ------
        DriverNotFoundError
            If driver fails to start or times out.
        """
        driver_name = self._get_driver_name()
        self._node.get_logger().info(f"Initializing driver: {driver_name}")

        if self.check_driver_status():
            self._node.get_logger().info(f"Driver {driver_name} already running")
            self._driver_running = True
            return

        if not self._start_driver():
            raise DriverNotFoundError(driver_name)

        self._wait_for_driver(timeout=10.0)
        self._driver_running = True

    def check_driver_status(self) -> bool:
        """
        Check if driver node is running in ROS2 graph.

        Uses ProcessUtils for efficient node checking without blocking.

        Returns
        -------
        bool
            True if driver node found in ROS2 graph.
        """
        driver_name = self._get_driver_name()
        is_running = ProcessUtils.is_node_running(driver_name, timeout=2.0)
        self._driver_running = is_running
        return is_running

    def _wait_for_driver(self, timeout: float = 10.0) -> bool:
        """
        Wait for driver node to appear in ROS2 graph.

        Parameters
        ----------
        timeout : float, default=10.0
            Maximum wait time in seconds.

        Returns
        -------
        bool
            True if driver found within timeout.
        """
        driver_name = self._get_driver_name()
        if ProcessUtils.wait_for_node(driver_name, timeout=timeout, poll_interval=0.5):
            self._node.get_logger().info(f"Driver {driver_name} started")
            self._driver_running = True
            return True

        self._node.get_logger().warn(f"Timeout waiting for driver {driver_name}")
        self._driver_running = False
        return False

    def start_driver_process(self) -> bool:
        """
        Start the driver process.

        Convenience method that starts the driver and waits for it to be ready.

        Returns
        -------
        bool
            True if driver started successfully.
        """
        if self.check_driver_status():
            self._node.get_logger().info("Driver already running")
            return True

        if self._start_driver():
            return self._wait_for_driver(timeout=15.0)
        return False

    def stop_driver_process(self) -> bool:
        """
        Stop the driver process.

        Kills the tmux session running the driver.

        Returns
        -------
        bool
            True if driver stopped successfully.
        """
        driver_name = self._get_driver_name()
        success = ProcessUtils.kill_process(driver_name)
        if success:
            self._driver_running = False
            self._node.get_logger().info(f"Driver {driver_name} stopped")
        return success

    def _create_subscriber(
        self,
        msg_type: type,
        topic: str,
        callback: callable,
        qos: QoSProfile | int,
    ) -> Subscription:
        """
        Create ROS2 subscriber with reentrant callback group.

        Parameters
        ----------
        msg_type : type
            ROS2 message type.
        topic : str
            Topic name.
        callback : callable
            Callback function.
        qos : QoSProfile | int
            Quality of service profile or history depth.

        Returns
        -------
        Subscription
            Created subscription object.
        """
        sub = self._node.create_subscription(
            msg_type,
            topic,
            callback,
            qos,
            callback_group=self._callback_group,
        )
        self._subscribers.append(sub)
        return sub

    def _create_publisher(
        self,
        msg_type: type,
        topic: str,
        qos: QoSProfile | int,
    ) -> Publisher:
        """
        Create ROS2 publisher with reentrant callback group.

        Parameters
        ----------
        msg_type : type
            ROS2 message type.
        topic : str
            Topic name.
        qos : QoSProfile | int
            Quality of service profile or history depth.

        Returns
        -------
        Publisher
            Created publisher object.
        """
        pub = self._node.create_publisher(
            msg_type,
            topic,
            qos,
            callback_group=self._callback_group,
        )
        self._publishers.append(pub)
        return pub

    def _create_client(self, srv_type: type, service_name: str) -> Client:
        """
        Create ROS2 service client with reentrant callback group.

        Parameters
        ----------
        srv_type : type
            ROS2 service type.
        service_name : str
            Service name.

        Returns
        -------
        Client
            Created client object.
        """
        client = self._node.create_client(
            srv_type,
            service_name,
            callback_group=self._callback_group,
        )
        self._clients.append(client)
        return client

    def delay(self, seconds: float) -> None:
        """
        Delay with ROS spinning.

        Maintains ROS communication during delay with spin_once.

        Parameters
        ----------
        seconds : float
            Delay duration in seconds.
        """
        duration = Duration(seconds=seconds)
        start_time = self._node.get_clock().now()

        while (self._node.get_clock().now() - start_time) < duration:
            rclpy.spin_once(self._node, timeout_sec=0.1)

    def cleanup(self) -> None:
        """
        Cleanup all ROS2 resources.

        Destroys all subscribers, publishers, clients, and obstacle detectors.
        Called automatically on object deletion.
        """
        self._obstacle_manager.cleanup()

        for sub in self._subscribers:
            self._node.destroy_subscription(sub)
        for pub in self._publishers:
            self._node.destroy_publisher(pub)
        for client in self._clients:
            self._node.destroy_client(client)

        self._subscribers.clear()
        self._publishers.clear()
        self._clients.clear()

    def __del__(self) -> None:
        self.cleanup()
