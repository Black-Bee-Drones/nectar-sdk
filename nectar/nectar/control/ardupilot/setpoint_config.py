"""Setpoint navigation configuration for ArduPilot GUIDED mode.

Configures GUID_OPTIONS, speed limits, arrival radius, acceleration,
jerk limits, and rangefinder usage for setpoint-based navigation strategies.
Shared YAML/dict I/O and range-clamping live in the firmware-agnostic
:class:`~nectar.control.vehicle.setpoint_config.SetpointConfig` base.

ArduPilot parameters reference:
    https://ardupilot.org/copter/docs/parameters.html#wpnav-parameters
    https://ardupilot.org/copter/docs/parameters.html#psc-parameters
    https://ardupilot.org/copter/docs/ac2_guidedmode.html#guided-mode-options
"""

from dataclasses import dataclass
from typing import ClassVar, Dict, Tuple

from nectar.control.vehicle.setpoint_config import SetpointConfig


@dataclass
class SetpointNavConfig(SetpointConfig):
    """
    Configuration for ArduPilot setpoint navigation parameters.

    All speed/distance values in SI units (m/s, m). Conversion to
    ArduPilot units (cm/s, cm) happens internally when setting FCU
    parameters.

    Parameters
    ----------
    guid_options : int
        Bitmask for GUID_OPTIONS parameter. Controls GUIDED mode behavior.
        Bit 0 (1): Allow arming from TX.
        Bit 6 (64): WPNav S-curve path planning for position targets.
        Bit 7 (128): Weathervaning.
        Default 1 = bit 0 (arm from TX, AC_PosControl).
        See https://ardupilot.org/copter/docs/ac2_guidedmode.html#guided-mode-options
    speed : float
        Horizontal speed limit in m/s (maps to WPNAV_SPEED in cm/s).
    speed_up : float
        Climb speed limit in m/s (maps to WPNAV_SPEED_UP in cm/s).
    speed_down : float
        Descent speed limit in m/s (maps to WPNAV_SPEED_DN in cm/s).
    accel : float
        Horizontal acceleration in m/s/s (maps to WPNAV_ACCEL in cm/s/s).
    radius : float
        Arrival radius in m (maps to WPNAV_RADIUS in cm).
        Only used in WPNav mode for trajectory deceleration planning.
    jerk : float
        WPNav horizontal jerk limit in m/s³ (maps to WPNAV_JERK).
        Controls S-curve trajectory smoothness in WPNav mode (bit 6).
        ArduPilot default 1.0, range 1–20.
    psc_jerk : float
        Position controller horizontal jerk limit in m/s³ (PSC_JERK_XY in 4.6.3,
        PSC_JERK_NE in 4.8+). Affects AC_PosControl (SubMode::Pos) response speed.
        ArduPilot default 5.0, range 1–20.
        SITL typically needs higher values (e.g. 50) for usable response.
    rfnd_use : int
        Rangefinder terrain following for WPNav (maps to WPNAV_RFND_USE).
        0 = disabled, 1 = enabled. ArduPilot default 1.
    """

    guid_options: int = 1
    speed: float = 2.0
    speed_up: float = 1.5
    speed_down: float = 1.5
    accel: float = 1.0
    radius: float = 0.2
    jerk: float = 1.0
    psc_jerk: float = 5.0
    rfnd_use: int = 1

    # ArduPilot v4.8+ renamed WPNAV_* → WP_*. Maps primary (4.6.3) name → alias (4.8+) name.
    PARAM_ALIASES: ClassVar[Dict[str, str]] = {
        "WPNAV_SPEED": "WP_SPD",
        "WPNAV_SPEED_UP": "WP_SPD_UP",
        "WPNAV_SPEED_DN": "WP_SPD_DN",
        "WPNAV_ACCEL": "WP_ACC",
        "WPNAV_RADIUS": "WP_RADIUS_M",
        "WPNAV_JERK": "WP_JERK",
        "WPNAV_RFND_USE": "WP_RFND_USE",
        "PSC_JERK_XY": "PSC_JERK_NE",
    }

    # ArduPilot valid ranges
    _RANGES: ClassVar[Dict[str, Tuple[float, float]]] = {
        "speed": (0.1, 20.0),  # WPNAV_SPEED: 10–2000 cm/s
        "speed_up": (0.1, 10.0),  # WPNAV_SPEED_UP: 10–1000 cm/s
        "speed_down": (0.1, 5.0),  # WPNAV_SPEED_DN: 10–500 cm/s
        "accel": (0.5, 5.0),  # WPNAV_ACCEL: 50–500 cm/s²
        "radius": (0.05, 10.0),  # WPNAV_RADIUS: 5–1000 cm
        "jerk": (1.0, 20.0),  # WPNAV_JERK: 1–20 m/s³
        "psc_jerk": (1.0, 50.0),  # PSC_JERK_XY / PSC_JERK_NE: 1–20 (SITL needs ~50)
    }

    def __post_init__(self) -> None:
        self.guid_options = int(self.guid_options)
        self.rfnd_use = int(bool(self.rfnd_use))
        super().__post_init__()

    @property
    def use_wpnav(self) -> bool:
        """True if GUID_OPTIONS bit 6 (WPNav S-curve) is enabled."""
        return bool(self.guid_options & (1 << 6))

    def to_fcu_params(self) -> dict:
        """Return ArduPilot parameter names and values in FCU units.

        Speed/accel/radius are converted to cm/s and cm. Jerk values are
        already in m/s³. Uses stable WPNAV_* names
        as primary. Use ``PARAM_ALIASES`` to get fallback names for
        ArduPilot v4.8+.
        """
        return {
            "GUID_OPTIONS": self.guid_options,
            "WPNAV_SPEED": float(self.speed * 100),
            "WPNAV_SPEED_UP": float(self.speed_up * 100),
            "WPNAV_SPEED_DN": float(self.speed_down * 100),
            "WPNAV_ACCEL": float(self.accel * 100),
            "WPNAV_RADIUS": float(round(self.radius * 100)),
            "WPNAV_JERK": float(self.jerk),
            "WPNAV_RFND_USE": int(self.rfnd_use),
            "PSC_JERK_XY": float(self.psc_jerk),
        }
