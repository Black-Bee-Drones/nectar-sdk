"""Setpoint navigation configuration for ArduPilot GUIDED mode.

Configures WPNav vs PosControl mode, speed limits, arrival radius,
and acceleration for setpoint-based navigation strategies.

ArduPilot parameters reference:
    https://ardupilot.org/copter/docs/parameters-Copter-stable-V4.6.3.html#wpnav-parameters
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SetpointNavConfig:
    """
    Configuration for ArduPilot setpoint navigation parameters.

    All values in SI units (m/s, m). Conversion to ArduPilot units
    (cm/s, cm) happens internally when setting FCU parameters.

    Parameters
    ----------
    use_wpnav : bool
        Enable S-curve WPNav path planning (GUID_OPTIONS bit 6).
        False uses direct AC_PosControl (default GUIDED behavior).
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
    """

    use_wpnav: bool = False
    speed: float = 2.0
    speed_up: float = 1.5
    speed_down: float = 1.5
    accel: float = 1.0
    radius: float = 0.2

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "SetpointNavConfig":
        """
        Load configuration from YAML file.

        Parameters
        ----------
        file_path : str or Path
            Path to YAML configuration file.

        Returns
        -------
        SetpointNavConfig
        """
        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        return cls.from_dict(config_dict)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SetpointNavConfig":
        """
        Create from dictionary.

        Parameters
        ----------
        config_dict : dict
            Dictionary with configuration parameters.

        Returns
        -------
        SetpointNavConfig
        """
        return cls(
            use_wpnav=config_dict.get("use_wpnav", False),
            speed=config_dict.get("speed", 2.0),
            speed_up=config_dict.get("speed_up", 1.5),
            speed_down=config_dict.get("speed_down", 1.5),
            accel=config_dict.get("accel", 1.0),
            radius=config_dict.get("radius", 0.2),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "use_wpnav": self.use_wpnav,
            "speed": self.speed,
            "speed_up": self.speed_up,
            "speed_down": self.speed_down,
            "accel": self.accel,
            "radius": self.radius,
        }
