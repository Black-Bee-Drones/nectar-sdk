"""MAVROS drone: :class:`ArduPilotDrone` over a :class:`MavrosTransport`.

All flight/navigation behavior lives in
:class:`~nectar.control.ardupilot.drone.ArduPilotDrone`; this class only wires
up the MAVROS transport.
"""

from typing import Optional

from rclpy.executors import Executor

from nectar.control.ardupilot.drone import ArduPilotDrone
from nectar.control.config import DroneConfig, MavrosConfig, require_config
from nectar.control.factory import DroneFactory
from nectar.control.mavros.transport import MavrosTransport


class MavrosDrone(ArduPilotDrone):
    """
    MAVROS drone implementation for ArduPilot/PX4 flight controllers.

    Parameters
    ----------
    config : MavrosConfig
        MAVROS-specific configuration.
    executor : Executor, optional
        ROS 2 executor to register this drone's node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    """

    def __init__(
        self,
        config: MavrosConfig,
        executor: Optional[Executor] = None,
    ) -> None:
        super().__init__(config, MavrosTransport(), executor)
        self._node.get_logger().info("MavrosDrone initialized")

    @classmethod
    def from_config(
        cls,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> "MavrosDrone":
        """Factory entry point for :class:`DroneFactory`."""
        return cls(require_config(config, MavrosConfig), executor)


DroneFactory.register("mavros", MavrosDrone.from_config)
