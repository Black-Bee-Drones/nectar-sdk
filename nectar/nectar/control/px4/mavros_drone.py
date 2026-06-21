"""PX4 drone over MAVROS: :class:`Px4Drone` on a :class:`MavrosTransport`.

this class only wires up the MAVROS transport,
which reaches PX4 through ``mavros px4.launch``.
"""

from typing import Optional

from rclpy.executors import Executor

from nectar.control.config import DroneConfig, Px4MavrosConfig, require_config
from nectar.control.factory import DroneFactory
from nectar.control.mavros.transport import MavrosTransport
from nectar.control.px4.drone import Px4Drone


class Px4MavrosDrone(Px4Drone):
    """
    PX4 drone implementation over MAVROS.

    Parameters
    ----------
    config : Px4MavrosConfig
        PX4/MAVROS-specific configuration.
    executor : Executor, optional
        ROS 2 executor to register this drone's node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    """

    def __init__(
        self,
        config: Px4MavrosConfig,
        executor: Optional[Executor] = None,
    ) -> None:
        super().__init__(config, MavrosTransport(), executor)
        self._node.get_logger().info("Px4MavrosDrone initialized")

    @classmethod
    def from_config(
        cls,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> "Px4MavrosDrone":
        """Factory entry point for :class:`DroneFactory`."""
        return cls(require_config(config, Px4MavrosConfig), executor)


DroneFactory.register("px4", Px4MavrosDrone.from_config)
