"""Transport abstraction for the vehicle core."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Union

from nectar.control.vehicle.types import (
    Attitude,
    DistanceReading,
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    TargetFrame,
    VehicleState,
)

if TYPE_CHECKING:
    from nectar.control.vehicle.drone import VehicleDrone


class VehicleTransport(ABC):
    """Abstract FCU transport: telemetry in, commands/setpoints out."""

    # Lifecycle

    def attach(self, drone: "VehicleDrone") -> None:
        """Bind the transport to its drone (and ROS node) before ``start()``.

        Stores the drone so the transport can create ROS entities on
        ``drone.node`` and log through it. Subclasses may override to capture
        extra references but should call ``super().attach(drone)``.
        """
        self._drone = drone

    @abstractmethod
    def start(self) -> None:
        """Begin receiving telemetry (subscribers / RX timer) and TX housekeeping."""

    @abstractmethod
    def close(self) -> None:
        """Tear down all resources created by :meth:`start`."""

    @abstractmethod
    def driver_name(self) -> str:
        """ROS node name of the backing driver, or ``""`` if there is none."""

    @abstractmethod
    def driver_command(self) -> str:
        """Shell command that launches the driver, or ``""`` if not applicable."""

    @abstractmethod
    def start_driver(self) -> bool:
        """Start the backing driver process; ``True`` if running/started."""

    # Telemetry

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether the FCU link is up."""

    @property
    @abstractmethod
    def state(self) -> VehicleState:
        """Connection / arming / flight-mode summary."""

    @property
    @abstractmethod
    def local_pose(self) -> Optional[LocalPose]:
        """EKF-fused local pose (ENU), or ``None`` if not yet received."""

    @property
    @abstractmethod
    def vision_pose(self) -> Optional[LocalPose]:
        """External-vision pose (ENU), or ``None``."""

    @property
    @abstractmethod
    def gps(self) -> Optional[GeoPoint]:
        """Global position fix, or ``None``."""

    @property
    @abstractmethod
    def heading(self) -> Optional[float]:
        """Compass heading in degrees (NED, 0=North), or ``None``."""

    @property
    @abstractmethod
    def rel_alt(self) -> Optional[float]:
        """Altitude above home in meters, or ``None``."""

    @property
    @abstractmethod
    def rangefinder(self) -> Optional[float]:
        """Downward rangefinder distance in meters, or ``None``."""

    @property
    def distance_sensors(self) -> Dict[int, DistanceReading]:
        """Most recent reading per sensor id, any orientation.

        Snapshot of every distance sensor the vehicle reports. Empty when the
        transport exposes none. The downward sensor used for altitude remains
        available via :attr:`rangefinder`. Optional; defaults to empty.
        """
        return {}

    @property
    def attitude(self) -> Optional[Attitude]:
        """Vehicle attitude, or ``None``. Optional; defaults to ``None``."""
        return None

    # Commands

    @abstractmethod
    def set_mode(self, mode: str) -> bool:
        """Set the FCU flight mode (e.g. ``"GUIDED"``)."""

    @abstractmethod
    def arm(self) -> bool:
        """Arm the motors."""

    @abstractmethod
    def disarm(self, force: bool = True) -> bool:
        """Disarm the motors (force bypasses safety checks)."""

    @abstractmethod
    def command_takeoff(self, altitude: float) -> bool:
        """Issue a takeoff command to ``altitude`` meters (must be GUIDED+armed)."""

    @abstractmethod
    def command_land(self) -> bool:
        """Command landing at the current position."""

    @abstractmethod
    def set_home(self, current: bool = True) -> bool:
        """Set home; ``current=True`` uses the present position."""

    @abstractmethod
    def set_param(self, name: str, value: Union[int, float]) -> bool:
        """Set an ArduPilot parameter."""

    @abstractmethod
    def send_command_long(self, command: int, *params: float) -> bool:
        """Send a ``COMMAND_LONG`` (up to 7 params); ``True`` if accepted."""

    # Setpoints

    @abstractmethod
    def send_velocity_target(
        self,
        vx: float,
        vy: float,
        vz: float,
        yaw_rate: float,
        frame: TargetFrame,
    ) -> None:
        """Send a velocity setpoint (m/s, yaw rate rad/s) in ``frame``."""

    @abstractmethod
    def send_local_target(self, target: LocalTarget) -> None:
        """Send a local position+yaw setpoint."""

    @abstractmethod
    def send_global_target(self, target: GlobalTarget) -> None:
        """Send a global position+yaw setpoint."""
