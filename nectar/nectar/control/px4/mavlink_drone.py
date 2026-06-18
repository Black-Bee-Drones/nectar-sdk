"""PX4 drone over a direct pymavlink link: :class:`Px4Drone` on a
:class:`PymavlinkTransport` with PX4 mode encoding.

Mirrors :class:`~nectar.control.px4.mavros_drone.Px4MavrosDrone` (identical
``Px4Drone`` flight semantics, but speaks raw MAVLink instead of MAVROS — no ROS
middleware between the SDK and the FCU

PX4 flight modes are encoded by :class:`Px4ModeCodec` (``MAV_CMD_DO_SET_MODE``
with PX4 ``(main, sub)`` modes from :mod:`nectar.control.px4.modes`), which is
injected into the otherwise firmware-neutral transport.
"""

from typing import Optional

from pymavlink import mavutil
from rclpy.executors import Executor

from nectar.control.config import DroneConfig, Px4MavlinkConfig
from nectar.control.factory import DroneFactory
from nectar.control.mavlink.connection import MavlinkConnection
from nectar.control.mavlink.modes import MavlinkModeCodec
from nectar.control.mavlink.transport import PymavlinkTransport
from nectar.control.px4.drone import Px4Drone
from nectar.control.px4.modes import MODE_TO_PX4, px4_mode_name

_M = mavutil.mavlink


class Px4ModeCodec(MavlinkModeCodec):
    """PX4 flight-mode handling over MAVLink (``MAV_CMD_DO_SET_MODE``)."""

    def set_mode(self, transport, mode: str) -> bool:
        main_sub = MODE_TO_PX4.get(mode.upper())
        if main_sub is None:
            transport.node.get_logger().error(f"Unknown PX4 mode: {mode}")
            return False
        main_mode, sub_mode = main_sub
        # MAV_CMD_DO_SET_MODE: param1=base_mode (custom enabled), param2=main, param3=sub.
        return transport.send_command_long(
            _M.MAV_CMD_DO_SET_MODE,
            float(_M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED),
            float(main_mode),
            float(sub_mode),
        )

    def decode_mode(self, msg) -> str:
        return px4_mode_name(msg.custom_mode)

    @property
    def land_mode(self) -> str:
        return "AUTO.LAND"

    def is_guided(self, mode: str) -> bool:
        return mode == "OFFBOARD"


class Px4MavlinkDrone(Px4Drone):
    """PX4 drone over a direct pymavlink."""

    def __init__(
        self,
        config: Px4MavlinkConfig,
        executor: Optional[Executor] = None,
        connection: Optional[MavlinkConnection] = None,
    ) -> None:
        super().__init__(
            config,
            PymavlinkTransport(connection, mode_codec=Px4ModeCodec()),
            executor,
        )
        self._node.get_logger().info("Px4MavlinkDrone initialized")

    @classmethod
    def from_config(
        cls,
        config: DroneConfig,
        executor: Optional[Executor] = None,
    ) -> "Px4MavlinkDrone":
        """Factory entry point for :class:`DroneFactory`."""
        if not isinstance(config, Px4MavlinkConfig):
            config = Px4MavlinkConfig()
        return cls(config, executor)

    @property
    def connection(self) -> MavlinkConnection:
        """The underlying MAVLink endpoint (shareable with sensor publishers)."""
        return self._transport.connection


DroneFactory.register("px4_mavlink", Px4MavlinkDrone.from_config)
