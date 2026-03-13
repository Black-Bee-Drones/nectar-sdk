"""Setpoint navigation configuration for ArduPilot GUIDED mode.

Configures GUID_OPTIONS, speed limits, arrival radius, and acceleration
for setpoint-based navigation strategies.

ArduPilot parameters reference:
    https://ardupilot.org/copter/docs/parameters-Copter-stable-V4.6.3.html#wpnav-parameters
    https://ardupilot.org/copter/docs/ac2_guidedmode.html#guided-mode-options
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class SetpointNavConfig:
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
        Default 65 = bit 0 + bit 6 (arm from TX + WPNav).
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
    """

    guid_options: int = 65
    speed: float = 2.0
    speed_up: float = 1.5
    speed_down: float = 1.5
    accel: float = 1.0
    radius: float = 0.2

    # ArduPilot valid ranges
    _RANGES = {
        "speed": (0.1, 20.0),  # WPNAV_SPEED: 10–2000 cm/s
        "speed_up": (0.1, 10.0),  # WPNAV_SPEED_UP: 10–1000 cm/s
        "speed_down": (0.1, 5.0),  # WPNAV_SPEED_DN: 10–500 cm/s
        "accel": (0.5, 5.0),  # WPNAV_ACCEL: 50–500 cm/s²
        "radius": (0.05, 10.0),  # WPNAV_RADIUS: 5–1000 cm
    }

    def __post_init__(self) -> None:
        self.guid_options = int(self.guid_options)
        for field_name, (lo, hi) in self._RANGES.items():
            setattr(self, field_name, max(lo, min(float(getattr(self, field_name)), hi)))

    @property
    def use_wpnav(self) -> bool:
        """True if GUID_OPTIONS bit 6 (WPNav S-curve) is enabled."""
        return bool(self.guid_options & (1 << 6))

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

        Raises
        ------
        ValueError
            If YAML content is not a mapping.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        if config_dict is None:
            return cls()
        if not isinstance(config_dict, dict):
            raise ValueError(f"Expected YAML mapping, got {type(config_dict).__name__}")
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
            guid_options=config_dict.get("guid_options", 65),
            speed=config_dict.get("speed", 2.0),
            speed_up=config_dict.get("speed_up", 1.5),
            speed_down=config_dict.get("speed_down", 1.5),
            accel=config_dict.get("accel", 1.0),
            radius=config_dict.get("radius", 0.2),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "guid_options": self.guid_options,
            "speed": self.speed,
            "speed_up": self.speed_up,
            "speed_down": self.speed_down,
            "accel": self.accel,
            "radius": self.radius,
        }
