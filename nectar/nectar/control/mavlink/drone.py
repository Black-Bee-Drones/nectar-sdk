"""MAVLink drone: :class:`ArduPilotDrone` over a :class:`PymavlinkTransport`.

Same ArduPilot vehicle and flight logic as :class:`~nectar.control.mavros.drone.MavrosDrone`,
but the transport owns a direct pymavlink link
"""

from typing import Optional

from rclpy.executors import Executor

from nectar.control.ardupilot.drone import ArduPilotDrone
from nectar.control.config import DroneConfig, MavlinkConfig, require_config
from nectar.control.factory import DroneFactory
from nectar.control.mavlink.connection import MavlinkConnection
from nectar.control.mavlink.transport import PymavlinkTransport


class MavlinkDrone(ArduPilotDrone):
    """Direct-pymavlink ArduPilot drone.

    Parameters
    ----------
    config : MavlinkConfig
        MAVLink-specific configuration (pymavlink connection string, baud, ...).
    executor : Executor, optional
        ROS 2 executor to register this drone's node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    connection : MavlinkConnection, optional
        Pre-built endpoint to share (e.g. when a rangefinder publisher already
        owns the link). When ``None``, the transport builds one from ``config``.
    """

    def __init__(
        self,
        config: MavlinkConfig,
        executor: Optional[Executor] = None,
        connection: Optional[MavlinkConnection] = None,
    ) -> None:
        super().__init__(config, PymavlinkTransport(connection), executor)
        self._node.get_logger().info("MavlinkDrone initialized")

    @classmethod
    def from_config(
        cls,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> "MavlinkDrone":
        """Factory entry point for :class:`DroneFactory`."""
        return cls(require_config(config, MavlinkConfig), executor)

    @property
    def connection(self) -> MavlinkConnection:
        """The underlying MAVLink endpoint (shareable with sensor publishers)."""
        return self._transport.connection


DroneFactory.register("mavlink", MavlinkDrone.from_config)
