"""PX4 drone over native uXRCE-DDS: :class:`Px4Drone` on a :class:`Px4DdsTransport`.

All PX4 flight semantics (OFFBOARD streaming, arm sequence, AUTO.LAND/AUTO.RTL)
live in :class:`~nectar.control.px4.drone.Px4Drone`; this class only wires up the
native uXRCE-DDS transport (px4_msgs over the Micro XRCE-DDS Agent). The offboard
pump in ``Px4Drone`` already republishes ``OffboardControlMode`` + setpoint each
tick, exactly as PX4's native offboard control requires.

Requires ``px4_msgs`` in the workspace and a running ``MicroXRCEAgent``.
"""

from typing import Optional

from rclpy.executors import Executor

from nectar.control.config import DroneConfig, Px4DdsConfig, require_config
from nectar.control.factory import DroneFactory
from nectar.control.px4.dds_transport import Px4DdsTransport
from nectar.control.px4.drone import Px4Drone


class Px4DdsDrone(Px4Drone):
    """
    PX4 drone over the native uXRCE-DDS bridge.

    Parameters
    ----------
    config : Px4DdsConfig
        PX4/uXRCE-DDS-specific configuration.
    executor : Executor, optional
        ROS 2 executor to register this drone's node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    """

    def __init__(
        self,
        config: Px4DdsConfig,
        executor: Optional[Executor] = None,
    ) -> None:
        super().__init__(config, Px4DdsTransport(), executor)
        self._node.get_logger().info("Px4DdsDrone initialized")

    @classmethod
    def from_config(
        cls,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> "Px4DdsDrone":
        """Factory entry point for :class:`DroneFactory`."""
        return cls(require_config(config, Px4DdsConfig), executor)


DroneFactory.register("px4_dds", Px4DdsDrone.from_config)
