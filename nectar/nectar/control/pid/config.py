"""PID configuration from YAML files or dictionaries."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PIDConfig:
    """PID controller configuration."""

    kp: float = 0.0
    ki: float = 0.0
    kd: float = 0.0
    setpoint: float = 0.0
    output_min: float = -1.0
    output_max: float = 1.0
    integral_min: float = -1.0
    integral_max: float = 1.0

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "PIDConfig":
        """
        Load PID configuration from YAML file.

        Parameters
        ----------
        file_path : str or Path
            Path to YAML configuration file.

        Returns
        -------
        PIDConfig
            PID configuration object.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        return cls.from_dict(config_dict)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "PIDConfig":
        """
        Create PIDConfig from dictionary.

        Parameters
        ----------
        config_dict : dict
            Dictionary with PID parameters.

        Returns
        -------
        PIDConfig
            PID configuration object.
        """
        return cls(
            kp=config_dict.get("kp", 0.0),
            ki=config_dict.get("ki", 0.0),
            kd=config_dict.get("kd", 0.0),
            setpoint=config_dict.get("setpoint", 0.0),
            output_min=config_dict.get("output_min", -1.0),
            output_max=config_dict.get("output_max", 1.0),
            integral_min=config_dict.get("integral_min", -1.0),
            integral_max=config_dict.get("integral_max", 1.0),
        )

    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.

        Returns
        -------
        dict
            Configuration as dictionary.
        """
        return {
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "setpoint": self.setpoint,
            "output_min": self.output_min,
            "output_max": self.output_max,
            "integral_min": self.integral_min,
            "integral_max": self.integral_max,
        }

    def get_output_limits(self) -> tuple[float, float]:
        """Get output limits as tuple."""
        return (self.output_min, self.output_max)

    def get_integral_limits(self) -> tuple[float, float]:
        """Get integral limits as tuple."""
        return (self.integral_min, self.integral_max)


@dataclass
class PositionPIDConfig:
    """Configuration for position controller PIDs (X, Y, Z, Yaw axes)."""

    x: PIDConfig = field(default_factory=PIDConfig)
    y: PIDConfig = field(default_factory=PIDConfig)
    z: PIDConfig = field(default_factory=PIDConfig)
    yaw: PIDConfig = field(default_factory=PIDConfig)

    @classmethod
    def from_yaml(cls, file_path: str | Path) -> "PositionPIDConfig":
        """
        Load position PID configuration from YAML file.

        Parameters
        ----------
        file_path : str or Path
            Path to YAML configuration file.

        Returns
        -------
        PositionPIDConfig
            Position PID configuration object.
        """

        with open(file_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        return cls(
            x=PIDConfig.from_dict(config_dict.get("x", {})),
            y=PIDConfig.from_dict(config_dict.get("y", {})),
            z=PIDConfig.from_dict(config_dict.get("z", {})),
            yaw=PIDConfig.from_dict(config_dict.get("yaw", {})),
        )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "x": self.x.to_dict(),
            "y": self.y.to_dict(),
            "z": self.z.to_dict(),
            "yaw": self.yaw.to_dict(),
        }
