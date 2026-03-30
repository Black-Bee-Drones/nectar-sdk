import shlex
import subprocess
from dataclasses import dataclass
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
    """

    name: str
    node_patterns: List[str]
    session_name: str


DRIVER_INFO: Dict[str, DriverInfo] = {
    "mavros": DriverInfo(
        name="MAVROS",
        node_patterns=["mavros_node", "mavros"],
        session_name="mavros_node",
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
