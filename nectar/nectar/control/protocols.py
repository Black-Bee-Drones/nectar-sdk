from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Protocol, runtime_checkable

from nectar.control.types import (
    AltitudeSource,
    MoveReference,
    NavigationMethod,
    RTLMethod,
)


class ObstacleDirection(Enum):
    FRONT = auto()
    BACK = auto()
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()


@dataclass
class ObstacleInfo:
    detected: bool
    direction: Optional[ObstacleDirection] = None
    distance: Optional[float] = None


@runtime_checkable
class Drone(Protocol):
    @property
    def is_ready(self) -> bool: ...

    def connect(self) -> bool: ...

    def disconnect(self) -> None: ...

    def arm(self) -> bool: ...

    def disarm(self) -> bool: ...

    def takeoff(self, altitude: float) -> bool: ...

    def land(self, timeout: float = 30.0) -> bool: ...

    def move_velocity(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vz: float = 0.0,
        vyaw: float = 0.0,
        duration: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
    ) -> None: ...

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        yaw: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
        timeout: Optional[float] = 60.0,
        precision: float = 0.2,
        method: NavigationMethod = NavigationMethod.POSITION,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
    ) -> bool: ...

    def move_to_gps(
        self,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        heading: Optional[float] = None,
        timeout: Optional[float] = 60.0,
        precision: float = 0.5,
        method: NavigationMethod = NavigationMethod.PID,
    ) -> bool: ...

    def emergency_stop(self) -> None: ...

    def set_home(self) -> bool: ...

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        method: RTLMethod = RTLMethod.NAVIGATE,
        land: bool = True,
    ) -> bool: ...


@runtime_checkable
class ObstacleDetector(Protocol):
    def update(self) -> ObstacleInfo: ...

    def reset(self) -> None: ...

    @property
    def is_enabled(self) -> bool: ...

    def enable(self) -> None: ...

    def disable(self) -> None: ...
