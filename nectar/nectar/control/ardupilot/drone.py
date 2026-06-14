"""Shared ArduPilot vehicle behavior, driven by a pluggable transport.

:class:`ArduPilotDrone` holds all the flight/navigation logic common to every
ArduPilot vehicle (arm/takeoff/land/move/rtl/params/...), reading telemetry and
issuing commands
Concrete drones (``MavrosDrone``, ``MavlinkDrone``) only construct the right
transport and subclass this.
"""

import math
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
from rclpy.duration import Duration
from rclpy.executors import Executor

from nectar.control.ardupilot.gps_utils import GPSUtils
from nectar.control.ardupilot.navigator import ArduPilotNavigator
from nectar.control.ardupilot.sequencer import FlightSequencer
from nectar.control.ardupilot.setpoint_config import SetpointNavConfig
from nectar.control.ardupilot.target_computer import TargetComputer
from nectar.control.ardupilot.transport import MavlinkTransport
from nectar.control.ardupilot.types import (
    DistanceReading,
    GeoPoint,
    GlobalTarget,
    LocalPose,
    LocalTarget,
    SensorOrientation,
    TargetFrame,
    Vec3,
)
from nectar.control.base import BaseDrone
from nectar.control.capabilities import Capability
from nectar.control.config import DroneConfig
from nectar.control.exceptions import (
    CapabilityNotSupportedError,
    SensorNotAvailableError,
    TakeoffPositionNotSetError,
)
from nectar.control.pid import PIDConfig, PositionPIDConfig
from nectar.control.types import (
    AltitudeSource,
    MoveReference,
    NavigationMethod,
    PoseSource,
    RTLMethod,
)
from nectar.utils.log import ARROW, ERR, OK, WARN
from nectar.utils.position_utils import PositionUtils


class ArduPilotDrone(BaseDrone):
    """
    Base ArduPilot drone implementing all shared flight behavior.

    Parameters
    ----------
    config : DroneConfig
        Configuration; subclasses pass ``MavrosConfig`` / ``MavlinkConfig``.
    transport : MavlinkTransport
        Concrete transport (constructed by the subclass).
    executor : Executor, optional
        ROS 2 executor to register this drone's node with.
    """

    def __init__(
        self,
        config: DroneConfig,
        transport: MavlinkTransport,
        executor: Optional[Executor] = None,
    ) -> None:
        self._transport = transport
        self._pose_source = config.pose_source
        self._pid_config: Optional[PositionPIDConfig] = None
        self._setpoint_config: Optional[SetpointNavConfig] = None
        self._applied_radius_cm: float = 0.0
        self._takeoff_position: Optional[Union[LocalTarget, GlobalTarget]] = None
        self._takeoff_local: Optional[LocalTarget] = None
        self._initial_altitude: float = 0.0
        self._initial_heading: float = 0.0

        super().__init__(config, executor)

        transport.attach(self)
        transport.start()

        self._sequencer = FlightSequencer(self)
        self._navigator = ArduPilotNavigator(self)

        self._startup_sensors()
        self._load_pid_config()
        self._load_setpoint_config()

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
    def is_indoor(self) -> bool:
        """True if configured for vision-based indoor navigation."""
        return self._pose_source == PoseSource.VISION

    @property
    def is_armed(self) -> Optional[bool]:
        """Check if motors are armed."""
        return self._transport.state.armed

    @property
    def flight_mode(self) -> Optional[str]:
        """Current ArduPilot flight mode."""
        return self._transport.state.mode

    @property
    def is_fcu_connected(self) -> Optional[bool]:
        """Check if FCU link is up."""
        return self._transport.state.connected

    @property
    def gps(self) -> GeoPoint:
        """
        GPS fix as a plain :class:`GeoPoint`.

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("GPS", "indoor")
        return self._transport.gps

    @property
    def heading(self) -> float:
        """
        Compass heading in degrees.

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("Heading", "indoor")
        hdg = self._transport.heading
        return hdg if hdg is not None else 0.0

    @property
    def rel_alt(self) -> float:
        """
        Relative altitude above home position.

        Raises
        ------
        SensorNotAvailableError
            If pose_source is VISION (indoor mode).
        """
        if self.is_indoor:
            raise SensorNotAvailableError("Relative altitude", "indoor")
        alt = self._transport.rel_alt
        return alt if alt is not None else 0.0

    @property
    def vision_pose(self) -> Optional[LocalPose]:
        """Vision-based pose estimate (ENU) as a plain :class:`LocalPose`."""
        return self._transport.vision_pose

    @property
    def local_pose(self) -> Optional[LocalPose]:
        """EKF-fused local position (ENU) as a plain :class:`LocalPose`."""
        return self._transport.local_pose

    @property
    def lidar_available(self) -> bool:
        """Whether rangefinder data has been received."""
        return self._transport.rangefinder is not None

    @property
    def pid_config(self) -> Optional[PositionPIDConfig]:
        """Current PID configuration for position control."""
        return self._pid_config

    @property
    def setpoint_config(self) -> Optional[SetpointNavConfig]:
        """Current setpoint navigation configuration."""
        return self._setpoint_config

    def get_altitude(self, source: AltitudeSource = AltitudeSource.AUTO) -> Optional[float]:
        """
        Get altitude from a specific sensor source.

        Parameters
        ----------
        source : AltitudeSource, default=AUTO
            Sensor source to read altitude from:

            - AUTO: best available (lidar > vision Z > relative altitude).
            - LIDAR: lidar rangefinder reading.
            - VISION: vision pose Z component.
            - REL_ALT: GPS-based relative altitude.

        Returns
        -------
        float or None
            Altitude in meters, or None if the requested source is unavailable.
        """
        transport = self._transport
        if source == AltitudeSource.LIDAR:
            return transport.rangefinder
        if source == AltitudeSource.VISION:
            vp = transport.vision_pose
            return vp.position.z if vp is not None else None
        if source == AltitudeSource.REL_ALT:
            if not self.is_indoor:
                return transport.rel_alt
            return None
        # AUTO: lidar > vision Z > relative altitude
        rng = transport.rangefinder
        if rng is not None:
            return rng
        vp = transport.vision_pose
        if vp is not None:
            return vp.position.z
        rel = transport.rel_alt
        if rel is not None:
            return rel
        return None

    @property
    def distance_sensors(self) -> Dict[int, DistanceReading]:
        """All distance-sensor readings the FCU reports, keyed by sensor id.

        Covers every orientation (forward, the yaw sectors, up, down) and id, for
        obstacle detection, redundancy, or verification. The downward sensor used
        for altitude is also available through :meth:`get_altitude` with
        ``AltitudeSource.LIDAR``.
        """
        return self._transport.distance_sensors

    def get_distance(self, orientation: SensorOrientation) -> Optional[DistanceReading]:
        """Most recent reading facing ``orientation``, or ``None`` if none.

        When several sensors share an orientation, the latest one is returned.
        """
        matches = [
            r for r in self._transport.distance_sensors.values() if r.orientation == orientation
        ]
        if not matches:
            return None
        return max(matches, key=lambda r: r.timestamp)

    @property
    def position(self) -> Union[LocalPose, GeoPoint]:
        """Current position: vision pose (indoor) or GPS (outdoor)."""
        if self.is_indoor:
            return self._transport.vision_pose
        return self._transport.gps

    @property
    def position_as_target(self) -> Optional[Union[LocalTarget, GlobalTarget]]:
        """Current position converted to a plain setpoint target."""
        if self.is_indoor:
            vp = self._transport.vision_pose
            if vp is None:
                self._node.get_logger().debug("position_as_target: No vision data")
                return None
            lidar = self._transport.rangefinder
            z = lidar if lidar is not None else vp.position.z
            return LocalTarget(
                position=Vec3(vp.position.x, vp.position.y, z),
                yaw=vp.yaw,
            )
        gps = self._transport.gps
        if gps is None:
            self._node.get_logger().debug("position_as_target: No GPS data")
            return None
        return GlobalTarget(
            latitude=gps.latitude,
            longitude=gps.longitude,
            altitude=gps.altitude,
            yaw=math.radians(90.0 - self.heading),
        )

    def _get_driver_name(self) -> str:
        return self._transport.driver_name()

    def _get_driver_command(self) -> str:
        return self._transport.driver_command()

    def _start_driver(self) -> bool:
        return self._transport.start_driver()

    def connect(self) -> bool:
        """Check link status to the FCU."""
        self._connected = self._transport.connected
        return self._connected

    def disconnect(self) -> None:
        """Disconnect and cleanup resources."""
        self.cleanup()

    def cleanup(self) -> None:
        """Close the transport, then tear down ROS resources."""
        try:
            self._transport.close()
        except Exception:
            pass
        super().cleanup()

    # Sensor / config startup

    def _startup_sensors(self) -> None:
        """Wait for expected sensors and record initial altitude/heading."""
        config = self._config
        timeout = config.sensor_timeout
        transport = self._transport

        self._node.get_logger().info("Starting sensor initialization...")

        if config.expect_lidar:
            if self._wait_until(lambda: transport.rangefinder is not None, timeout):
                self._node.get_logger().info("LiDAR available")
            else:
                self._node.get_logger().warn("LiDAR not available")
        else:
            self._node.get_logger().info("LiDAR not checked")

        if self.is_indoor:
            sensors_ok = self._wait_until(lambda: transport.vision_pose is not None, timeout)
            if sensors_ok:
                self._node.get_logger().info("Vision pose received")
            self._initial_altitude = 0.0
            self._initial_heading = 0.0
        else:
            sensors_ok = self._wait_until(
                lambda: transport.gps is not None and transport.heading is not None,
                timeout,
            )
            if sensors_ok:
                self._node.get_logger().info("GPS and heading received")
                self._initial_altitude = transport.gps.altitude
                self._initial_heading = transport.heading

        if not sensors_ok:
            self._node.get_logger().warn("Sensor initialization incomplete")

    def _wait_until(self, predicate, timeout: float) -> bool:
        """Wait until ``predicate()`` is true or ``timeout`` seconds elapse."""
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

    def _config_dir(self) -> Path:
        """Directory holding bundled PID/setpoint YAML presets"""
        return Path(__file__).parent / "config"

    def _load_pid_config(self) -> None:
        """Load PID configuration from file or use defaults for the current mode."""
        config = self._config

        if config.pid_config_file:
            path = Path(config.pid_config_file)
        else:
            config_dir = self._config_dir()
            if self.is_indoor:
                path = config_dir / "position_indoor.yaml"
            else:
                path = config_dir / "position_outdoor.yaml"

        if path.exists():
            self._pid_config = PositionPIDConfig.from_yaml(path)
        else:
            self._pid_config = self._default_pid_config()

    def _default_pid_config(self) -> PositionPIDConfig:
        """Generate default PID configuration for the current mode."""
        if self.is_indoor:
            return PositionPIDConfig(
                x=PIDConfig(
                    kp=0.5,
                    output_min=-0.42,
                    output_max=0.42,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
                y=PIDConfig(
                    kp=0.5,
                    output_min=-0.42,
                    output_max=0.42,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
                z=PIDConfig(
                    kp=0.22,
                    output_min=-0.15,
                    output_max=0.1,
                    integral_min=-0.3,
                    integral_max=0.3,
                ),
                yaw=PIDConfig(
                    kp=0.5,
                    ki=0.1,
                    output_min=-0.2,
                    output_max=0.2,
                    integral_min=-0.5,
                    integral_max=0.5,
                ),
            )
        return PositionPIDConfig(
            x=PIDConfig(
                kp=0.8,
                output_min=-1.0,
                output_max=1.0,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            y=PIDConfig(
                kp=0.8,
                output_min=-1.0,
                output_max=1.0,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            z=PIDConfig(
                kp=0.5,
                output_min=-0.8,
                output_max=0.8,
                integral_min=-1.0,
                integral_max=1.0,
            ),
            yaw=PIDConfig(
                kp=0.5,
                ki=0.1,
                output_min=-0.3,
                output_max=0.3,
                integral_min=-0.5,
                integral_max=0.5,
            ),
        )

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

    def _sync_wpnav_radius(self, precision: float) -> None:
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

    # Arm / disarm / takeoff / land

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

    def disarm(self) -> bool:
        """
        Force disarm motors.

        Sends MAV_CMD_COMPONENT_ARM_DISARM (400) with the force flag
        (param2=21196) to bypass safety checks.

        Returns
        -------
        bool
            True if disarming successful, False on failure or timeout.
        """
        try:
            return bool(self._transport.disarm(force=True))
        except TimeoutError as e:
            self._node.get_logger().error(f"Disarm failed: {e}")
            return False

    def takeoff(
        self,
        altitude: float,
        max_retries: int = 2,
        adjust_altitude: bool = True,
        precision: float = 0.12,
        timeout: float = 25.0,
    ) -> bool:
        """
        Execute takeoff with event-driven completion detection.

        Per attempt: arm (state-polled) -> spin-up delay -> set takeoff position
        (first attempt) -> takeoff command -> wait for liftoff and altitude
        settling -> optional altitude adjustment. Skips entirely if already
        airborne. Retries only on failed liftoff.

        Parameters
        ----------
        altitude : float
            Target altitude in meters.
        max_retries : int, default=2
            Maximum number of takeoff attempts.
        adjust_altitude : bool, default=True
            If True, fine-tune altitude using move_to after settling.
        precision : float, default=0.12
            Altitude precision in meters for adjustment.
        timeout : float, default=25.0
            Maximum seconds to wait for altitude settling and for adjustment.

        Returns
        -------
        bool
            True if takeoff successful, False if all retries exhausted.
        """
        if self._sequencer.is_airborne():
            self._node.get_logger().warn(
                f"{WARN} Already airborne at {self.get_altitude() or 0.0:.2f}m, skipping takeoff"
            )
            if self._takeoff_position is None:
                self._set_takeoff_position()
            return True

        for attempt in range(max_retries):
            self._node.get_logger().info(
                f"{ARROW} Takeoff attempt {attempt + 1}/{max_retries} to {altitude:.2f}m"
            )

            if not self.arm():
                self._node.get_logger().error(f"{ERR} Arm failed, cannot takeoff")
                return False

            self.delay(self._sequencer.spin_up_delay)

            if attempt == 0 and not self._set_takeoff_position():
                self._node.get_logger().error(f"{ERR} Failed to set takeoff position")
                return False

            start_alt = self.get_altitude() or 0.0

            try:
                if not self._transport.command_takeoff(float(altitude)):
                    return False
            except TimeoutError as e:
                self._node.get_logger().error(f"{ERR} Takeoff service timeout: {e}")
                return False

            lifted, current_alt = self._sequencer.wait_takeoff_settle(
                start_alt, start_alt + float(altitude), timeout
            )
            height_gain = current_alt - start_alt
            armed = self.is_armed

            if lifted and armed:
                self._node.get_logger().info(
                    f"{OK} Settled at {current_alt:.2f}m (gain {height_gain:.2f}m)"
                )
                if adjust_altitude and abs(altitude - current_alt) > precision:
                    self._node.get_logger().info(
                        f"{ARROW} Adjusting altitude {current_alt:.2f}m → {altitude:.2f}m"
                    )
                    self.move_to(
                        x=0.0,
                        y=0.0,
                        z=altitude,
                        yaw=0.0,
                        reference=MoveReference.TAKEOFF,
                        method=NavigationMethod.PID,
                        precision=precision,
                        timeout=timeout,
                    )
                return True

            if self._sequencer.is_airborne():
                self._node.get_logger().warn(
                    f"{WARN} Low gain ({height_gain:.2f}m) but airborne at "
                    f"{current_alt:.2f}m, accepting"
                )
                return True

            if attempt < max_retries - 1:
                self._node.get_logger().warn(
                    f"{WARN} No liftoff (gain {height_gain:.2f}m, armed={armed}), "
                    f"disarming for retry"
                )
                self.disarm()
                self.delay(1.5)
            else:
                self._node.get_logger().error(f"{ERR} Takeoff failed after {max_retries} attempts")

        return False

    def land(self, timeout: float = 60.0) -> bool:
        """
        Execute landing at current position.

        Sends the land command and waits for touchdown (descent velocity has
        settled) or full disarm, whichever happens first. Returning on
        touchdown avoids blocking for ArduPilot's ``DISARM_DELAY``.

        Parameters
        ----------
        timeout : float, default=60.0
            Maximum time to wait for landing completion. Defaults are generous
            for slow SITL descents; real drones return early.

        Returns
        -------
        bool
            True on touchdown or disarm, False on command failure or timeout.
        """
        try:
            start_alt = self.get_altitude() or 0.0
            if not self._transport.command_land():
                return False

            if self._sequencer.wait_landed(start_alt, timeout):
                self._node.get_logger().info(
                    f"{OK} Landed at {self.get_altitude() or 0.0:.2f}m (armed={self.is_armed})"
                )
                return True
            self._node.get_logger().warn(f"{WARN} Land timed out before touchdown")
            return False
        except TimeoutError as e:
            self._node.get_logger().error(f"{ERR} Land service timeout: {e}")
            return False

    # Movement

    def publish_setpoint(self, target: Union[LocalTarget, GlobalTarget]) -> None:
        """Send a navigation target to the transport's setpoint egress."""
        if isinstance(target, GlobalTarget):
            self._transport.send_global_target(target)
        else:
            self._transport.send_local_target(target)

    def move_velocity(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vz: float = 0.0,
        vyaw: float = 0.0,
        duration: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
    ) -> None:
        """
        Move the drone by sending velocity commands.

        Parameters
        ----------
        vx : float (m/s), default=0.0
            BODY/TAKEOFF: forward (+) / backward (-).
            WORLD: east (+) / west (-).
        vy : float (m/s), default=0.0
            BODY/TAKEOFF: left (+) / right (-).
            WORLD: north (+) / south (-).
        vz : float (m/s), default=0.0
            Up (+) / down (-).
        vyaw : float (rad/s), default=0.0
            Counter-clockwise (+) / clockwise (-).
        duration : float (s), optional
            Movement time. If None, publishes a single command (continuous
            mode, caller must re-publish).
        reference : MoveReference, default=BODY
            Velocity reference frame:

            - BODY: heading-relative (FLU: vx=forward, vy=left, vz=up). Sent in
              the BODY frame; the transport converts FLU to FRD.
            - WORLD: absolute directions (ENU: vx=east, vy=north, vz=up). Sent
              in the LOCAL frame; the transport converts ENU to NED.
            - TAKEOFF: velocities in the takeoff heading, rotated into the
              current body frame. Requires the takeoff position to be set.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but the takeoff position is not set.
        SensorNotAvailableError
            If required position sensors are not available.
        """
        frame = TargetFrame.LOCAL if reference == MoveReference.WORLD else TargetFrame.BODY

        if reference == MoveReference.TAKEOFF:
            if self._takeoff_position is None:
                raise TakeoffPositionNotSetError("move_velocity with TAKEOFF reference")

            self._validate_position_sensors()

            local = self._transport.local_pose
            if local is not None:
                current_yaw = local.yaw
            elif self.is_indoor:
                current_yaw = self._transport.vision_pose.yaw
            else:
                current_yaw = np.radians(90.0 - self.heading)

            takeoff_yaw = PositionUtils.get_yaw_from_pose(self._takeoff_position)

            vx_body, vy_body, vz_body = PositionUtils.transform_takeoff_to_body_velocities(
                vx, vy, vz, current_yaw, takeoff_yaw
            )
            vels = (float(vx_body), float(vy_body), float(vz_body))
        else:
            vels = (float(vx), float(vy), float(vz))

        self._node.get_logger().debug(
            f"Velocity cmd: vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} vyaw={vyaw:.2f} "
            f"ref={reference.name}"
        )

        if duration is None:
            self._transport.send_velocity_target(vels[0], vels[1], vels[2], float(vyaw), frame)
        else:
            rate = 1.0 / 50
            start = self._node.get_clock().now()
            dur = Duration(seconds=duration)

            while self._node.get_clock().now() - start < dur:
                self._transport.send_velocity_target(vels[0], vels[1], vels[2], float(vyaw), frame)
                self.delay(rate)

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        yaw: Optional[float] = None,
        reference: MoveReference = MoveReference.BODY,
        timeout: Optional[float] = 60.0,
        precision: float = 0.2,
        method: NavigationMethod = NavigationMethod.PID_EKF,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
    ) -> bool:
        """
        Move the drone to a position relative to its current location and heading.

        Parameters
        ----------
        x : float, optional
            Forward (+) / backward (-) in meters. For PID methods, None disables
            X-axis control; for POSITION methods, None means zero offset.
        y : float, optional
            Left (+) / right (-) in meters. For PID methods, None disables
            Y-axis control; for POSITION methods, None means zero offset.
        z : float, optional
            Up (+) / down (-) in meters. For PID methods, None disables altitude
            control; for POSITION methods, None means zero offset.
        yaw : float, optional
            Yaw angle in degrees. None maintains the current yaw.
        reference : MoveReference, default=BODY
            BODY: relative to current position/heading.
            TAKEOFF: absolute from the takeoff position/heading.
        timeout : float, optional, default=60.0
            Maximum navigation time in seconds.
        precision : float, default=0.2
            Arrival threshold in meters.
        method : NavigationMethod, default=PID_EKF
            PID_EKF: companion-side velocity PID with EKF-fused position.
            PID: companion-side velocity PID with raw sensors (vision/GPS).
            POSITION: onboard position controller (local setpoint).
            POSITION_GLOBAL: onboard GPS position controller (outdoor only).
        altitude_source : AltitudeSource, default=AUTO
            Altitude source for PID navigation:

            - AUTO: best available (lidar > vision Z > relative altitude).
            - LIDAR: rangefinder for ground-relative altitude. With BODY
              reference z is a relative offset from the current lidar reading;
              with TAKEOFF reference z is absolute altitude above ground.

        Returns
        -------
        bool
            True if the target is reached within precision.

        Raises
        ------
        TakeoffPositionNotSetError
            If reference=TAKEOFF but the takeoff position is not set.
        CapabilityNotSupportedError
            If reference=WORLD, or POSITION_GLOBAL indoors.
        SensorNotAvailableError
            If required position or altitude sensors are not available.

        See Also
        --------
        https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html
        """
        if reference == MoveReference.WORLD:
            raise CapabilityNotSupportedError(
                "WORLD reference in position control", self._config.name
            )

        if reference == MoveReference.TAKEOFF:
            takeoff = self._get_takeoff_for_method(method)
            if takeoff is None:
                raise TakeoffPositionNotSetError("move_to with TAKEOFF reference")

        self._validate_position_sensors(method)

        if z is not None:
            z = self._check_altitude_safety(z, reference)

        self._node.get_logger().info(
            f"move_to: x={x} y={y} z={z} yaw={yaw} ref={reference.name} "
            f"method={method.name} precision={precision}m "
            f"alt_source={altitude_source.name}"
        )
        self.delay(0.05)

        # POSITION_GLOBAL: GPS setpoint with AMSL correction (outdoor only)
        if method == NavigationMethod.POSITION_GLOBAL:
            if self.is_indoor:
                raise CapabilityNotSupportedError("POSITION_GLOBAL", "indoor mode")
            target = TargetComputer.compute_gps_setpoint(
                self.gps,
                self.heading,
                x,
                y,
                z,
                yaw,
                reference,
                self._takeoff_position if reference == MoveReference.TAKEOFF else None,
                self.rel_alt,
                self._initial_altitude,
            )
            check_alt = (
                TargetComputer.compute_target_rel_alt(self.rel_alt, z, reference)
                if z is not None
                else None
            )
            self._sync_wpnav_radius(precision)
            return self._navigator.navigate_setpoint(target, timeout, precision, check_alt)

        # POSITION: local position setpoint
        if method == NavigationMethod.POSITION:
            pos, yaw_rad = self._get_local_position()
            takeoff = self._takeoff_local if reference == MoveReference.TAKEOFF else None
            target = TargetComputer.compute_local_target(
                pos,
                yaw_rad,
                x,
                y,
                z,
                yaw,
                reference,
                takeoff,
            )
            self._sync_wpnav_radius(precision)
            return self._navigator.navigate_setpoint(target, timeout, precision)

        # PID methods (PID or PID_EKF)
        use_local = method == NavigationMethod.PID_EKF
        target = self._compute_pid_target(x, y, z, yaw, reference, method)
        active_axes = (x is not None, y is not None, z is not None)
        alt_target = self._navigator.resolve_altitude_target(z, reference, altitude_source)

        return self._navigator.navigate_pid(
            target=target,
            active_axes=active_axes,
            yaw=yaw,
            timeout=timeout,
            precision=precision,
            altitude_source=altitude_source,
            altitude_target=alt_target,
            use_local=use_local,
        )

    def move_to_gps(
        self,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        heading: Optional[float] = None,
        timeout: Optional[float] = 60.0,
        precision: float = 0.5,
        method: NavigationMethod = NavigationMethod.PID,
    ) -> bool:
        """
        Move the drone to a GPS coordinate.

        Parameters
        ----------
        latitude : float
            Target latitude in degrees (WGS84).
        longitude : float
            Target longitude in degrees (WGS84).
        altitude : float, optional
            Target altitude above ground in meters (relative). None keeps current.
        heading : float, optional
            Heading in degrees (0=North). None keeps current.
        timeout : float, optional, default=60.0
            Maximum navigation time in seconds.
        precision : float, default=0.5
            Arrival threshold in meters.
        method : NavigationMethod, default=PID
            PID: companion-side velocity PID with raw GPS.
            PID_EKF: companion-side velocity PID with EKF local position.
            POSITION_GLOBAL: onboard GPS position controller.

        Returns
        -------
        bool
            True if the target is reached within precision.

        Raises
        ------
        CapabilityNotSupportedError
            If indoor mode, or POSITION (local) is used with GPS coordinates.
        """
        if self.is_indoor:
            raise CapabilityNotSupportedError("GPS navigation", "indoor mode")

        if method == NavigationMethod.POSITION:
            raise CapabilityNotSupportedError(
                "POSITION (local) for GPS waypoints — use POSITION_GLOBAL",
                self._config.name,
            )

        self._validate_position_sensors(method)

        alt = altitude if altitude is not None else self.rel_alt
        hdg = heading if heading is not None else self.heading

        self._node.get_logger().info(
            f"move_to_gps: lat={latitude:.6f} lon={longitude:.6f} alt={alt:.1f}m "
            f"hdg={hdg:.1f}\u00b0 method={method.name} precision={precision}m"
        )

        # POSITION_GLOBAL: publish a GPS setpoint
        if method == NavigationMethod.POSITION_GLOBAL:
            target = GPSUtils.create_global_target(
                latitude, longitude, alt, hdg, self._initial_altitude
            )
            self._sync_wpnav_radius(precision)
            return self._navigator.navigate_setpoint(target, timeout, precision, check_alt=alt)

        # PID_EKF: convert GPS target to local NED and use EKF position
        if method == NavigationMethod.PID_EKF:
            target = TargetComputer.gps_to_local_target(
                latitude,
                longitude,
                alt,
                self.gps,
                self._transport.local_pose,
                self.rel_alt,
                hdg,
            )
            return self._navigator.navigate_pid(
                target=target,
                active_axes=(True, True, True),
                yaw=None,
                timeout=timeout,
                precision=precision,
                altitude_source=AltitudeSource.REL_ALT,
                altitude_target=alt,
                use_local=True,
            )

        # PID: raw GPS with geodesic error computation
        target = GPSUtils.create_global_target(
            latitude, longitude, alt, hdg, self._initial_altitude
        )
        return self._navigator.navigate_pid(
            target=target,
            active_axes=(True, True, True),
            yaw=None,
            timeout=timeout,
            precision=precision,
            altitude_source=AltitudeSource.REL_ALT,
            altitude_target=alt,
        )

    def _compute_pid_target(
        self,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference: MoveReference,
        method: NavigationMethod,
    ) -> Union[LocalTarget, GlobalTarget]:
        """Compute the target for PID navigation based on method and pose source."""
        takeoff = (
            self._get_takeoff_for_method(method) if reference == MoveReference.TAKEOFF else None
        )

        if method == NavigationMethod.PID_EKF:
            local = self._transport.local_pose
            return TargetComputer.compute_local_target(
                local.position,
                local.yaw,
                x,
                y,
                z,
                yaw,
                reference,
                takeoff,
            )

        if self.is_indoor:
            vision = self._transport.vision_pose
            return TargetComputer.compute_local_target(
                vision.position,
                vision.yaw,
                x,
                y,
                z,
                yaw,
                reference,
                takeoff,
            )

        # Outdoor PID with raw GPS
        return TargetComputer.compute_gps_target(
            self.gps,
            self.heading,
            x,
            y,
            z,
            yaw,
            reference,
            takeoff,
        )

    def _get_local_position(self) -> tuple:
        """Get (position, yaw) from EKF local position for setpoint navigation."""
        local = self._transport.local_pose
        if local is None:
            raise SensorNotAvailableError(
                "Local position",
                "POSITION requires EKF local position",
            )
        return local.position, local.yaw

    def _get_takeoff_for_method(self, method: NavigationMethod):
        """Get the appropriate takeoff position for a navigation method."""
        if method in (NavigationMethod.PID_EKF, NavigationMethod.POSITION):
            return self._takeoff_local
        return self._takeoff_position

    def _validate_position_sensors(self, method: NavigationMethod = NavigationMethod.PID) -> None:
        """Validate that the position sensors required by ``method`` are available."""
        if method in (NavigationMethod.PID_EKF, NavigationMethod.POSITION):
            if self._transport.local_pose is None:
                raise SensorNotAvailableError(
                    "Local position",
                    "PID_EKF/POSITION requires EKF local position",
                )
            return
        if self.is_indoor:
            if self._transport.vision_pose is None:
                raise SensorNotAvailableError("Vision pose", "navigation requires sensor data")
        else:
            if self._transport.gps is None:
                raise SensorNotAvailableError("GPS", "navigation requires sensor data")

    def _check_altitude_safety(self, z: float, reference: MoveReference) -> Optional[float]:
        """Reject z values that would target an altitude at or below ground level."""
        if reference == MoveReference.TAKEOFF:
            if z <= 0:
                self._node.get_logger().warn(
                    f"z={z} with TAKEOFF reference targets altitude ≤ 0. "
                    f"Ignoring z to prevent ground collision."
                )
                return None
        else:
            current_alt = self.get_altitude()
            if current_alt is not None and current_alt + z <= 0:
                self._node.get_logger().warn(
                    f"z={z} from current altitude {current_alt:.2f}m targets "
                    f"{current_alt + z:.2f}m (≤ 0). Ignoring z to prevent ground collision."
                )
                return None
        return z

    # Takeoff position management

    def _set_takeoff_position(self) -> bool:
        """Store current position as the takeoff reference (raw + local)."""
        try:
            pos = self.position_as_target
            if pos is None:
                self._node.get_logger().error("Cannot set takeoff position: No position data")
                return False
            self._takeoff_position = pos

            local = self._transport.local_pose
            if local is not None:
                self._takeoff_local = LocalTarget(
                    position=Vec3(local.position.x, local.position.y, local.position.z),
                    yaw=local.yaw,
                )
            else:
                self._takeoff_local = pos if isinstance(pos, LocalTarget) else None

            self._node.get_logger().info("Takeoff position set")
            return True
        except (SensorNotAvailableError, ValueError, AttributeError) as e:
            self._node.get_logger().error(f"Cannot set takeoff position: {e}")
            return False

    def set_takeoff_position(
        self,
        pose: Optional[Union[LocalPose, GeoPoint, LocalTarget, GlobalTarget]] = None,
        heading: Optional[float] = None,
    ) -> None:
        """
        Manually set the takeoff position for TAKEOFF reference frame and RTL.

        Parameters
        ----------
        pose : LocalPose | GeoPoint | LocalTarget | GlobalTarget, optional
            Position to use. If None, uses the current position.
        heading : float, optional
            Heading in degrees. Required if ``pose`` is a :class:`GeoPoint`.

        Raises
        ------
        ValueError
            If the pose type is not supported.
        """
        if pose is None:
            self._takeoff_position = self.position_as_target
            local = self._transport.local_pose
            if local is not None:
                self._takeoff_local = LocalTarget(
                    position=Vec3(local.position.x, local.position.y, local.position.z),
                    yaw=local.yaw,
                )
            elif isinstance(self._takeoff_position, LocalTarget):
                self._takeoff_local = self._takeoff_position
        elif isinstance(pose, LocalPose):
            target = LocalTarget(
                position=Vec3(pose.position.x, pose.position.y, pose.position.z),
                yaw=pose.yaw,
            )
            self._takeoff_local = target
            if self.is_indoor:
                self._takeoff_position = target
            else:
                self._node.get_logger().warn(
                    "Local pose provided outdoors: only _takeoff_local updated."
                )
        elif isinstance(pose, LocalTarget):
            self._takeoff_local = pose
            if self.is_indoor:
                self._takeoff_position = pose
            else:
                self._node.get_logger().warn(
                    "LocalTarget provided outdoors: only _takeoff_local updated."
                )
        elif isinstance(pose, GeoPoint) and heading is not None:
            self._takeoff_position = GlobalTarget(
                latitude=pose.latitude,
                longitude=pose.longitude,
                altitude=pose.altitude,
                yaw=math.radians(90.0 - heading),
            )
            local = self._transport.local_pose
            if local is not None:
                self._takeoff_local = LocalTarget(
                    position=Vec3(local.position.x, local.position.y, local.position.z),
                    yaw=local.yaw,
                )
        elif isinstance(pose, GlobalTarget):
            self._takeoff_position = pose
            local = self._transport.local_pose
            if local is not None:
                self._takeoff_local = LocalTarget(
                    position=Vec3(local.position.x, local.position.y, local.position.z),
                    yaw=local.yaw,
                )
        else:
            raise ValueError(f"Invalid pose type: {type(pose).__name__}")
        self._node.get_logger().info("Takeoff position set")

    def set_pid_config(self, config) -> None:
        """
        Update PID configuration.

        Parameters
        ----------
        config : str | dict | PositionPIDConfig
            YAML file path, configuration dictionary, or PositionPIDConfig.

        Raises
        ------
        TypeError
            If the config type is not supported.
        """
        if isinstance(config, str):
            self._pid_config = PositionPIDConfig.from_yaml(config)
        elif isinstance(config, dict):
            self._pid_config = PositionPIDConfig(
                x=PIDConfig.from_dict(config.get("x", {})),
                y=PIDConfig.from_dict(config.get("y", {})),
                z=PIDConfig.from_dict(config.get("z", {})),
                yaw=PIDConfig.from_dict(config.get("yaw", {})),
            )
        elif isinstance(config, PositionPIDConfig):
            self._pid_config = config
        else:
            raise TypeError(f"Invalid config type: {type(config)}")
        self._node.get_logger().info("PID configuration updated")

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

    # Vehicle commands

    def emergency_stop(self) -> None:
        """Execute emergency stop via force disarm."""
        self._node.get_logger().warn("Emergency stop triggered")
        self.disarm()

    def set_home(self) -> bool:
        """
        Set the current GPS position as home.

        Returns
        -------
        bool
            True if the home position was set, False on failure or timeout.

        See Also
        --------
        https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-set-home
        """
        try:
            return bool(self._transport.set_home(current=True))
        except TimeoutError as e:
            self._node.get_logger().error(f"Set home failed: {e}")
            return False

    def set_mode(self, mode: str) -> bool:
        """
        Set the FCU flight mode.

        Parameters
        ----------
        mode : str
            Flight mode name (e.g. 'GUIDED', 'STABILIZE', 'LOITER', 'RTL', 'LAND').

        Returns
        -------
        bool
            True only once the FCU reports the requested mode. False if the
            transport rejects the request or the mode is not confirmed within
            the timeout.

        See Also
        --------
        https://ardupilot.org/copter/docs/flight-modes.html
        """
        if not self._transport.set_mode(mode):
            return False
        if self._wait_until(lambda: (self.flight_mode or "").upper() == mode.upper(), 3.0):
            return True
        self._node.get_logger().error(
            f"{ERR} Mode '{mode}' not confirmed (still '{self.flight_mode}')"
        )
        return False

    def set_param(self, param_id: str, param_value: Union[int, float]) -> bool:
        """
        Set an ArduPilot parameter.

        Parameters
        ----------
        param_id : str
            Parameter name (e.g. 'RTL_ALT', 'WPNAV_SPEED').
        param_value : int or float
            Parameter value. Integers are sent as int, floats as double.

        Returns
        -------
        bool
            True if the parameter was set, False on failure or timeout.

        See Also
        --------
        https://ardupilot.org/dev/docs/mavlink-get-set-params.html
        """
        return self._transport.set_param(param_id, param_value)

    def set_speed(self, speed: float, speed_type: str = "horizontal") -> bool:
        """
        Change the speed limit at runtime via MAV_CMD_DO_CHANGE_SPEED.

        Immediately updates the position controller speed limits in the current
        flight mode (both position-hold and waypoint sub-modes).

        Parameters
        ----------
        speed : float
            Speed in m/s. Use -1 for no change, -2 to revert to default.
        speed_type : str, default="horizontal"
            Speed axis: "horizontal", "climb", or "descent".

        Returns
        -------
        bool
            True if the command was accepted, False on failure or timeout.

        See Also
        --------
        https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed
        """
        type_map = {"horizontal": 0, "climb": 1, "descent": 2}
        if speed_type not in type_map:
            self._node.get_logger().error(
                f"Invalid speed_type '{speed_type}'. Use: {list(type_map.keys())}"
            )
            return False
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

    def do_servo(self, aux_out: int, pwm_value: int) -> bool:
        """
        Control an auxiliary servo output via MAV_CMD_DO_SET_SERVO.

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
        """
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

    # Return to launch

    # ArduPilot v4.8+ renamed RTL params from centimeters to meters.
    _RTL_PARAM_ALIASES = {
        "RTL_ALT": "RTL_ALT_M",
        "RTL_ALT_FINAL": "RTL_ALT_FINAL_M",
    }

    def rtl(
        self,
        altitude: Optional[float] = None,
        precision: float = 0.2,
        method: RTLMethod = RTLMethod.NAVIGATE,
        land: bool = True,
    ) -> bool:
        """
        Return to launch position.

        Parameters
        ----------
        altitude : float, optional
            Transit altitude in meters. If set, climbs/descends before navigating.
        precision : float, default=0.2
            Arrival threshold in meters (used by the NAVIGATE method).
        method : RTLMethod, default=NAVIGATE
            NAVIGATE: SDK navigates to the takeoff position using position control.
            NATIVE: trigger ArduPilot's native RTL mode.
        land : bool, default=True
            Execute landing after reaching home.

        Returns
        -------
        bool
            True if RTL was successful.

        Raises
        ------
        TakeoffPositionNotSetError
            If method=NAVIGATE but the takeoff position is not set.
        """
        self._node.get_logger().info(f"RTL using method: {method.name}")

        if method == RTLMethod.NATIVE:
            return self._rtl_ardupilot(altitude, land)
        return self._rtl_pid(altitude, precision, land)

    def _rtl_ardupilot(self, altitude: Optional[float], land: bool) -> bool:
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

    def _rtl_pid(self, altitude: Optional[float], precision: float, land: bool) -> bool:
        if self._takeoff_position is None:
            raise TakeoffPositionNotSetError("RTL")

        if altitude is not None:
            target_z = altitude - (self.get_altitude() or 0.0)
            self._node.get_logger().info(f"Moving to RTL altitude: {altitude}m")
            self.move_to(
                x=0,
                y=0,
                z=target_z,
                precision=precision,
                method=NavigationMethod.PID_EKF,
            )

        self._node.get_logger().info("Navigating to takeoff position")
        self.move_to(
            x=0,
            y=0,
            z=0,
            reference=MoveReference.TAKEOFF,
            precision=precision,
            method=NavigationMethod.PID_EKF,
        )

        if land:
            self._node.get_logger().info("Landing")
            self.land()

        return True
