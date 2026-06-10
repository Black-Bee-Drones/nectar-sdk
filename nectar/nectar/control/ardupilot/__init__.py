"""Shared ArduPilot/MAVLink vehicle core."""

from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.ardupilot.types import (
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
