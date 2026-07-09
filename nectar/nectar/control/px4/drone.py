"""PX4 firmware specialization of the shared vehicle core.

:class:`Px4Drone` implements the PX4-specific flight semantics on top of
:class:`~nectar.control.vehicle.drone.VehicleDrone`:

- **Offboard streaming**: PX4 only accepts ``OFFBOARD`` mode (and only arms in
  it) while setpoints stream faster than 2 Hz, and drops out of offboard if the
  stream stalls for ~500 ms. A background ROS timer (the *offboard pump*)
  republishes the last commanded setpoint at ``offboard_rate_hz`` so the vehicle
  stays in offboard between explicit movement commands.
- **Arm sequence**: stream a hold setpoint until the pump has actually ticked
  enough times, switch to ``OFFBOARD``, then arm.
- **Takeoff/land/RTL**: takeoff climbs to an offboard position setpoint (no mode
  change); landing and RTL use PX4's ``AUTO.LAND`` / ``AUTO.RTL`` modes.

All transport-agnostic flight/navigation logic lives in the vehicle core.
Concrete drones (``Px4MavrosDrone``) only construct the right transport.

See Also
--------
https://docs.px4.io/main/en/flight_modes_mc/
https://docs.px4.io/main/en/ros2/offboard_control.html
"""

from pathlib import Path
from typing import Optional

from nectar.control.capabilities import Capability
from nectar.control.px4.setpoint_config import Px4SetpointConfig
from nectar.control.vehicle.drone import VehicleDrone
from nectar.control.vehicle.types import (
    GlobalTarget,
    LocalTarget,
    TargetFrame,
    Vec3,
)
from nectar.utils.log import ERR, WARN

# PX4 flight modes (MAVROS custom_mode strings).
_MODE_OFFBOARD = "OFFBOARD"
_MODE_LAND = "AUTO.LAND"
_MODE_RTL = "AUTO.RTL"


class Px4Drone(VehicleDrone):
    """Base PX4 drone: OFFBOARD control with a continuous setpoint pump."""

    # Nominal seconds of setpoint streaming before requesting OFFBOARD so PX4
    # accepts it.
    _OFFBOARD_PRESTREAM_S = 0.5
    # Upper bound on that wait so a dead pump/transport can't hang arm() forever.
    _OFFBOARD_PRESTREAM_TIMEOUT_S = 2.0

    # PX4 setpoint params come from a Px4SetpointConfig (MPC_* speed/accel/jerk).
    _setpoint_config_class = Px4SetpointConfig

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
        """Directory holding bundled PX4 PID YAML presets."""
        return Path(__file__).parent / "config"

    # Offboard setpoint pump

    def _load_firmware_config(self) -> None:
        """Load the MPC setpoint config and start the offboard setpoint pump."""
        super()._load_firmware_config()
        self._offboard_setpoint: Optional[tuple] = None
        self._offboard_active: bool = False
        self._pump_ticks: int = 0
        rate = float(getattr(self._config, "offboard_rate_hz", 20.0) or 20.0)
        self._pump_timer = self._node.create_timer(
            1.0 / rate, self._pump_tick, callback_group=self._callback_group
        )

    def _pump_tick(self) -> None:
        """Republish the last setpoint so PX4 stays in OFFBOARD."""
        sp = self._offboard_setpoint
        if not self._offboard_active or sp is None:
            return
        self._pump_ticks += 1
        kind = sp[0]
        if kind == "vel":
            _, vx, vy, vz, yaw_rate, frame = sp
            self._transport.send_velocity_target(vx, vy, vz, yaw_rate, frame)
        elif kind == "local":
            self._transport.send_local_target(sp[1])
        elif kind == "global":
            self._transport.send_global_target(sp[1])

    def _seed_hold_setpoint(self) -> None:
        """Seed the pump with a position-hold setpoint at the current pose."""
        local = self._transport.local_pose
        if local is not None:
            self._offboard_setpoint = (
                "local",
                LocalTarget(
                    position=Vec3(local.position.x, local.position.y, local.position.z),
                    yaw=local.yaw,
                ),
            )
        else:
            self._offboard_setpoint = ("vel", 0.0, 0.0, 0.0, 0.0, TargetFrame.BODY)

    def _emit_velocity(
        self, vx: float, vy: float, vz: float, yaw_rate: float, frame: TargetFrame
    ) -> None:
        """Send a velocity setpoint and keep it as the pump's held value."""
        self._offboard_setpoint = ("vel", vx, vy, vz, yaw_rate, frame)
        self._offboard_active = True
        self._transport.send_velocity_target(vx, vy, vz, yaw_rate, frame)

    def publish_setpoint(self, target) -> None:
        """Send a position setpoint and keep it as the pump's held value."""
        if isinstance(target, GlobalTarget):
            self._offboard_setpoint = ("global", target)
            self._transport.send_global_target(target)
        else:
            self._offboard_setpoint = ("local", target)
            self._transport.send_local_target(target)
        self._offboard_active = True

    def _stream_offboard_prestream(self) -> None:
        """Block until the pump has actually published enough setpoints.

        PX4 only accepts the ``OFFBOARD`` switch while a setpoint stream is
        already flowing.
        """
        rate = float(getattr(self._config, "offboard_rate_hz", 20.0) or 20.0)
        min_ticks = max(1, round(rate * self._OFFBOARD_PRESTREAM_S))
        target = self._pump_ticks + min_ticks
        if not self._wait_until(
            lambda: self._pump_ticks >= target, self._OFFBOARD_PRESTREAM_TIMEOUT_S
        ):
            self._node.get_logger().warn(
                f"{WARN} Offboard pump reached {self._pump_ticks}/{target} setpoints "
                "before the prestream timeout; requesting OFFBOARD anyway"
            )

    def _ensure_offboard_ready(self) -> None:
        """Ensure the pump is streaming and the FCU is in OFFBOARD mode."""
        if self._offboard_setpoint is None:
            self._seed_hold_setpoint()
        self._offboard_active = True
        if (self.flight_mode or "").upper() == _MODE_OFFBOARD:
            return
        # Let the pump stream a few setpoints before requesting the mode switch.
        self._stream_offboard_prestream()
        if not self.set_mode(_MODE_OFFBOARD):
            self._node.get_logger().warn(f"{WARN} Could not enter {_MODE_OFFBOARD} mode")

    # Arm (OFFBOARD)

    def arm(self) -> bool:
        """
        Arm motors in OFFBOARD mode.

        Streams a hold setpoint so PX4 accepts the offboard switch, enters
        OFFBOARD, then arms, polling vehicle state to confirm each step.

        Returns
        -------
        bool
            True if arming successful, False on failure or timeout.
        """
        try:
            self._seed_hold_setpoint()
            self._offboard_active = True
            self._stream_offboard_prestream()

            if not self.set_mode(_MODE_OFFBOARD):
                return False
            if not self._wait_until(lambda: self.flight_mode == _MODE_OFFBOARD, 3.0):
                self._node.get_logger().warn(f"{WARN} OFFBOARD slow to reflect in state")
            # MPC_* speed/accel limits (no-op on the uXRCE-DDS backend, which has
            # no apply_setpoint_params field and cannot set_param).
            if getattr(self._config, "apply_setpoint_params", False):
                self._apply_setpoint_config()
            if not self._transport.arm():
                return False
            if not self._wait_until(lambda: self.is_armed, 6.0):
                self._node.get_logger().warn(f"{WARN} Arm ACKed but state slow to update")
            return True
        except TimeoutError as e:
            self._node.get_logger().error(f"{ERR} Arm failed: {e}")
            return False

    # Takeoff / land via offboard climb and AUTO.LAND

    def _command_takeoff(self, altitude: float) -> bool:
        """Climb to ``altitude`` by streaming an offboard position setpoint."""
        local = self._transport.local_pose
        if local is None:
            # No EKF local position: fall back to the FCU takeoff command.
            return self._transport.command_takeoff(altitude)
        target = LocalTarget(
            position=Vec3(
                local.position.x,
                local.position.y,
                local.position.z + float(altitude),
            ),
            yaw=local.yaw,
        )
        self.publish_setpoint(target)
        return True

    def _command_land(self) -> bool:
        """Land at the current position via PX4 AUTO.LAND."""
        self._offboard_active = False
        return self.set_mode(_MODE_LAND)

    # Native return-to-launch (AUTO.RTL)

    def _rtl_native(self, altitude: Optional[float], land: bool) -> bool:
        try:
            if altitude is not None:
                self.set_param("RTL_RETURN_ALT", float(altitude))
            # RTL_LAND_DELAY: 0 lands on arrival, -1 loiters at home (no land).
            self.set_param("RTL_LAND_DELAY", 0.0 if land else -1.0)
            self._offboard_active = False
            return self.set_mode(_MODE_RTL)
        except TimeoutError as e:
            self._node.get_logger().error(f"RTL PX4 failed: {e}")
            return False

    # Runtime speed (PX4 MPC_* parameters)

    def _change_speed(self, speed: float, speed_type: str) -> bool:
        """Runtime speed change by updating the PX4 ``MPC_*`` velocity parameter.

        ``horizontal`` sets the cruise speed and raises the hard cap to match;
        ``climb`` / ``descent`` set the vertical limits. Requires a backend that
        can set parameters (MAVROS / direct MAVLink); the uXRCE-DDS backend
        cannot and returns False.
        """
        if speed <= 0:
            self._node.get_logger().error("PX4 set_speed requires a positive speed (m/s)")
            return False
        params = {
            "horizontal": ("MPC_XY_CRUISE", "MPC_XY_VEL_MAX"),
            "climb": ("MPC_Z_VEL_MAX_UP",),
            "descent": ("MPC_Z_VEL_MAX_DN",),
        }[speed_type]
        ok = True
        for name in params:
            ok = self.set_param(name, float(speed)) and ok
        return ok
