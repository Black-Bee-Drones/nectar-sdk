"""ArduPilot firmware specialization.

The shared vehicle core (plain types, transport ABC, navigator) now lives in
:mod:`nectar.control.vehicle`. The plain types are re-exported here for
backward compatibility; ``SetpointNavConfig`` is ArduPilot-specific.
"""

from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.vehicle.types import (
    Attitude,
    DistanceReading,
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    SensorOrientation,
    TargetFrame,
    Vec3,
    VehicleState,
)

__all__ = [
    "Attitude",
    "DistanceReading",
    "GeoPoint",
    "GlobalTarget",
    "LocalPose",
    "LocalTarget",
    "SensorOrientation",
    "SetpointNavConfig",
    "TargetFrame",
    "Vec3",
    "VehicleState",
]
