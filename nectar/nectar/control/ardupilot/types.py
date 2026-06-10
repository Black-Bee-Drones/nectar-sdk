"""types for the ArduPilot vehicle core.

Conventions
-----------
- All local positions/velocities are in the ENU frame (x=East, y=North,
  z=Up), matching what MAVROS exposes on ``/mavros/local_position/pose``.
- All yaw values are in **radians, ENU** (0 = East, CCW positive), which
  is what :func:`nectar.utils.PositionUtils.get_yaw_from_pose` returns for
  every supported message type. Compass *heading* (degrees, NED) is kept
  separate and only used for GPS body-frame math.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class TargetFrame(Enum):
    """Reference frame for a velocity/position setpoint."""

    LOCAL = auto()
    """Absolute local ENU frame (FRAME_LOCAL_NED on the wire)."""

    BODY = auto()
    """Body/offset frame (FRAME_BODY_NED on the wire)."""


@dataclass
class Vec3:
    """A 3D vector / point in meters (ENU when used as a local position)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class LocalPose:
    """EKF- or vision-fused local pose in the ENU frame.

    Parameters
    ----------
    position : Vec3
        Position in meters (ENU).
    yaw : float
        Yaw in radians (ENU, 0 = East).
    """

    position: Vec3 = field(default_factory=Vec3)
    yaw: float = 0.0


@dataclass
class GeoPoint:
    """A global position.

    Parameters
    ----------
    latitude, longitude : float
        Degrees.
    altitude : float
        Meters. AMSL when sourced from GPS (``NavSatFix``-equivalent).
    """

    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0


@dataclass
class Attitude:
    """Vehicle attitude in radians (ENU yaw)."""

    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0


@dataclass
class VehicleState:
    """Connection / arming / flight-mode summary.

    Mirrors the subset of ``mavros_msgs/State`` the core relies on.
    """

    connected: bool = False
    armed: bool = False
    guided: bool = False
    mode: str = ""
    system_status: int = 0


@dataclass
class LocalTarget:
    """A local-frame navigation/setpoint target.

    Parameters
    ----------
    position : Vec3
        Target position in meters (ENU).
    yaw : float
        Target yaw in radians (ENU).
    frame : TargetFrame
        Reference frame; computed targets are always ``TargetFrame.LOCAL``.
    """

    position: Vec3 = field(default_factory=Vec3)
    yaw: float = 0.0
    frame: TargetFrame = TargetFrame.LOCAL


@dataclass
class GlobalTarget:
    """A global navigation/setpoint target.

    Parameters
    ----------
    latitude, longitude : float
        Degrees.
    altitude : float
        Meters AMSL (already geoid-corrected, ready to publish).
    yaw : float
        Target yaw in radians (ENU). ``None`` leaves yaw uncontrolled.
    """

    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    yaw: Optional[float] = 0.0
