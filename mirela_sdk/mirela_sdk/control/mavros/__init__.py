"""Mavros control module for ArduPilot drones."""

from mirela_sdk.control.mavros.mavros_api import MavDrone
from mirela_sdk.control.mavros.exceptions import (
    MavrosControlError,
    TakeoffPositionNotSetError,
    SensorNotAvailableError,
    InvalidModeError,
    InvalidStrategyError,
    NavigationError,
    GPSError,
)

__all__ = [
    "MavDrone",
    "MavrosControlError",
    "TakeoffPositionNotSetError",
    "SensorNotAvailableError",
    "InvalidModeError",
    "InvalidStrategyError",
    "NavigationError",
    "GPSError",
]
