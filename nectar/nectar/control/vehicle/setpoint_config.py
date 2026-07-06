"""Shared base for firmware setpoint-navigation configuration.

A :class:`SetpointConfig` carries SI-unit speed/accel/jerk limits for setpoint
navigation (the autopilot's onboard position controller) and converts them to
autopilot parameters via :meth:`to_fcu_params`. ArduPilot
(:class:`~nectar.control.ardupilot.setpoint_config.SetpointNavConfig`) and PX4
(:class:`~nectar.control.px4.setpoint_config.Px4SetpointConfig`) subclass it,
sharing the YAML/dict I/O and range-clamping while each maps to its own
parameter names (``WPNAV_*`` vs ``MPC_*``).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from pathlib import Path
from typing import ClassVar, Dict, Tuple, Union

import yaml


@dataclass
class SetpointConfig(ABC):
    """Firmware-agnostic setpoint-navigation configuration base.

    Subclasses declare SI-unit fields (m/s, m/s/s, m/s³), a ``_RANGES`` map of
    ``field -> (min, max)`` used to clamp values in :meth:`__post_init__`, an
    optional ``PARAM_ALIASES`` map (primary FCU name -> firmware alias), and
    implement :meth:`to_fcu_params`.
    """

    # field name -> (min, max); clamped in __post_init__. Override per firmware.
    _RANGES: ClassVar[Dict[str, Tuple[float, float]]] = {}
    # primary FCU param name -> firmware alias (fallback). Override per firmware.
    PARAM_ALIASES: ClassVar[Dict[str, str]] = {}

    def __post_init__(self) -> None:
        self._clamp()

    def _clamp(self) -> None:
        """Clamp each ``_RANGES`` field into its valid ``[min, max]`` interval."""
        for name, (lo, hi) in self._RANGES.items():
            setattr(self, name, max(lo, min(float(getattr(self, name)), hi)))

    @abstractmethod
    def to_fcu_params(self) -> Dict[str, Union[int, float]]:
        """Return autopilot parameter name -> value in FCU units."""

    @classmethod
    def from_yaml(cls, file_path: Union[str, Path]) -> "SetpointConfig":
        """Load configuration from a YAML mapping file.

        Raises
        ------
        ValueError
            If the YAML content is not a mapping.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError(f"Expected YAML mapping, got {type(data).__name__}")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SetpointConfig":
        """Create from a dict, ignoring keys that are not declared fields."""
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in config_dict.items() if k in valid})

    def to_dict(self) -> dict:
        """Serialize the configuration fields to a plain dict."""
        return {f.name: getattr(self, f.name) for f in fields(self)}
