from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Union

import numpy as np
from geographic_msgs.msg import GeoPoseStamped
from mavros_msgs.msg import PositionTarget
from rclpy.duration import Duration

from nectar.control.exceptions import SensorNotAvailableError
from nectar.control.mavros.gps_utils import GPSUtils
from nectar.control.pid import PIDController
from nectar.control.types import AltitudeSource, MoveReference
from nectar.utils.position_utils import PositionUtils

if TYPE_CHECKING:
    from nectar.control.mavros.drone import MavrosDrone

LIDAR_ALTITUDE_LIMIT = 15.0  # meters


class MavrosNavigator:
    """
    Navigation controller for MavrosDrone.

    Handles PID velocity-based and FCU setpoint navigation for both
    local (PositionTarget) and GPS (GeoPoseStamped) targets.

    Parameters
    ----------
    drone : MavrosDrone
        Drone instance providing sensor data, publishers, and configuration.
    """

    def __init__(self, drone: MavrosDrone) -> None:
        self._drone = drone

    def navigate_pid(
        self,
        target: Union[PositionTarget, GeoPoseStamped],
        active_axes: tuple[bool, bool, bool],
        yaw: Optional[float],
        timeout: Optional[float],
        precision: float,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
        altitude_target: Optional[float] = None,
        use_local: bool = False,
    ) -> bool:
        """
        PID velocity-based navigation loop.

        Computes body-frame errors, feeds them into per-axis PID controllers,
        and publishes velocity commands until the target is reached or timeout.

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            Navigation target in the appropriate frame.
        active_axes : tuple[bool, bool, bool]
            Which axes are actively controlled (x, y, z).
        yaw : float, optional
            Target yaw in degrees. None disables yaw control.
        timeout : float, optional
            Maximum navigation time in seconds. None for no timeout.
        precision : float
            Arrival threshold in meters.
        altitude_source : AltitudeSource, default=AUTO
            Which sensor to read for altitude error computation.
        altitude_target : float, optional
            Absolute target value in the altitude source's frame.
        use_local : bool, default=False
            If True, use EKF local position for error computation (PID_LOCAL).

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.
        """
        drone = self._drone
        logger = drone.node.get_logger()

        pid_x = self._create_pid("x")
        pid_y = self._create_pid("y")
        pid_z = self._create_pid("z")
        pid_yaw = self._create_pid("yaw")

        self._log_target(target, altitude_source, altitude_target)

        start = drone.node.get_clock().now()
        timeout_dur = Duration(seconds=timeout) if timeout else None
        drone.obstacle_manager.reset_all()

        x_active, y_active, z_active = active_axes

        while True:
            drone.delay(0.01)

            if not drone.obstacle_manager.should_continue_navigation(drone):
                continue

            disable_x, disable_y, disable_z = drone.obstacle_manager.get_axis_control()

            dx, dy, dz, dyaw = self._compute_errors(
                target, yaw, altitude_source, altitude_target, use_local
            )

            axes = {
                "x": (x_active and not disable_x, dx, pid_x),
                "y": (y_active and not disable_y, dy, pid_y),
                "z": (z_active and not disable_z, dz, pid_z),
            }

            dead_zone = precision / 2
            vel = {}
            error_parts = []
            dist_sq = 0.0

            for name, (active, err, pid) in axes.items():
                v = pid.update(-err) if active else 0.0
                if abs(err) < dead_zone:
                    v = 0.0
                vel[name] = v
                if active:
                    error_parts.append(f"d{name}={err:.2f}")
                    dist_sq += err**2

            vyaw = pid_yaw.update(-dyaw) if yaw is not None else 0.0
            if yaw is not None:
                error_parts.append(f"dyaw={np.degrees(dyaw):.1f}\u00b0")

            distance = np.sqrt(dist_sq)

            logger.info(
                f"Distance: {distance:.2f}m | Error: {', '.join(error_parts)} | "
                f"Vel: vx={vel['x']:.2f}, vy={vel['y']:.2f}, "
                f"vz={vel['z']:.2f}, vyaw={vyaw:.2f}",
                throttle_duration_sec=0.5,
            )

            drone.move_velocity(vel["x"], vel["y"], vel["z"], vyaw)

            if distance <= precision:
                if yaw is not None and abs(dyaw) > np.radians(3):
                    continue
                drone.move_velocity(0.0, 0.0, 0.0, 0.0)
                logger.info(f"\033[32;1mTarget reached! Distance: {distance:.2f}m\033[0m")
                return True

            if timeout_dur and (drone.node.get_clock().now() - start) > timeout_dur:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0)
                logger.warn(f"\033[33;1mTimeout reached. Distance: {distance:.2f}m\033[0m")
                return False

    def navigate_setpoint(
        self,
        target: Union[PositionTarget, GeoPoseStamped],
        timeout: Optional[float],
        precision: float,
        check_alt: Optional[float] = None,
    ) -> bool:
        """
        Direct setpoint navigation loop.

        Publishes target to MAVROS topics and monitors distance until reached.

        For PositionTarget: publishes to local setpoint topic, checks
        Euclidean distance using local/vision pose.

        For GeoPoseStamped: publishes to GPS setpoint topic, checks
        geodesic distance using GPS and relative altitude.

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            Navigation target message.
        timeout : float, optional
            Maximum navigation time in seconds. None for no timeout.
        precision : float
            Arrival threshold in meters.
        check_alt : float, optional
            For GPS targets: relative altitude for arrival checking.

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.
        """
        drone = self._drone
        logger = drone.node.get_logger()
        is_gps = isinstance(target, GeoPoseStamped)

        if is_gps:
            tp = target.pose.position
            logger.info(
                f"Setpoint nav \u2192 GPS target: lat={tp.latitude:.6f}, "
                f"lon={tp.longitude:.6f}, alt={check_alt or 0:.1f}m"
            )
        else:
            tp = target.position
            logger.info(
                f"Setpoint nav \u2192 local target: x={tp.x:.2f}, y={tp.y:.2f}, z={tp.z:.2f}"
            )

        start = drone.node.get_clock().now()
        timeout_dur = Duration(seconds=timeout) if timeout else None

        while True:
            target.header.stamp = drone.node.get_clock().now().to_msg()
            drone.publish_setpoint(target)
            drone.delay(0.02)

            if is_gps:
                reached, distance = self._check_reached_gps(target, check_alt, precision)
            else:
                reached, distance = self._check_reached_local(target, precision)

            logger.info(
                f"Distance: {distance:.2f}m",
                throttle_duration_sec=0.5,
            )

            if reached:
                logger.info(f"\033[32;1mSetpoint reached! Distance: {distance:.2f}m\033[0m")
                return True

            if timeout_dur and (drone.node.get_clock().now() - start) > timeout_dur:
                logger.warn(f"\033[33;1mSetpoint timeout. Distance: {distance:.2f}m\033[0m")
                return False

    def resolve_altitude_target(
        self,
        z: Optional[float],
        reference: MoveReference,
        altitude_source: AltitudeSource,
    ) -> Optional[float]:
        """
        Compute the absolute altitude target for the given source and reference.

        Parameters
        ----------
        z : float, optional
            Altitude parameter from move_to. None disables altitude control.
        reference : MoveReference
            Movement reference frame.
        altitude_source : AltitudeSource
            Requested altitude source.

        Returns
        -------
        float or None
            Absolute target value, or None for default position-based altitude.

        Raises
        ------
        SensorNotAvailableError
            If LIDAR source requested but lidar data is not available.
        """
        if z is None:
            return None

        if altitude_source == AltitudeSource.LIDAR:
            return self._resolve_lidar_target(z, reference)

        if altitude_source == AltitudeSource.REL_ALT:
            return self._resolve_rel_alt_target(z, reference)

        # AUTO / VISION: use default position-based dz from get_body_distance
        return None

    def _resolve_lidar_target(self, z: float, reference: MoveReference) -> Optional[float]:
        """Compute absolute lidar target altitude."""
        if not self._drone.lidar_available:
            raise SensorNotAvailableError("Lidar", "altitude_source=LIDAR requires lidar data")

        current_lidar = self._drone.get_altitude(AltitudeSource.LIDAR)

        if reference == MoveReference.TAKEOFF:
            lidar_target = z
        else:
            lidar_target = current_lidar + z

        if lidar_target > LIDAR_ALTITUDE_LIMIT:
            self._drone.node.get_logger().warn(
                f"Lidar target {lidar_target:.1f}m exceeds limit "
                f"({LIDAR_ALTITUDE_LIMIT}m), falling back to position-based altitude"
            )
            return None

        return lidar_target

    def _resolve_rel_alt_target(self, z: float, reference: MoveReference) -> Optional[float]:
        """Compute absolute relative altitude target."""
        current_rel = self._drone.get_altitude(AltitudeSource.REL_ALT)

        if current_rel is None:
            return None

        if reference == MoveReference.TAKEOFF:
            return z
        return current_rel + z

    def _compute_errors(
        self,
        target: Union[PositionTarget, GeoPoseStamped],
        yaw: Optional[float],
        altitude_source: AltitudeSource,
        altitude_target: Optional[float],
        use_local: bool = False,
    ) -> tuple[float, float, float, float]:
        """
        Compute body-frame navigation errors.

        Parameters
        ----------
        target : PositionTarget | GeoPoseStamped
            Navigation target.
        yaw : float, optional
            Target yaw in degrees. None disables yaw error.
        altitude_source : AltitudeSource
            Altitude sensor source.
        altitude_target : float, optional
            Absolute target altitude in the source's frame.
        use_local : bool, default=False
            Use EKF local position instead of raw sensors.

        Returns
        -------
        tuple[float, float, float, float]
            (dx, dy, dz, dyaw) errors in body frame.
        """
        drone = self._drone

        if use_local:
            current = drone.local_pos
            hdg = None
        elif drone.is_indoor:
            current = drone.vision_pos
            hdg = None
        else:
            current = drone.position
            hdg = drone.heading

        dx, dy, dz = PositionUtils.get_body_distance(target, current, hdg)

        # Override dz when an explicit altitude target is provided
        if altitude_target is not None:
            dz = self._resolve_altitude_error(dz, altitude_source, altitude_target)

        # Compute yaw error
        if yaw is not None:
            if use_local:
                curr_yaw = PositionUtils.get_yaw_from_pose(drone.local_pos)
            elif drone.is_indoor:
                curr_yaw = PositionUtils.get_yaw_from_pose(drone.vision_pos)
            else:
                curr_yaw = np.radians(hdg)
            dyaw = PositionUtils.get_yaw_from_pose(target) - curr_yaw
            dyaw = (dyaw + np.pi) % (2 * np.pi) - np.pi
            if abs(dyaw) < np.radians(3):
                dyaw = 0.0
        else:
            dyaw = 0.0

        return dx, dy, dz, dyaw

    def _resolve_altitude_error(
        self,
        dz_default: float,
        altitude_source: AltitudeSource,
        altitude_target: float,
    ) -> float:
        """
        Compute altitude error from the configured source.

        Parameters
        ----------
        dz_default : float
            Default dz from position comparison (fallback).
        altitude_source : AltitudeSource
            Which sensor to read.
        altitude_target : float
            Desired absolute value in that sensor's frame.

        Returns
        -------
        float
            Altitude error (target - current).
        """
        current = self._drone.get_altitude(altitude_source)

        if current is not None:
            return altitude_target - current

        return dz_default

    def _check_reached_local(self, target: PositionTarget, precision: float) -> tuple[bool, float]:
        """
        Check arrival for local targets using EKF local position.

        Parameters
        ----------
        target : PositionTarget
            Local navigation target.
        precision : float
            Arrival threshold in meters.

        Returns
        -------
        tuple[bool, float]
            (reached, distance). Returns (False, inf) if local_pos unavailable.
        """
        local = self._drone.local_pos
        if local is None:
            return False, float("inf")

        current = local.pose.position
        dx = target.position.x - current.x
        dy = target.position.y - current.y
        dz = target.position.z - current.z
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        return distance <= precision, distance

    def _check_reached_gps(
        self,
        target: GeoPoseStamped,
        check_alt: Optional[float],
        precision: float,
    ) -> tuple[bool, float]:
        """
        Check arrival for GPS targets using geodesic distance.

        Parameters
        ----------
        target : GeoPoseStamped
            GPS navigation target.
        check_alt : float, optional
            Target relative altitude for vertical check.
        precision : float
            Arrival threshold in meters.

        Returns
        -------
        tuple[bool, float]
            (reached, horizontal_distance)
        """
        gps = self._drone.gps
        target_alt = check_alt if check_alt is not None else self._drone.rel_alt

        reached, dist, _ = GPSUtils.check_reached(
            gps.latitude,
            gps.longitude,
            self._drone.rel_alt,
            target.pose.position.latitude,
            target.pose.position.longitude,
            target_alt,
            precision,
        )
        return reached, dist

    def _create_pid(self, axis: str) -> PIDController:
        """
        Create PID controller for the specified axis from drone config.

        Parameters
        ----------
        axis : str
            Axis name ('x', 'y', 'z', 'yaw').

        Returns
        -------
        PIDController
        """
        cfg = getattr(self._drone.pid_config, axis, None)
        if cfg is None:
            return PIDController(kp=0.5, ki=0.1, output_limits=(-0.2, 0.2))
        return PIDController(
            kp=cfg.kp,
            ki=cfg.ki,
            kd=cfg.kd,
            output_limits=cfg.get_output_limits(),
            integral_limits=cfg.get_integral_limits(),
        )

    def _log_target(
        self,
        target: Union[PositionTarget, GeoPoseStamped],
        altitude_source: AltitudeSource,
        altitude_target: Optional[float],
    ) -> None:
        """Log navigation target details."""
        logger = self._drone.node.get_logger()

        if isinstance(target, GeoPoseStamped):
            tp = target.pose.position
            logger.info(
                f"PID nav: GPS target: lat={tp.latitude:.6f}, "
                f"lon={tp.longitude:.6f}, alt={tp.altitude:.1f}m"
            )
        else:
            tp = target.position
            logger.info(f"PID nav: local target: x={tp.x:.2f}, y={tp.y:.2f}, z={tp.z:.2f}")

        if altitude_target is not None:
            logger.info(
                f"PID nav: altitude target: {altitude_target:.2f}m (source={altitude_source.name})"
            )
