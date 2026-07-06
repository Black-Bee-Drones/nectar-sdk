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

    # ArduPilot setpoint params come from a SetpointNavConfig (WPNAV/GUID_OPTIONS).
    _setpoint_config_class = SetpointNavConfig

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
            Capability.ACTUATOR,
            Capability.GRIPPER,
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

    def _config_dir(self) -> Path:
        """Directory holding bundled ArduPilot PID/setpoint YAML presets."""
        return Path(__file__).parent / "config"

    # Setpoint configuration (GUID_OPTIONS / WPNAV)

    def _load_firmware_config(self) -> None:
        self._applied_radius_cm: float = 0.0
        super()._load_firmware_config()

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

    # Servo and runtime speed (ArduPilot command specifics)

    def do_servo(self, aux_out: int, pwm_value: int) -> bool:
        """
        Control an auxiliary servo output via MAV_CMD_DO_SET_SERVO.

        ArduPilot-specific per-channel PWM control. PX4 exposes no equivalent;
        use :meth:`set_actuator` / :meth:`set_gripper` for portable payloads.

        Parameters
        ----------
        aux_out : int
            Servo channel (0-7 maps to AUX outputs 1-8, FCU channels 9-16).
        pwm_value : int
            PWM value in microseconds (typically 1000-2000).

        Returns
        -------
        bool
            True if the command was sent, False on failure or timeout.

        Raises
        ------
        CapabilityNotSupportedError
            If the drone does not declare ``Capability.SERVO``.
        """
        self._require(Capability.SERVO)
        try:
            return bool(
                self._transport.send_command_long(
                    183,  # MAV_CMD_DO_SET_SERVO
                    float(aux_out + 8),
                    float(pwm_value),
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                )
            )
        except TimeoutError as e:
            self._node.get_logger().error(f"Servo command failed: {e}")
            return False

    def _change_speed(self, speed: float, speed_type: str) -> bool:
        """Runtime speed change via MAV_CMD_DO_CHANGE_SPEED.

        Immediately updates AC_PosControl's active speed limit. ``speed`` of -1
        means "no change" and -2 reverts to the WPNAV default.

        See Also
        --------
        https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed
        """
        type_map = {"horizontal": 0, "climb": 1, "descent": 2}
        try:
            return bool(
                self._transport.send_command_long(
                    178,  # MAV_CMD_DO_CHANGE_SPEED
                    float(type_map[speed_type]),
                    float(speed),
                    -1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                )
            )
        except TimeoutError as e:
            self._node.get_logger().error(f"Set speed failed: {e}")
            return False
