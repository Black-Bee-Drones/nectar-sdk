"""Shared ArduPilot/MAVLink vehicle core."""

from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.ardupilot.types import (
    Attitude,
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    TargetFrame,
    Vec3,
    VehicleState,
)

__all__ = [
    "Attitude",
    "GeoPoint",
    "GlobalTarget",
    "LocalPose",
    "LocalTarget",
    "SetpointNavConfig",
    "TargetFrame",
    "Vec3",
    "VehicleState",
]
