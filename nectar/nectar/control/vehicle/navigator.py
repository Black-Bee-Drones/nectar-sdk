"""Navigation loops for multicopter vehicles."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Union

import numpy as np
from rclpy.duration import Duration

from nectar.control.exceptions import SensorNotAvailableError
from nectar.control.pid import PIDController
from nectar.control.types import AltitudeSource, MoveReference
from nectar.control.vehicle.gps_utils import GPSUtils
from nectar.control.vehicle.types import GlobalTarget, LocalTarget
from nectar.utils.position_utils import PositionUtils

if TYPE_CHECKING:
    from nectar.control.vehicle.drone import VehicleDrone

LIDAR_ALTITUDE_LIMIT = 15.0  # meters
DEFAULT_PRECISION_YAW_DEG = 3.0
DEFAULT_SETTLE_TIME = 0.15
_ARRIVAL_BRAKE_S = 0.4


def resolve_precisions(
    precision: float,
    precision_z: Optional[float] = None,
    precision_yaw: Optional[float] = None,
) -> tuple[float, float, float]:
    """Return ``(xy_m, z_m, yaw_rad)`` with None meaning inherit defaults."""
    z = precision if precision_z is None else precision_z
    yaw_deg = DEFAULT_PRECISION_YAW_DEG if precision_yaw is None else precision_yaw
    return precision, z, math.radians(yaw_deg)


def cylinder_errors(
    dx: float,
    dy: float,
    dz: float,
    dyaw: float,
    x_on: bool,
    y_on: bool,
    z_on: bool,
    yaw_on: bool,
) -> tuple[float, float, float]:
    """XY hypot, |z|, |yaw| for active axes. Inactive axes report 0."""
    xy_sq = 0.0
    if x_on:
        xy_sq += dx * dx
    if y_on:
        xy_sq += dy * dy
    xy = math.sqrt(xy_sq) if (x_on or y_on) else 0.0
    z = abs(dz) if z_on else 0.0
    yaw = abs(dyaw) if yaw_on else 0.0
    return xy, z, yaw


def inside_cylinder(
    xy: float,
    z: float,
    yaw: float,
    precision_xy: float,
    precision_z: float,
    precision_yaw: float,
) -> bool:
    """True when all reported errors (inactive axes already 0) are inside."""
    return xy <= precision_xy and z <= precision_z and yaw <= precision_yaw


def _held_s(now, since) -> float:
    return (now - since).nanoseconds * 1e-9


class VehicleNavigator:
    """
    Navigation controller for :class:`VehicleDrone`.

    Handles PID velocity-based and FCU setpoint navigation for both local
    (:class:`LocalTarget`) and global (:class:`GlobalTarget`) targets.

    Parameters
    ----------
    drone : VehicleDrone
        Drone instance providing telemetry, setpoint egress, and configuration.
    """

    def __init__(self, drone: "VehicleDrone") -> None:
        self._drone = drone

    def navigate_pid(
        self,
        target: Union[LocalTarget, GlobalTarget],
        active_axes: tuple[bool, bool, bool],
        yaw: Optional[float],
        timeout: Optional[float],
        precision: float,
        altitude_source: AltitudeSource = AltitudeSource.AUTO,
        altitude_target: Optional[float] = None,
        use_local: bool = False,
        precision_z: Optional[float] = None,
        precision_yaw: Optional[float] = None,
        settle_time: float = DEFAULT_SETTLE_TIME,
    ) -> bool:
        """
        PID velocity-based navigation loop.

        Computes body-frame errors, feeds them into per-axis PID controllers,
        and publishes velocity commands until the target is held inside the
        arrival cylinder for ``settle_time``, or timeout.

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.
        """
        drone = self._drone
        logger = drone.node.get_logger()
        prec_xy, prec_z, prec_yaw = resolve_precisions(precision, precision_z, precision_yaw)
        yaw_on = yaw is not None

        pid_x = self._create_pid("x")
        pid_y = self._create_pid("y")
        pid_z = self._create_pid("z")
        pid_yaw = self._create_pid("yaw")

        self._log_target(target, altitude_source, altitude_target)
        logger.info(
            f"PID nav: precision xy\u2264{prec_xy:.2f}m  z\u2264{prec_z:.2f}m  "
            f"yaw\u2264{math.degrees(prec_yaw):.1f}\u00b0  settle={settle_time:.2f}s"
        )

        start = drone.node.get_clock().now()
        timeout_dur = Duration(seconds=timeout) if timeout else None
        drone.obstacle_manager.reset_all()

        x_active, y_active, z_active = active_axes

        # Align yaw before translating to prevent body-frame errors from
        # rotating during simultaneous yaw + position PID control.
        if yaw_on and (x_active or y_active):
            aligned = self._align_yaw(target, pid_yaw, start, timeout_dur, use_local, prec_yaw)
            if not aligned:
                return False
            pid_yaw.reset()
            # World-frame target projects onto both body axes after yaw change
            x_active = True
            y_active = True

        inside_since = None

        while True:
            drone.delay(0.01)

            if not drone.obstacle_manager.should_continue_navigation(drone):
                inside_since = None
                continue

            disable_x, disable_y, disable_z = drone.obstacle_manager.get_axis_control()

            dx, dy, dz, dyaw = self._compute_errors(
                target, yaw, altitude_source, altitude_target, use_local
            )

            x_on = x_active and not disable_x
            y_on = y_active and not disable_y
            z_on = z_active and not disable_z

            vel = {
                "x": pid_x.update(-dx) if x_on else 0.0,
                "y": pid_y.update(-dy) if y_on else 0.0,
                "z": pid_z.update(-dz) if z_on else 0.0,
            }
            vyaw = pid_yaw.update(-dyaw) if yaw_on else 0.0

            xy, z_err, yaw_err = cylinder_errors(dx, dy, dz, dyaw, x_on, y_on, z_on, yaw_on)
            inside = inside_cylinder(xy, z_err, yaw_err, prec_xy, prec_z, prec_yaw)

            now = drone.node.get_clock().now()
            settled, inside_since, held = self._settle(inside, inside_since, now, settle_time)

            logger.info(
                self._arrival_log(
                    xy,
                    z_err,
                    yaw_err,
                    x_on,
                    y_on,
                    z_on,
                    yaw_on,
                    vel,
                    vyaw,
                    inside,
                    held,
                    settle_time,
                ),
                throttle_duration_sec=0.5,
            )

            drone.move_velocity(vel["x"], vel["y"], vel["z"], vyaw)

            if settled:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=_ARRIVAL_BRAKE_S)
                logger.info(
                    f"\033[32;1mReached  {self._arrival_summary(xy, z_err, yaw_err, yaw_on)}"
                    f"  (held {held:.2f}s)\033[0m"
                )
                return True

            if timeout_dur and (now - start) > timeout_dur:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=_ARRIVAL_BRAKE_S)
                logger.warn(
                    f"\033[33;1mTimeout  {self._arrival_summary(xy, z_err, yaw_err, yaw_on)}\033[0m"
                )
                return False

    def navigate_setpoint(
        self,
        target: Union[LocalTarget, GlobalTarget],
        timeout: Optional[float],
        precision: float,
        check_alt: Optional[float] = None,
        precision_z: Optional[float] = None,
        precision_yaw: Optional[float] = None,
        settle_time: float = DEFAULT_SETTLE_TIME,
    ) -> bool:
        """
        Direct setpoint navigation loop.

        Sends the target to the transport and monitors the arrival cylinder
        until held for ``settle_time``.

        For :class:`LocalTarget`: XY hypot + |z| using EKF local position.
        For :class:`GlobalTarget`: geodesic XY + relative altitude.

        Returns
        -------
        bool
            True if target reached within precision, False on timeout.
        """
        drone = self._drone
        logger = drone.node.get_logger()
        is_gps = isinstance(target, GlobalTarget)
        target_yaw = PositionUtils.get_yaw_from_pose(target)
        prec_xy, prec_z, prec_yaw = resolve_precisions(precision, precision_z, precision_yaw)
        z_on = (not is_gps) or check_alt is not None

        if is_gps:
            logger.info(
                f"Setpoint nav \u2192 GPS target: lat={target.latitude:.6f}, "
                f"lon={target.longitude:.6f}, alt={check_alt or 0:.1f}m, "
                f"yaw={np.degrees(target_yaw):.1f}\u00b0"
            )
        else:
            tp = target.position
            logger.info(
                f"Setpoint nav \u2192 local target: x={tp.x:.2f}, y={tp.y:.2f}, "
                f"z={tp.z:.2f}, yaw={np.degrees(target_yaw):.1f}\u00b0"
            )
        logger.info(
            f"Setpoint nav: precision xy\u2264{prec_xy:.2f}m  z\u2264{prec_z:.2f}m  "
            f"yaw\u2264{math.degrees(prec_yaw):.1f}\u00b0  settle={settle_time:.2f}s"
        )

        start = drone.node.get_clock().now()
        timeout_dur = Duration(seconds=timeout) if timeout else None
        inside_since = None

        drone.publish_setpoint(target)

        while True:
            drone.delay(0.1)

            if is_gps:
                dx, dy, dz, xy = self._gps_errors(target, check_alt)
            else:
                dx, dy, dz, xy = self._local_errors(target)

            curr_yaw = self._get_current_yaw(use_local=not is_gps)
            dyaw = PositionUtils.compute_yaw_error(target_yaw, curr_yaw)
            z_err = abs(dz) if z_on else 0.0
            yaw_err = abs(dyaw)
            xy_report = xy if math.isfinite(xy) else float("inf")
            inside = math.isfinite(xy_report) and inside_cylinder(
                xy_report, z_err, yaw_err, prec_xy, prec_z, prec_yaw
            )

            now = drone.node.get_clock().now()
            settled, inside_since, held = self._settle(inside, inside_since, now, settle_time)

            settle_txt = f"  settle {held:.2f}/{settle_time:.2f}s" if inside else ""
            logger.info(
                f"xy={xy_report:.2f}m  z={z_err:.2f}m  "
                f"yaw={np.degrees(dyaw):.1f}\u00b0{settle_txt}",
                throttle_duration_sec=0.5,
            )

            if settled:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=_ARRIVAL_BRAKE_S)
                logger.info(
                    f"\033[32;1mReached  {self._arrival_summary(xy_report, z_err, yaw_err, True)}"
                    f"  (held {held:.2f}s)\033[0m"
                )
                return True

            if timeout_dur and (now - start) > timeout_dur:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=_ARRIVAL_BRAKE_S)
                logger.warn(
                    f"\033[33;1mTimeout  {self._arrival_summary(xy_report, z_err, yaw_err, True)}\033[0m"
                )
                return False

    def resolve_altitude_target(
        self,
        z: Optional[float],
        reference: MoveReference,
        altitude_source: AltitudeSource,
    ) -> Optional[float]:
        """
        Compute the absolute altitude target for the given source and reference.

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

    def _get_current_yaw(self, use_local: bool = False) -> float:
        """
        Get current yaw from the appropriate sensor source.

        Returns
        -------
        float
            Current yaw in radians (ENU).
        """
        drone = self._drone
        if use_local:
            return PositionUtils.get_yaw_from_pose(drone.local_pose)
        if drone.is_indoor:
            return PositionUtils.get_yaw_from_pose(drone.vision_pose)
        # Convert compass heading (NED: 0=North, CW) to ENU yaw (0=East, CCW)
        # to match target yaw (always ENU).
        return np.radians(90.0 - drone.heading)

    def _compute_errors(
        self,
        target: Union[LocalTarget, GlobalTarget],
        yaw: Optional[float],
        altitude_source: AltitudeSource,
        altitude_target: Optional[float],
        use_local: bool = False,
    ) -> tuple[float, float, float, float]:
        """
        Compute body-frame navigation errors.

        Returns
        -------
        tuple[float, float, float, float]
            (dx, dy, dz, dyaw) errors in body frame.
        """
        drone = self._drone

        if use_local:
            current = drone.local_pose
            hdg = None
        elif drone.is_indoor:
            current = drone.vision_pose
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
            curr_yaw = self._get_current_yaw(use_local)
            target_yaw = PositionUtils.get_yaw_from_pose(target)
            dyaw = PositionUtils.compute_yaw_error(target_yaw, curr_yaw)
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

        Returns
        -------
        float
            Altitude error (target - current), or ``dz_default`` if unavailable.
        """
        current = self._drone.get_altitude(altitude_source)

        if current is not None:
            return altitude_target - current

        return dz_default

    def _align_yaw(
        self,
        target,
        pid_yaw: "PIDController",
        start,
        timeout_dur: Optional[Duration],
        use_local: bool,
        precision_yaw: float,
    ) -> bool:
        """
        Rotate to target yaw before starting position control.

        Returns
        -------
        bool
            True if yaw aligned, False on timeout.
        """
        drone = self._drone
        logger = drone.node.get_logger()
        target_yaw = PositionUtils.get_yaw_from_pose(target)

        logger.info(
            f"Yaw alignment \u2192 {np.degrees(target_yaw):.1f}\u00b0  "
            f"(\u2264{math.degrees(precision_yaw):.1f}\u00b0)"
        )

        while True:
            drone.delay(0.01)

            if not drone.obstacle_manager.should_continue_navigation(drone):
                continue

            curr_yaw = self._get_current_yaw(use_local)
            dyaw = PositionUtils.compute_yaw_error(target_yaw, curr_yaw)

            if abs(dyaw) <= precision_yaw:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=0.1)
                logger.info(f"\033[32;1mYaw aligned  {np.degrees(curr_yaw):.1f}\u00b0\033[0m")
                return True

            vyaw = pid_yaw.update(-dyaw)
            drone.move_velocity(0.0, 0.0, 0.0, vyaw)

            logger.info(
                f"Yaw align: dyaw={np.degrees(dyaw):.1f}\u00b0  vyaw={vyaw:.2f}",
                throttle_duration_sec=0.5,
            )

            if timeout_dur and (drone.node.get_clock().now() - start) > timeout_dur:
                drone.move_velocity(0.0, 0.0, 0.0, 0.0, duration=_ARRIVAL_BRAKE_S)
                logger.warn("\033[33;1mTimeout during yaw alignment\033[0m")
                return False

    def _local_errors(self, target: LocalTarget) -> tuple[float, float, float, float]:
        """ENU errors and XY hypot. ``inf`` if local_pose is unavailable."""
        local = self._drone.local_pose
        if local is None:
            inf = float("inf")
            return inf, inf, inf, inf

        current = local.position
        dx = target.position.x - current.x
        dy = target.position.y - current.y
        dz = target.position.z - current.z
        return dx, dy, dz, math.hypot(dx, dy)

    def _gps_errors(
        self,
        target: GlobalTarget,
        check_alt: Optional[float],
    ) -> tuple[float, float, float, float]:
        """East/north/alt errors and geodesic XY distance."""
        gps = self._drone.gps
        current_alt = self._drone.rel_alt if check_alt is not None else 0.0
        target_alt = check_alt if check_alt is not None else 0.0

        _, dist, _ = GPSUtils.check_reached(
            gps.latitude,
            gps.longitude,
            current_alt,
            target.latitude,
            target.longitude,
            target_alt,
            precision_radius=float("inf"),
            alt_threshold=float("inf"),
        )
        east, north = GPSUtils.local_offset(
            gps.latitude, gps.longitude, target.latitude, target.longitude
        )
        dz = target_alt - current_alt if check_alt is not None else 0.0
        return east, north, dz, dist

    def _create_pid(self, axis: str) -> PIDController:
        """Create PID controller for the specified axis from drone config."""
        cfg = getattr(self._drone.pid_config, axis, None)
        if cfg is None:
            return PIDController(kp=0.5, ki=0.1, output_limits=(-0.2, 0.2))
        return PIDController(
            kp=cfg.kp,
            ki=cfg.ki,
            kd=cfg.kd,
            output_limits=cfg.get_output_limits(),
            integral_limits=cfg.get_integral_limits(),
            output_deadband=cfg.output_deadband,
        )

    @staticmethod
    def _settle(inside: bool, inside_since, now, settle_time: float):
        if not inside:
            return False, None, 0.0
        if inside_since is None:
            inside_since = now
        held = _held_s(now, inside_since)
        if settle_time <= 0.0:
            return True, inside_since, held
        return held >= settle_time, inside_since, held

    @staticmethod
    def _arrival_summary(xy: float, z: float, yaw: float, yaw_on: bool) -> str:
        parts = [f"xy={xy:.2f}m", f"z={z:.2f}m"]
        if yaw_on:
            parts.append(f"yaw={math.degrees(yaw):.1f}\u00b0")
        return "  ".join(parts)

    @staticmethod
    def _arrival_log(
        xy: float,
        z: float,
        yaw: float,
        x_on: bool,
        y_on: bool,
        z_on: bool,
        yaw_on: bool,
        vel: dict,
        vyaw: float,
        inside: bool,
        held: float,
        settle_time: float,
    ) -> str:
        parts = []
        if x_on or y_on:
            parts.append(f"xy={xy:.2f}m")
        if z_on:
            parts.append(f"z={z:.2f}m")
        if yaw_on:
            parts.append(f"yaw={math.degrees(yaw):.1f}\u00b0")
        err = "  ".join(parts) if parts else "-"
        cmd = f"vx={vel['x']:.2f}  vy={vel['y']:.2f}  vz={vel['z']:.2f}  vyaw={vyaw:.2f}"
        if inside:
            return f"{err}  |  {cmd}  |  settle {held:.2f}/{settle_time:.2f}s"
        return f"{err}  |  {cmd}"

    def _log_target(
        self,
        target: Union[LocalTarget, GlobalTarget],
        altitude_source: AltitudeSource,
        altitude_target: Optional[float],
    ) -> None:
        """Log navigation target details."""
        logger = self._drone.node.get_logger()
        target_yaw = np.degrees(PositionUtils.get_yaw_from_pose(target))

        if isinstance(target, GlobalTarget):
            logger.info(
                f"PID nav: GPS target: lat={target.latitude:.6f}, "
                f"lon={target.longitude:.6f}, alt={target.altitude:.1f}m, "
                f"yaw={target_yaw:.1f}\u00b0"
            )
        else:
            tp = target.position
            logger.info(
                f"PID nav: local target: x={tp.x:.2f}, y={tp.y:.2f}, "
                f"z={tp.z:.2f}, yaw={target_yaw:.1f}\u00b0"
            )

        if altitude_target is not None:
            logger.info(
                f"PID nav: altitude target: {altitude_target:.2f}m (source={altitude_source.name})"
            )
