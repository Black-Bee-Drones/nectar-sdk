"""Declarative drone capability model.

Each drone declares the set of :class:`Capability` it supports via
``BaseDrone.capabilities``. This replaces scattered ad-hoc checks with one
source of truth that callers can query with ``drone.supports(cap)`` and that
the SDK uses to raise a consistent
:class:`~nectar.control.exceptions.CapabilityNotSupportedError`.
"""

from enum import Enum, auto


class Capability(Enum):
    """A discrete feature a drone may or may not support."""

    GPS_NAV = auto()
    """Navigate to global (lat/lon) waypoints."""

    LOCAL_SETPOINT = auto()
    """Onboard local position controller (FRAME_LOCAL_NED setpoints)."""

    GLOBAL_SETPOINT = auto()
    """Onboard global position controller (GPS setpoints)."""

    PID_NAV = auto()
    """Companion-side velocity PID navigation."""

    VELOCITY_WORLD = auto()
    """Velocity commands in the world/local frame."""

    VELOCITY_TAKEOFF = auto()
    """Velocity commands relative to the takeoff frame."""

    SERVO = auto()
    """Auxiliary servo / actuator control."""

    PARAMS = auto()
    """Read/write autopilot parameters."""

    RANGEFINDER = auto()
    """Downward rangefinder altitude source."""

    DISTANCE_SENSORS = auto()
    """All-orientation distance sensor telemetry."""

    VISION_POSE = auto()
    """External-vision pose estimate (indoor / non-GPS)."""

    NATIVE_RTL = auto()
    """Autopilot-native return-to-launch."""

    OBSTACLE_AVOIDANCE = auto()
    """Companion-side obstacle detection / avoidance."""
