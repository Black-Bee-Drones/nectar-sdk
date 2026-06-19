import shlex
import subprocess
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from nectar.utils.process import ProcessUtils


class DriverStatus(Enum):
    UNKNOWN = auto()
    RUNNING = auto()
    STOPPED = auto()
    STARTING = auto()
    ERROR = auto()


@dataclass
class DriverInfo:
    """
    Information about a drone driver.

    Attributes
    ----------
    name : str
        Human-readable driver name.
    node_patterns : List[str]
        ROS2 node name patterns to check for driver status.
    session_name : str
        Tmux session name for the driver process.
    topic_patterns : List[str]
        ROS2 topic name patterns that signal the driver is up, used when
        ``detect_via == "topic"`` (e.g. PX4's ``/fmu/*`` once the uXRCE-DDS
        agent and the FCU client have connected).
    driverless : bool, default=False
        True when the transport opens the FCU link inside the drone instance
        (no separate driver process), e.g. the direct pymavlink backends.
    detect_via : str, default="node"
        How to detect a running driver: ``"node"`` queries the ROS 2 node
        graph for ``node_patterns``; ``"topic"`` queries the topic graph for
        ``topic_patterns`` (for processes exposed only through their data
        topics, e.g. the Micro XRCE-DDS Agent, which is not a ROS 2 node).
    """

    name: str
    node_patterns: List[str]
    session_name: str
    topic_patterns: List[str] = field(default_factory=list)
    driverless: bool = False
    detect_via: str = "node"


DRIVER_INFO: Dict[str, DriverInfo] = {
    "mavros": DriverInfo(
        name="MAVROS",
        node_patterns=["mavros_node", "mavros"],
        session_name="mavros_node",
    ),
    "mavlink": DriverInfo(
        name="Direct MAVLink",
        node_patterns=[],
        session_name="",
        driverless=True,
    ),
    "px4": DriverInfo(
        name="MAVROS (PX4)",
        node_patterns=["mavros_node", "mavros"],
        session_name="mavros_node",
    ),
    "px4_mavlink": DriverInfo(
        name="Direct MAVLink (PX4)",
        node_patterns=[],
        session_name="",
        driverless=True,
    ),
    "px4_dds": DriverInfo(
        name="Micro XRCE-DDS Agent",
        node_patterns=[],
        session_name="micro_xrce_agent",
        topic_patterns=["/fmu/"],
        detect_via="topic",
    ),
    "bebop": DriverInfo(
        name="Bebop Driver",
        node_patterns=["bebop_driver"],
        session_name="bebop_driver",
    ),
    "crazyflie": DriverInfo(
        name="Crazyflie Server",
        node_patterns=["crazyflie_server"],
        session_name="crazyflie_server",
    ),
}


def build_driver_command(
    drone_type: str,
    *,
    connection_string: str = "",
    ip: str = "",
    backend: str = "",
    mocap: bool = False,
    agent_port: int = 8888,
) -> str:
    """
    Build the shell command that launches a drone's driver process.

    Single source of truth for the driver launch commands shared by the SDK
    and the GUI.

    Parameters
    ----------
    drone_type : str
        Drone type identifier (e.g. ``"mavros"``, ``"px4"``, ``"px4_dds"``).
    connection_string : str, optional
        FCU connection string / ``fcu_url`` for the MAVROS backends.
    ip : str, optional
        Drone IP address (Bebop).
    backend : str, optional
        Crazyswarm2 backend (Crazyflie).
    mocap : bool, default=False
        Whether to enable motion capture (Crazyflie).
    agent_port : int, default=8888
        UDP port for the Micro XRCE-DDS Agent (``px4_dds``).

    Returns
    -------
    str
        Command to run in a tmux session.

    Raises
    ------
    ValueError
        If the drone type has no driver process (driverless or unknown).
    """
    key = drone_type.lower()
    if key == "mavros":
        conn = connection_string or "serial:///dev/ttyUSB0:921600"
        return f"ros2 launch mavros apm.launch fcu_url:={conn}"
    if key == "px4":
        conn = connection_string or "udp://:14540@127.0.0.1:14580"
        return f"ros2 launch mavros px4.launch fcu_url:={conn}"
    if key == "px4_dds":
        return f"MicroXRCEAgent udp4 -p {agent_port}"
    if key == "crazyflie":
        command = f"ros2 launch crazyflie launch.py backend:={backend or 'cpp'}"
        if not mocap:
            command += " mocap:=False"
        return command
    if key == "bebop":
        return f"ros2 launch ros2_bebop_driver bebop_node_launch.xml ip:={ip or '192.168.42.1'}"
    raise ValueError(f"No driver command for drone type: '{drone_type}'")


def is_driver_running(drone_type: str, timeout: float = 2.0) -> bool:
    """
    Check whether a drone's driver is currently up.

    Dispatches on the driver's ``detect_via`` strategy: a ROS 2 node-graph
    lookup for node-based drivers, or a topic-graph lookup for transports that
    surface only through their data topics (e.g. the Micro XRCE-DDS Agent,
    detected by PX4's ``/fmu/*`` topics). Topic detection is independent of how
    the agent was launched (GUI, ``make sim-bridge PROTOCOL=dds``, or manually),
    so an externally started agent is recognized too.

    Parameters
    ----------
    drone_type : str
        Drone type identifier.
    timeout : float, default=2.0
        Maximum time for the ROS 2 graph query.

    Returns
    -------
    bool
        True if the driver is running. Always False for driverless or
        unknown types.
    """
    info = DRIVER_INFO.get(drone_type.lower())
    if info is None or info.driverless:
        return False
    if info.detect_via == "topic":
        topics = ProcessUtils.get_ros2_topics(timeout)
        return any(pattern in topic for pattern in info.topic_patterns for topic in topics)
    nodes = ProcessUtils.get_ros2_nodes(timeout)
    return any(pattern in node for pattern in info.node_patterns for node in nodes)


class DriverMonitor:
    """
    Monitor and manage drone driver processes.

    Provides utilities for checking driver status using ROS2 node graph
    and managing driver lifecycle through ProcessUtils.

    Parameters
    ----------
    driver_type : str
        Type of driver to monitor ('mavros' or 'bebop').

    Attributes
    ----------
    status : DriverStatus
        Current driver status.
    last_error : Optional[str]
        Last error message if status is ERROR.
    """

    def __init__(self, driver_type: str) -> None:
        self._driver_type = driver_type.lower()
        self._info = DRIVER_INFO.get(self._driver_type)
        self._status = DriverStatus.UNKNOWN
        self._last_error: Optional[str] = None
        self._callbacks: List[Callable[[DriverStatus], None]] = []

    @property
    def status(self) -> DriverStatus:
        return self._status

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def is_running(self) -> bool:
        return self._status == DriverStatus.RUNNING

    @property
    def driver_info(self) -> Optional[DriverInfo]:
        return self._info

    def add_status_callback(self, callback: Callable[[DriverStatus], None]) -> None:
        """
        Register callback for status changes.

        Parameters
        ----------
        callback : Callable[[DriverStatus], None]
            Function called when driver status changes.
        """
        self._callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[DriverStatus], None]) -> None:
        """
        Remove registered status callback.

        Parameters
        ----------
        callback : Callable[[DriverStatus], None]
            Previously registered callback.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_status_change(self, new_status: DriverStatus) -> None:
        if new_status != self._status:
            self._status = new_status
            for callback in self._callbacks:
                try:
                    callback(new_status)
                except Exception:
                    # Don't let callback errors affect status notification
                    pass

    def check_status(self) -> DriverStatus:
        """
        Check current driver status by querying ROS2 node graph.

        Returns
        -------
        DriverStatus
            Current driver status.
        """
        if self._info is None:
            self._notify_status_change(DriverStatus.ERROR)
            self._last_error = f"Unknown driver type: {self._driver_type}"
            return self._status

        try:
            nodes = self._get_ros2_nodes()
            for pattern in self._info.node_patterns:
                for node in nodes:
                    if pattern in node:
                        self._notify_status_change(DriverStatus.RUNNING)
                        self._last_error = None
                        return self._status

            self._notify_status_change(DriverStatus.STOPPED)
            self._last_error = None
            return self._status

        except Exception as e:
            self._notify_status_change(DriverStatus.ERROR)
            self._last_error = str(e)
            return self._status

    def _get_ros2_nodes(self) -> List[str]:
        """
        Get list of running ROS2 nodes.

        Returns
        -------
        List[str]
            List of node names.
        """
        try:
            result = subprocess.run(
                shlex.split("ros2 node list"),
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return []
        except subprocess.TimeoutExpired:
            return []
        except Exception:
            return []

    def start_driver(self, command: str) -> bool:
        """
        Start driver process.

        Parameters
        ----------
        command : str
            Shell command to start the driver.

        Returns
        -------
        bool
            True if driver started successfully.
        """
        if self._info is None:
            self._last_error = f"Unknown driver type: {self._driver_type}"
            return False

        self._notify_status_change(DriverStatus.STARTING)

        success = ProcessUtils.start_process(command, self._info.session_name)
        if success:
            self._last_error = None
            return True
        else:
            self._notify_status_change(DriverStatus.ERROR)
            self._last_error = "Failed to start driver process"
            return False

    def stop_driver(self) -> bool:
        """
        Stop driver process.

        Returns
        -------
        bool
            True if driver stopped successfully.
        """
        if self._info is None:
            return False

        success = ProcessUtils.kill_process(self._info.session_name)
        if success:
            self._notify_status_change(DriverStatus.STOPPED)
            self._last_error = None
        return success

    def restart_driver(self, command: str) -> bool:
        """
        Restart driver process.

        Parameters
        ----------
        command : str
            Shell command to start the driver.

        Returns
        -------
        bool
            True if driver restarted successfully.
        """
        self.stop_driver()
        return self.start_driver(command)

    @staticmethod
    def get_available_drivers() -> List[str]:
        """
        Get list of supported driver types.

        Returns
        -------
        List[str]
            Available driver type identifiers.
        """
        return list(DRIVER_INFO.keys())

    @staticmethod
    def is_ros2_available() -> bool:
        """
        Check if ROS2 environment is available.

        Returns
        -------
        bool
            True if ROS2 commands are accessible.
        """
        try:
            result = subprocess.run(
                shlex.split("ros2 --help"),
                capture_output=True,
                timeout=2.0,
            )
            return result.returncode == 0
        except Exception:
            return False
