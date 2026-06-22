"""Setpoint navigation configuration for PX4 (multicopter position controller).

The PX4 analog of ArduPilot's WPNAV parameters: speed, acceleration, jerk and
yaw-rate limits for the onboard position controller that tracks OFFBOARD
position setpoints (``move_to``/``move_to_gps`` POSITION methods, and the PX4
takeoff climb). Shared YAML/dict I/O and range-clamping live in the
firmware-agnostic :class:`~nectar.control.vehicle.setpoint_config.SetpointConfig`
base.

PX4 saturates the commanded velocity to ``MPC_XY_VEL_MAX`` and tracks setpoints
at the desired cruise speed ``MPC_XY_CRUISE`` (autonomous/offboard). See the PX4
Controller Diagrams and Full Parameter Reference:

    https://docs.px4.io/main/en/flight_stack/controller_diagrams
    https://docs.px4.io/main/en/advanced/parameter_reference#multicopter-position-control
"""

from dataclasses import dataclass
from typing import ClassVar, Dict, Tuple

from nectar.control.vehicle.setpoint_config import SetpointConfig


@dataclass
class Px4SetpointConfig(SetpointConfig):
    """
    Configuration for PX4 setpoint navigation (``MPC_*`` parameters).

    All values in SI units (m/s, m/s/s, m/s³) except ``yaw_rate`` (deg/s, to
    match PX4's ``MPC_YAWRAUTO_MAX``). Unlike ArduPilot there is no
    ``GUID_OPTIONS``/arrival-radius equivalent — PX4 offboard arrival is judged
    by the SDK navigator, so only kinematic limits are configured here.

    Parameters
    ----------
    speed : float
        Desired horizontal cruise speed in m/s (maps to ``MPC_XY_CRUISE``).
    vel_max : float
        Maximum horizontal speed in m/s (maps to ``MPC_XY_VEL_MAX``, the hard
        saturation). Raised to at least ``speed`` so the cruise is never capped.
    speed_up : float
        Maximum climb speed in m/s (maps to ``MPC_Z_VEL_MAX_UP``).
    speed_down : float
        Maximum descent speed in m/s (maps to ``MPC_Z_VEL_MAX_DN``).
    accel : float
        Horizontal acceleration in m/s/s (maps to ``MPC_ACC_HOR``).
    accel_up : float
        Maximum upward acceleration in m/s/s (maps to ``MPC_ACC_UP_MAX``).
    accel_down : float
        Maximum downward acceleration in m/s/s (maps to ``MPC_ACC_DOWN_MAX``).
    jerk : float
        Auto-mode jerk limit in m/s³ (maps to ``MPC_JERK_AUTO``). Controls the
        smoothness of the jerk-limited trajectory generator.
    yaw_rate : float
        Maximum auto yaw rate in deg/s (maps to ``MPC_YAWRAUTO_MAX``).
    takeoff_speed : float
        Takeoff climb speed in m/s (maps to ``MPC_TKO_SPEED``).
    """

    speed: float = 5.0
    vel_max: float = 12.0
    speed_up: float = 3.0
    speed_down: float = 1.5
    accel: float = 3.0
    accel_up: float = 4.0
    accel_down: float = 3.0
    jerk: float = 4.0
    yaw_rate: float = 45.0
    takeoff_speed: float = 1.5

    # PX4 valid ranges (from the multicopter position-control parameter metadata).
    _RANGES: ClassVar[Dict[str, Tuple[float, float]]] = {
        "speed": (0.1, 20.0),  # MPC_XY_CRUISE
        "vel_max": (0.5, 20.0),  # MPC_XY_VEL_MAX
        "speed_up": (0.3, 8.0),  # MPC_Z_VEL_MAX_UP
        "speed_down": (0.3, 4.0),  # MPC_Z_VEL_MAX_DN
        "accel": (2.0, 15.0),  # MPC_ACC_HOR
        "accel_up": (2.0, 15.0),  # MPC_ACC_UP_MAX
        "accel_down": (2.0, 15.0),  # MPC_ACC_DOWN_MAX
        "jerk": (1.0, 80.0),  # MPC_JERK_AUTO
        "yaw_rate": (5.0, 360.0),  # MPC_YAWRAUTO_MAX (deg/s)
        "takeoff_speed": (1.0, 5.0),  # MPC_TKO_SPEED
    }

    def to_fcu_params(self) -> dict:
        """Return PX4 parameter names and values in FCU units.

        PX4 parameters are already in SI units, so values pass through directly
        (``yaw_rate`` stays in deg/s). ``MPC_XY_VEL_MAX`` is raised to at least
        the cruise ``speed`` so the cruise is never clamped by the cap.
        """
        return {
            "MPC_XY_CRUISE": float(self.speed),
            "MPC_XY_VEL_MAX": float(max(self.vel_max, self.speed)),
            "MPC_Z_VEL_MAX_UP": float(self.speed_up),
            "MPC_Z_VEL_MAX_DN": float(self.speed_down),
            "MPC_ACC_HOR": float(self.accel),
            "MPC_ACC_UP_MAX": float(self.accel_up),
            "MPC_ACC_DOWN_MAX": float(self.accel_down),
            "MPC_JERK_AUTO": float(self.jerk),
            "MPC_YAWRAUTO_MAX": float(self.yaw_rate),
            "MPC_TKO_SPEED": float(self.takeoff_speed),
        }
