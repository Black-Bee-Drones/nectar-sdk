"""ArduPilot firmware specialization of the shared vehicle core.

:class:`ArduPilotDrone` implements the ArduPilot-specific flight semantics on
top of :class:`~nectar.control.vehicle.drone.VehicleDrone`: GUIDED-mode arming,
the ``GUID_OPTIONS``/``WPNAV`` setpoint configuration, and native ``RTL``-mode
return-to-launch. All transport-agnostic flight/navigation logic lives in the
vehicle core; concrete drones (``MavrosDrone``, ``MavlinkDrone``) only construct
the right transport and subclass this.
"""

from pathlib import Path
from typing import Optional

from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.capabilities import Capability
from nectar.control.vehicle.drone import VehicleDrone
from nectar.utils.log import ERR, WARN


class ArduPilotDrone(VehicleDrone):
    """Base ArduPilot drone: GUIDED control, WPNAV setpoints, native RTL."""

    # ArduPilot v4.8+ renamed RTL params from centimeters to meters.
    _RTL_PARAM_ALIASES = {
        "RTL_ALT": "RTL_ALT_M",
        "RTL_ALT_FINAL": "RTL_ALT_FINAL_M",
    }

    # Capabilities

    @property
    def capabilities(self) -> "frozenset[Capability]":
        """Capabilities derived from the configured pose source."""
        caps = {
            Capability.PID_NAV,
            Capability.LOCAL_SETPOINT,
            Capability.VELOCITY_BODY,
            Capability.VELOCITY_WORLD,
            Capability.VELOCITY_TAKEOFF,
            Capability.SERVO,
            Capability.PARAMS,
            Capability.NATIVE_RTL,
            Capability.OBSTACLE_AVOIDANCE,
            Capability.RANGEFINDER,
            Capability.DISTANCE_SENSORS,
        }
        if self.is_indoor:
            caps.add(Capability.VISION_POSE)
        else:
            caps.add(Capability.GPS_NAV)
            caps.add(Capability.GLOBAL_SETPOINT)
        return frozenset(caps)

    @property
    def setpoint_config(self) -> Optional[SetpointNavConfig]:
        """Current setpoint navigation configuration."""
        return self._setpoint_config

    def _config_dir(self) -> Path:
        """Directory holding bundled ArduPilot PID/setpoint YAML presets."""
        return Path(__file__).parent / "config"

    # Setpoint configuration (GUID_OPTIONS / WPNAV)

    def _load_firmware_config(self) -> None:
        self._setpoint_config: Optional[SetpointNavConfig] = None
        self._applied_radius_cm: float = 0.0
        self._load_setpoint_config()

    def _load_setpoint_config(self) -> None:
        """Load setpoint navigation config from file or use defaults."""
        config = self._config

        if config.setpoint_config_file:
            path = Path(config.setpoint_config_file)
        else:
            config_dir = self._config_dir()
            if self.is_indoor:
                path = config_dir / "setpoint_indoor.yaml"
            else:
                path = config_dir / "setpoint_outdoor.yaml"

        if path.exists():
            self._setpoint_config = SetpointNavConfig.from_yaml(path)
        else:
            self._setpoint_config = SetpointNavConfig()

    def _apply_setpoint_config(self) -> None:
        """Send setpoint navigation parameters (GUID_OPTIONS, WPNAV) to the FCU."""
        if self._setpoint_config is None:
            return

        cfg = self._setpoint_config
        aliases = cfg.PARAM_ALIASES
        failed = []

        # ArduPilot v4.8+ (PR #32147) converted WPNAV params from cm/s to SI (m/s).
        # When falling back to WP_* aliases, divide by 100 to convert cm→m units.
        alias_si_units = {
            "WPNAV_SPEED",
            "WPNAV_SPEED_UP",
            "WPNAV_SPEED_DN",
            "WPNAV_ACCEL",
            "WPNAV_RADIUS",
        }

        for name, val in cfg.to_fcu_params().items():
            if self.set_param(name, val):
                continue
            alias = aliases.get(name)
            if alias:
                self._node.get_logger().info(f"Param {name} failed, trying alias {alias}")
                alias_val = val / 100.0 if name in alias_si_units else val
                if self.set_param(alias, alias_val):
                    continue
            failed.append(name)

        if failed:
            self._node.get_logger().warn(f"Setpoint config: failed to set {', '.join(failed)}")
        else:
            self._node.get_logger().info(
                f"Setpoint config applied: wpnav={cfg.use_wpnav}, "
                f"speed={cfg.speed}m/s, radius={cfg.radius}m"
            )

        if "WPNAV_RADIUS" not in failed:
            self._applied_radius_cm = float(round(cfg.radius * 100))

    def _prepare_position_setpoint(self, precision: float) -> None:
        """Sync WPNAV_RADIUS with precision if WPNav is enabled."""
        if not self._config.apply_setpoint_params:
            return
        if not (self._setpoint_config and self._setpoint_config.use_wpnav):
            return
        radius_cm = float(round(max(5.0, min(precision * 100, 1000.0))))
        if radius_cm != self._applied_radius_cm:
            name = "WPNAV_RADIUS"
            alias = SetpointNavConfig.PARAM_ALIASES.get(name)
            radius_m = radius_cm / 100.0
            if self.set_param(name, radius_cm) or (alias and self.set_param(alias, radius_m)):
                self._applied_radius_cm = radius_cm

    def set_setpoint_config(self, config, apply: bool = True) -> None:
        """
        Update setpoint navigation configuration.

        When ``apply=True`` (default), parameters are pushed to the FCU
        immediately via ``set_param`` (persisted to the autopilot's storage).
        Use ``apply=False`` to update the SDK-side config only (e.g. to change
        ``use_wpnav`` logic without touching the FCU).

        Parameters
        ----------
        config : str | Path | dict | SetpointNavConfig
            YAML file path, configuration dictionary, or SetpointNavConfig.
        apply : bool, default=True
            If True, push the parameters to the FCU.

        Raises
        ------
        TypeError
            If the config type is not supported.
        """
        if isinstance(config, (str, Path)):
            self._setpoint_config = SetpointNavConfig.from_yaml(config)
        elif isinstance(config, dict):
            self._setpoint_config = SetpointNavConfig.from_dict(config)
        elif isinstance(config, SetpointNavConfig):
            self._setpoint_config = config
        else:
            raise TypeError(f"Invalid config type: {type(config)}")
        if apply:
            self._apply_setpoint_config()
        self._node.get_logger().info("Setpoint navigation configuration updated")

    # Arm (GUIDED)

    def arm(self) -> bool:
        """
        Arm motors in GUIDED mode.

        Sets GUIDED mode and arms, polling vehicle state to confirm each step.

        Returns
        -------
        bool
            True if arming successful, False on failure or timeout.
        """
        try:
            if not self.set_mode("GUIDED"):
                return False
            if not self._wait_until(lambda: self.flight_mode == "GUIDED", 3.0):
                self._node.get_logger().warn(f"{WARN} Mode change slow to reflect in state")
            if self._config.apply_setpoint_params:
                self._apply_setpoint_config()
            if not self._transport.arm():
                return False
            if not self._wait_until(lambda: self.is_armed, 6.0):
                self._node.get_logger().warn(f"{WARN} Arm ACKed but state slow to update")
            return True
        except TimeoutError as e:
            self._node.get_logger().error(f"{ERR} Arm failed: {e}")
            return False

    # Native return-to-launch (RTL mode)

    def _rtl_native(self, altitude: Optional[float], land: bool) -> bool:
        try:
            rtl_alt_cm = int(altitude * 100) if altitude is not None else 0
            self._set_rtl_param("RTL_ALT", rtl_alt_cm)

            rtl_final_cm = 0 if land else rtl_alt_cm
            self._set_rtl_param("RTL_ALT_FINAL", rtl_final_cm)

            if not self.set_mode("RTL"):
                return False

            return True
        except TimeoutError as e:
            self._node.get_logger().error(f"RTL ArduPilot failed: {e}")
            return False

    def _set_rtl_param(self, name: str, value_cm: int) -> None:
        """Set an RTL parameter with v4.6.3/v4.8+ alias fallback."""
        if self.set_param(name, value_cm):
            return
        alias = self._RTL_PARAM_ALIASES.get(name)
        if alias:
            value_m = value_cm / 100.0
            if self.set_param(alias, value_m):
                return
        self._node.get_logger().warn(f"Failed to set {name}")
