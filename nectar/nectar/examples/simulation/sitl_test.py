#!/usr/bin/env python3
"""
Atomic SITL tests — each test starts from a guaranteed clean hover.


Prerequisites:
    Terminal 1: make sim-start-gazebo   (or make sim-start for headless)
    Terminal 2: make sim-outdoor        (or make sim-indoor for indoor)

Usage:
    python3 sitl_test.py                  # all outdoor tests
    python3 sitl_test.py --indoor         # all indoor-compatible tests
    python3 sitl_test.py pid_fwd          # single test
    python3 sitl_test.py --indoor --group vel   # velocity group indoor
    python3 sitl_test.py --fresh pid_fwd  # land between tests
    python3 sitl_test.py --list           # list available tests
"""

import math
import sys
import time

import rclpy
from rclpy.node import Node

from nectar.control import (
    SITL_GPS_CONFIG,
    SITL_VISION_CONFIG,
    DroneFactory,
    MoveReference,
    NavigationStrategy,
    RTLStrategy,
)
from nectar.control.mavros.setpoint_config import SetpointNavConfig
from nectar.utils.position_utils import PositionUtils

# Helpers


def pos_xyz(local_pos) -> tuple:
    if local_pos is None:
        return (0.0, 0.0, 0.0)
    p = local_pos.pose.position
    return (p.x, p.y, p.z)


def pos_str(local_pos) -> str:
    if local_pos is None:
        return "None"
    p = local_pos.pose.position
    return f"x={p.x:.3f}, y={p.y:.3f}, z={p.z:.3f}"


def dist_2d(a: tuple, b: tuple) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def get_yaw_deg(local_pos) -> float:
    """Get ENU yaw from local pose, returned in degrees."""
    if local_pos is None:
        return 0.0
    return math.degrees(PositionUtils.get_yaw_from_pose(local_pos))


# Test runner


class SITLTest(Node):
    """Isolated SITL test runner."""

    ALTITUDE = 3.0

    def __init__(self, fresh: bool = False, indoor: bool = False):
        super().__init__("sitl_test")
        self.indoor = indoor
        config = SITL_VISION_CONFIG if indoor else SITL_GPS_CONFIG
        self.drone = DroneFactory.create("mavros", config, self)
        self.results: dict[str, bool] = {}
        self.fresh = fresh
        mode = "indoor (vision)" if indoor else "outdoor (GPS)"
        self.get_logger().info(
            f"SITLTest initialized — {mode} (reset={'land/takeoff' if fresh else 'LOITER'})"
        )

    # State management

    def ensure_airborne(self):
        """Takeoff if not already in the air."""
        d = self.drone
        rclpy.spin_once(self, timeout_sec=0.5)
        if not d.is_armed:
            self.get_logger().info(f"Taking off to {self.ALTITUDE}m...")
            if not d.takeoff(
                altitude=self.ALTITUDE,
                adjust_altitude=True,
                precision=0.2,
                timeout=30.0,
            ):
                self.get_logger().error("Takeoff FAILED — aborting")
                raise RuntimeError("Takeoff failed")
            d.delay(3.0)
            # SITL position controller is jerk-limited; raise PSC_JERK
            # from ArduPilot default (5 m/s³) so setpoint navigation is usable.

            if not d.set_param("PSC_JERK_XY", 50.0):
                d.set_param("PSC_JERK_NE", 50.0)
            self.get_logger().info(f"Airborne at {pos_str(d.local_pos)}")
        else:
            d.set_takeoff_position()
            self.get_logger().info(f"Already armed at {pos_str(d.local_pos)}")

    def reset_hover(self):
        """Reset to clean hover between tests.

        Stays in GUIDED mode and publishes zero velocity for 5s.
        NOTE: LOITER→GUIDED mode switch breaks ArduPilot SITL's
        velocity controller — all subsequent velocity commands are
        ignored until a land/retakeoff cycle.
        """
        d = self.drone

        if self.fresh:
            self.get_logger().info("  [reset] Landing for full reset...")
            d.land(timeout=20.0)
            d.delay(3.0)
            self.ensure_airborne()
            return

        # Light reset: zero velocity in GUIDED (no mode switch)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=5.0)

    def measure_drift(self, duration: float = 2.0) -> float:
        """Return 2D drift over `duration` seconds."""
        p0 = pos_xyz(self.drone.local_pos)
        self.drone.delay(duration)
        p1 = pos_xyz(self.drone.local_pos)
        return dist_2d(p0, p1)

    # L0: Sensors

    def test_sensors(self) -> bool:
        """Check that all required MAVROS topics are flowing."""
        d = self.drone
        d.delay(1.0)

        if self.indoor:
            checks = {
                "state": d.mavros_state is not None and d.is_fcu_connected,
                "vision_pos": d.vision_pos is not None,
                "local_pos": d.local_pos is not None,
                "imu": d._imu is not None,
            }
        else:
            checks = {
                "state": d.mavros_state is not None and d.is_fcu_connected,
                "gps": d.gps is not None and d.gps.latitude != 0.0,
                "heading": d.heading is not None and d.heading != 0.0,
                "local_pos": d.local_pos is not None,
                "imu": d._imu is not None,
            }

        for name, ok in checks.items():
            status = "OK" if ok else "MISSING"
            self.get_logger().info(f"  {name:15s} {status}")

        passed = all(checks.values())
        self._result(
            "SENSORS",
            passed,
            ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in checks.items()),
        )
        return passed

    # L1: Basic ops

    def test_set_speed(self) -> bool:
        """set_speed via MAV_CMD_DO_CHANGE_SPEED."""
        r1 = self.drone.set_speed(0.5, "horizontal")
        r2 = self.drone.set_speed(0.3, "climb")
        r3 = self.drone.set_speed(0.3, "descent")
        passed = r1 and r2 and r3
        self._result("SET_SPEED", passed, f"h={r1}, climb={r2}, desc={r3}")
        return passed

    # L2: Velocity

    def test_vel_fwd(self) -> bool:
        """Velocity forward 0.5 m/s for 5s, BODY frame."""
        return self._test_velocity("VEL_FWD", vx=0.5, vy=0.0, ref=MoveReference.BODY)

    def test_vel_lat(self) -> bool:
        """Velocity left 0.5 m/s for 5s, BODY frame."""
        return self._test_velocity("VEL_LAT", vx=0.0, vy=0.5, ref=MoveReference.BODY)

    def test_vel_up(self) -> bool:
        """Velocity up 0.3 m/s for 5s."""
        d = self.drone
        alt_before = d.get_altitude() or 0.0
        d.move_velocity(vx=0.0, vy=0.0, vz=0.3, duration=5.0)
        alt_after = d.get_altitude() or 0.0
        gained = alt_after - alt_before
        d.move_velocity(0.0, 0.0, -0.3, 0.0, duration=5.0)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        passed = gained > 0.3
        self._result("VEL_UP", passed, f"gained={gained:.3f}m")
        return passed

    def test_vel_takeoff(self) -> bool:
        """Velocity forward 0.5 m/s for 5s, TAKEOFF frame."""
        return self._test_velocity("VEL_TAKEOFF", vx=0.5, vy=0.0, ref=MoveReference.TAKEOFF)

    def test_vel_world(self) -> bool:
        """Velocity east 0.5 m/s for 5s, WORLD (ENU) frame."""
        d = self.drone
        p_before = pos_xyz(d.local_pos)

        # WORLD: vx=east, vy=north in ENU
        d.move_velocity(vx=0.5, vy=0.0, vz=0.0, duration=5.0, reference=MoveReference.WORLD)
        p_after = pos_xyz(d.local_pos)

        # local_pos is ENU: x=east, y=north
        dx_east = p_after[0] - p_before[0]
        dy_north = p_after[1] - p_before[1]
        total = dist_2d(p_before, p_after)

        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # Expect primarily eastward movement regardless of heading
        passed = total > 0.3 and dx_east > 0
        self._result(
            "VEL_WORLD",
            passed,
            f"east={dx_east:.3f}m, north={dy_north:.3f}m, total={total:.3f}m",
        )
        return passed

    def test_vel_world_north(self) -> bool:
        """WORLD frame: vy=+0.5 should move North (+Y in ENU local)."""
        d = self.drone
        p0 = pos_xyz(d.local_pos)

        d.move_velocity(vx=0.0, vy=0.5, vz=0.0, duration=5.0, reference=MoveReference.WORLD)
        p1 = pos_xyz(d.local_pos)

        dy_north = p1[1] - p0[1]
        dx_east = p1[0] - p0[0]
        total = dist_2d(p0, p1)

        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # Expect primarily northward movement
        passed = total > 0.3 and dy_north > 0 and abs(dy_north) > abs(dx_east)
        self._result(
            "VEL_WORLD_NORTH",
            passed,
            f"north={dy_north:.3f}m, east={dx_east:.3f}m, total={total:.3f}m",
        )
        return passed

    def test_vel_world_after_rotate(self) -> bool:
        """WORLD vx=+0.5 still goes East after 90° yaw rotation (heading-independent)."""
        d = self.drone

        # Rotate 90° CCW first
        d.move_to(
            x=0.0,
            y=0.0,
            yaw=90.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.3,
            timeout=20.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=2.0)
        yaw_after_rot = get_yaw_deg(d.local_pos)

        p0 = pos_xyz(d.local_pos)

        # WORLD vx=+0.5 should go East regardless of current heading
        d.move_velocity(vx=0.5, vy=0.0, vz=0.0, duration=5.0, reference=MoveReference.WORLD)
        p1 = pos_xyz(d.local_pos)

        dx_east = p1[0] - p0[0]
        dy_north = p1[1] - p0[1]
        total = dist_2d(p0, p1)

        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # Expect primarily eastward despite rotated heading
        passed = total > 0.3 and dx_east > 0 and abs(dx_east) > abs(dy_north)
        self._result(
            "VEL_WORLD_ROTATED",
            passed,
            f"east={dx_east:.3f}m, north={dy_north:.3f}m, total={total:.3f}m, "
            f"heading={yaw_after_rot:.1f}°",
        )
        return passed

    def test_heading_enu(self) -> bool:
        """Verify compass_hdg (NED) matches local_pos yaw (ENU) via 90-hdg conversion."""
        d = self.drone
        d.delay(1.0)

        hdg = d.heading  # NED: 0=North, CW
        local_yaw = get_yaw_deg(d.local_pos)  # ENU: 0=East, CCW
        converted = (90.0 - hdg + 180) % 360 - 180  # NED→ENU, normalized
        local_norm = (local_yaw + 180) % 360 - 180

        error = abs(((converted - local_norm) + 180) % 360 - 180)
        passed = error < 10.0  # within 10°
        self._result(
            "HEADING_ENU",
            passed,
            f"compass_hdg={hdg:.1f}° (NED), local_yaw={local_yaw:.1f}° (ENU), "
            f"90-hdg={converted:.1f}°, error={error:.1f}°",
        )
        return passed

    def test_brake(self) -> bool:
        """Move at 0.5 m/s then zero-velocity stop. Drift < 0.8m in SITL."""
        d = self.drone
        d.move_velocity(vx=0.5, vy=0.0, vz=0.0, duration=2.0, reference=MoveReference.BODY)
        p0 = pos_xyz(d.local_pos)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        d.delay(3.0)
        p1 = pos_xyz(d.local_pos)
        drift = dist_2d(p0, p1)

        passed = drift < 0.8
        self._result("BRAKE", passed, f"drift={drift:.3f}m")
        return passed

    def test_vel_yaw(self) -> bool:
        """Yaw rotation via velocity command: 30°/s for 3s ≈ 90° turn."""
        d = self.drone
        yaw_before = get_yaw_deg(d.local_pos)
        d.move_velocity(vx=0.0, vy=0.0, vz=0.0, vyaw=0.5, duration=3.5)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        yaw_after = get_yaw_deg(d.local_pos)

        # Yaw difference (shortest path)
        delta = (yaw_after - yaw_before + 180) % 360 - 180
        passed = abs(delta) > 15  # expect meaningful rotation
        self._result("VEL_YAW", passed, f"rotated={delta:.1f}° (expect ~90°)")
        return passed

    def _test_velocity(self, name: str, vx: float, vy: float, ref: MoveReference) -> bool:
        d = self.drone
        p_before = pos_xyz(d.local_pos)
        yaw_before = PositionUtils.get_yaw_from_pose(d.local_pos)

        d.move_velocity(vx=vx, vy=vy, vz=0.0, duration=5.0, reference=ref)
        p_after = pos_xyz(d.local_pos)
        total = dist_2d(p_before, p_after)

        dx = p_after[0] - p_before[0]
        dy = p_after[1] - p_before[1]
        fwd = dx * math.cos(yaw_before) + dy * math.sin(yaw_before)
        lat = -dx * math.sin(yaw_before) + dy * math.cos(yaw_before)

        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # SITL velocity ramp-up is slow; expect ~30-50% of commanded * duration
        passed = total > 0.3
        self._result(name, passed, f"fwd={fwd:.3f}m, lat={lat:.3f}m, total={total:.3f}m")
        return passed

    # L3: PID navigation

    def test_pid_fwd(self) -> bool:
        """PID (GPS) forward 2m, BODY frame."""
        return self._test_nav("PID_FWD", 2.0, 0.0, NavigationStrategy.PID)

    def test_pid_lat(self) -> bool:
        """PID (GPS) left 2m, BODY frame."""
        return self._test_nav("PID_LAT", 0.0, 2.0, NavigationStrategy.PID)

    def test_pid_alt(self) -> bool:
        """PID altitude: up 1m then down 1m."""
        d = self.drone
        alt0 = d.get_altitude() or 0.0

        r1 = d.move_to(z=1.0, precision=0.2, timeout=20.0, strategy=NavigationStrategy.PID)
        d.delay(2.0)
        alt_up = d.get_altitude() or 0.0

        r2 = d.move_to(z=-1.0, precision=0.2, timeout=20.0, strategy=NavigationStrategy.PID)
        d.delay(2.0)
        alt_dn = d.get_altitude() or 0.0

        ok_up = abs(alt_up - (alt0 + 1.0)) < 0.3
        ok_dn = abs(alt_dn - alt0) < 0.3
        passed = r1 and r2 and ok_up and ok_dn
        self._result(
            "PID_ALT",
            passed,
            f"up={alt_up:.2f}m (exp {alt0 + 1:.1f}), dn={alt_dn:.2f}m (exp {alt0:.1f})",
        )
        return passed

    def test_pid_yaw(self) -> bool:
        """PID move_to with yaw=90°, no position change."""
        return self._test_yaw("PID_YAW", NavigationStrategy.PID, 90.0)

    def test_pid_local_yaw(self) -> bool:
        """PID_LOCAL move_to with yaw=90°, no position change."""
        return self._test_yaw("PID_LOCAL_YAW", NavigationStrategy.PID_LOCAL, 90.0)

    def test_yaw_direction(self) -> bool:
        """Verify +90° rotates CCW and -90° rotates CW (ENU convention)."""
        d = self.drone

        # +90° should rotate CCW (positive delta in ENU)
        yaw0 = get_yaw_deg(d.local_pos)
        r1 = d.move_to(
            x=0.0,
            y=0.0,
            yaw=90.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.3,
            timeout=20.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        yaw1 = get_yaw_deg(d.local_pos)
        delta_ccw = (yaw1 - yaw0 + 180) % 360 - 180

        # -90° should rotate CW (negative delta in ENU)
        r2 = d.move_to(
            x=0.0,
            y=0.0,
            yaw=-90.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.3,
            timeout=20.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        yaw2 = get_yaw_deg(d.local_pos)
        delta_cw = (yaw2 - yaw1 + 180) % 360 - 180

        ccw_ok = r1 and delta_ccw > 60
        cw_ok = r2 and delta_cw < -60
        passed = ccw_ok and cw_ok
        self._result(
            "YAW_DIRECTION",
            passed,
            f"+90°→Δ={delta_ccw:.1f}° ({'CCW ✓' if delta_ccw > 0 else 'CW ✗'}), "
            f"-90°→Δ={delta_cw:.1f}° ({'CW ✓' if delta_cw < 0 else 'CCW ✗'})",
        )
        return passed

    def test_yaw_takeoff_ref(self) -> bool:
        """TAKEOFF ref yaw=0 returns to takeoff heading after rotation."""
        d = self.drone
        takeoff_yaw = get_yaw_deg(d.local_pos)

        # Rotate +60° from current
        d.move_to(
            x=0.0,
            y=0.0,
            yaw=60.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.3,
            timeout=20.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        after_rot = get_yaw_deg(d.local_pos)

        # TAKEOFF ref yaw=0 → should return to takeoff heading
        d.move_to(
            x=0.0,
            y=0.0,
            z=0.0,
            yaw=0.0,
            reference=MoveReference.TAKEOFF,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.3,
            timeout=20.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        final_yaw = get_yaw_deg(d.local_pos)

        error = abs(((final_yaw - takeoff_yaw) + 180) % 360 - 180)
        passed = error < 15.0
        self._result(
            "YAW_TAKEOFF_REF",
            passed,
            f"takeoff={takeoff_yaw:.1f}°, after+60°={after_rot:.1f}°, "
            f"after_return={final_yaw:.1f}°, error={error:.1f}°",
        )
        return passed

    def test_pid_local_fwd(self) -> bool:
        """PID_LOCAL (EKF) forward 2m, BODY frame."""
        return self._test_nav("PID_LOCAL_FWD", 2.0, 0.0, NavigationStrategy.PID_LOCAL)

    def test_pid_local_lat(self) -> bool:
        """PID_LOCAL (EKF) left 2m, BODY frame."""
        return self._test_nav("PID_LOCAL_LAT", 0.0, 2.0, NavigationStrategy.PID_LOCAL, yaw=0.0)

    # L4: Setpoint navigation

    def test_setpoint_fwd(self) -> bool:
        """SETPOINT forward 2m, BODY frame."""
        return self._test_nav("SETPOINT_FWD", 2.0, 0.0, NavigationStrategy.SETPOINT)

    def test_setpoint_lat(self) -> bool:
        """SETPOINT left 2m, BODY frame."""
        return self._test_nav("SETPOINT_LAT", 0.0, 2.0, NavigationStrategy.SETPOINT)

    def test_setpoint_global(self) -> bool:
        """SETPOINT_GLOBAL forward 2m."""
        return self._test_nav("SETPOINT_GLOBAL", 2.0, 0.0, NavigationStrategy.SETPOINT_GLOBAL)

    def test_setpoint_yaw(self) -> bool:
        """SETPOINT move_to with yaw=90°, no position change."""
        return self._test_yaw("SETPOINT_YAW", NavigationStrategy.SETPOINT, 90.0)

    def test_setpoint_global_yaw(self) -> bool:
        """SETPOINT_GLOBAL move_to with yaw=90°."""
        return self._test_yaw("SETPOINT_GLOBAL_YAW", NavigationStrategy.SETPOINT_GLOBAL, 90.0)

    def test_setpoint_wpnav(self) -> bool:
        """SETPOINT with WPNav S-curve (GUID_OPTIONS=65), custom speed/radius.

        Also raises WP_JERK (default 1 m/s³) to match PSC_JERK_NE tuning
        """
        d = self.drone
        log = self.get_logger()

        # Save original config
        orig_cfg = d.setpoint_config

        # Raise WP_JERK from default 1 to 50 (same idea as PSC_JERK_NE)
        d.set_param("WP_JERK", 50.0)
        log.info("  Set WP_JERK=50")

        # Apply WPNav config: bit 6 = S-curve, speed=3 m/s, radius=0.5m
        wpnav_cfg = SetpointNavConfig(guid_options=65, speed=3.0, accel=1.5, radius=0.5)
        d.set_setpoint_config(wpnav_cfg)
        log.info("  Applied WPNav config: guid_options=65, speed=3, radius=0.5")

        p_before = pos_xyz(d.local_pos)
        t0 = time.time()
        try:
            result = d.move_to(
                x=2.0,
                reference=MoveReference.BODY,
                strategy=NavigationStrategy.SETPOINT,
                precision=0.5,
                timeout=30.0,
            )
        except Exception as e:
            log.error(f"  SETPOINT_WPNAV exception: {e}")
            result = False
        elapsed = time.time() - t0
        p_after = pos_xyz(d.local_pos)
        moved = dist_2d(p_before, p_after)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # Restore WP_JERK and original config
        d.set_param("WP_JERK", 1.0)
        if orig_cfg:
            d.set_setpoint_config(orig_cfg)

        self._result(
            "SETPOINT_WPNAV",
            result,
            f"time={elapsed:.1f}s, moved={moved:.3f}m, "
            f"{'REACHED' if result else 'TIMEOUT'} (WP_JERK=50)",
        )
        return result

    # L5: RTL

    def test_rtl_pid(self) -> bool:
        """Move forward 3m then RTL PID back to takeoff."""
        d = self.drone

        d.move_to(
            x=3.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID,
            precision=0.2,
            timeout=30.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        result = d.rtl(precision=0.2, strategy=RTLStrategy.PID, land=False)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        p_after = pos_xyz(d.local_pos)
        takeoff = d._takeoff_local
        if takeoff:
            tp = (takeoff.position.x, takeoff.position.y)
            error = dist_2d(p_after, tp)
        else:
            error = float("inf")

        passed = result and error < 1.0
        self._result("RTL_PID", passed, f"returned={result}, error={error:.3f}m")
        return passed

    def test_rtl_ardupilot(self) -> bool:
        """Move forward 3m then RTL ArduPilot (FCU native)."""
        d = self.drone

        d.move_to(
            x=3.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID,
            precision=0.2,
            timeout=30.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        result = d.rtl(strategy=RTLStrategy.ARDUPILOT, land=False)
        if result:
            d.delay(16.0)  # wait for ArduPilot to navigate back
            # ArduPilot RTL switches mode; switch back to GUIDED
            d.set_mode("GUIDED")
            d.delay(2.0)

        p_after = pos_xyz(d.local_pos)
        takeoff = d._takeoff_local
        if takeoff:
            tp = (takeoff.position.x, takeoff.position.y)
            error = dist_2d(p_after, tp)
        else:
            error = float("inf")

        passed = result and error < 2.0
        self._result("RTL_ARDUPILOT", passed, f"returned={result}, error={error:.3f}m")
        return passed

    # L6: Compound

    def test_sequential(self) -> bool:
        """PID fwd 2m → measure drift → PID_LOCAL lat 2m.

        Tests whether residual drift from PID contaminates PID_LOCAL.
        """
        d = self.drone

        # Step 1: PID forward
        self.get_logger().info("  [seq] PID forward 2m...")
        r1 = d.move_to(
            x=2.0,
            y=0.0,
            z=0.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID,
            precision=0.2,
            timeout=30.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        drift = self.measure_drift(2.0)
        self.get_logger().info(f"  [seq] Drift after PID: {drift:.3f}m")

        # Step 2: PID_LOCAL lateral
        self.get_logger().info("  [seq] PID_LOCAL left 2m...")
        r2 = d.move_to(
            x=0.0,
            y=2.0,
            z=0.0,
            yaw=0.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID_LOCAL,
            precision=0.2,
            timeout=30.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        passed = r1 and r2
        self._result(
            "SEQUENTIAL",
            passed,
            f"pid={'OK' if r1 else 'FAIL'}, pid_local={'OK' if r2 else 'FAIL'}, drift={drift:.3f}m",
        )
        return passed

    def test_takeoff_ref(self) -> bool:
        """Move forward 2m (PID), then return to TAKEOFF origin."""
        d = self.drone

        d.move_to(
            x=2.0,
            y=0.0,
            z=0.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID,
            precision=0.2,
            timeout=30.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
        d.delay(2.0)

        result = d.move_to(
            x=0.0,
            y=0.0,
            z=0.0,
            yaw=0.0,
            reference=MoveReference.TAKEOFF,
            strategy=NavigationStrategy.PID,
            precision=0.2,
            timeout=45.0,
        )
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        p = pos_xyz(d.local_pos)
        takeoff = d._takeoff_local
        if takeoff:
            tp = (takeoff.position.x, takeoff.position.y, takeoff.position.z)
            error = dist_2d(p, tp)
        else:
            error = float("inf")

        passed = result and error < 0.5
        self._result("TAKEOFF_REF", passed, f"returned={result}, error={error:.3f}m")
        return passed

    # L7: Square patterns

    def test_sq_pid(self) -> bool:
        """Square 3m: PID + BODY."""
        return self._test_square("SQ_PID", NavigationStrategy.PID)

    def test_sq_pid_takeoff(self) -> bool:
        """Square 3m: PID + TAKEOFF."""
        return self._test_square("SQ_PID_TAKEOFF", NavigationStrategy.PID, MoveReference.TAKEOFF)

    def test_sq_pid_local(self) -> bool:
        """Square 3m: PID_LOCAL + BODY."""
        return self._test_square("SQ_PID_LOCAL", NavigationStrategy.PID_LOCAL)

    def test_sq_setpoint(self) -> bool:
        """Square 3m: SETPOINT + BODY."""
        return self._test_square("SQ_SETPOINT", NavigationStrategy.SETPOINT, timeout=45.0)

    def test_sq_setpoint_global(self) -> bool:
        """Square 3m: SETPOINT_GLOBAL + BODY."""
        return self._test_square("SQ_SETPOINT_GLOBAL", NavigationStrategy.SETPOINT_GLOBAL)

    def test_sq_wpnav(self) -> bool:
        """Square 3m: SETPOINT + WPNav S-curve (GUID_OPTIONS=65)."""
        d = self.drone
        orig_cfg = d.setpoint_config
        d.set_param("WP_JERK", 50.0)
        wpnav_cfg = SetpointNavConfig(guid_options=65, speed=3.0, accel=1.5, radius=0.5)
        d.set_setpoint_config(wpnav_cfg)
        try:
            result = self._test_square("SQ_WPNAV", NavigationStrategy.SETPOINT, timeout=45.0)
        finally:
            d.set_param("WP_JERK", 1.0)
            if orig_cfg:
                d.set_setpoint_config(orig_cfg)
        return result

    # Internal

    def _test_square(
        self,
        name: str,
        strategy: NavigationStrategy,
        reference: MoveReference = MoveReference.BODY,
        side: float = 3.0,
        precision: float = 0.2,
        timeout: float = 30.0,
    ) -> bool:
        """Fly a square pattern and check closing error."""
        d = self.drone
        log = self.get_logger()
        p_start = pos_xyz(d.local_pos)

        if reference == MoveReference.TAKEOFF:
            legs = [
                (side, 0.0, f"→({side:.0f},0)"),
                (side, side, f"→({side:.0f},{side:.0f})"),
                (0.0, side, f"→(0,{side:.0f})"),
                (0.0, 0.0, "→(0,0)"),
            ]
        else:
            legs = [
                (side, 0.0, "fwd"),
                (0.0, side, "left"),
                (-side, 0.0, "back"),
                (0.0, -side, "right"),
            ]

        legs_ok = 0
        for i, (x, y, label) in enumerate(legs, 1):
            log.info(f"  [{name}] Leg {i}/4: {label}")
            t0 = time.time()
            try:
                result = d.move_to(
                    x=x,
                    y=y,
                    reference=reference,
                    strategy=strategy,
                    precision=precision,
                    timeout=timeout,
                )
            except Exception as e:
                log.error(f"  [{name}] Leg {i} exception: {e}")
                result = False
            elapsed = time.time() - t0
            p = pos_xyz(d.local_pos)
            status = "OK" if result else "FAIL"
            log.info(f"  [{name}] Leg {i}: {status} ({elapsed:.1f}s) pos=({p[0]:.2f}, {p[1]:.2f})")
            d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)
            if result:
                legs_ok += 1

        p_end = pos_xyz(d.local_pos)
        closing = dist_2d(p_start, p_end)
        passed = legs_ok == 4 and closing < 1.0

        self._result(
            name,
            passed,
            f"legs={legs_ok}/4, closing_error={closing:.3f}m",
        )
        return passed

    def _test_nav(
        self,
        name: str,
        x: float,
        y: float,
        strategy: NavigationStrategy,
        yaw=None,
        precision: float = 0.2,
        timeout: float = 30.0,
    ) -> bool:
        """Generic move_to test from current hover position."""
        d = self.drone
        p_before = pos_xyz(d.local_pos)

        t0 = time.time()
        try:
            result = d.move_to(
                x=x if x != 0.0 else None,
                y=y if y != 0.0 else None,
                z=None,
                yaw=yaw,
                reference=MoveReference.BODY,
                strategy=strategy,
                precision=precision,
                timeout=timeout,
            )
        except Exception as e:
            self.get_logger().error(f"  {name} exception: {e}")
            self._result(name, False, f"exception: {e}")
            return False
        elapsed = time.time() - t0

        p_after = pos_xyz(d.local_pos)
        moved = dist_2d(p_before, p_after)
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        self._result(
            name,
            result,
            f"time={elapsed:.1f}s, moved={moved:.3f}m, {'REACHED' if result else 'TIMEOUT'}",
        )
        return result

    def _test_yaw(
        self,
        name: str,
        strategy: NavigationStrategy,
        target_yaw_deg: float,
        timeout: float = 20.0,
    ) -> bool:
        """Test yaw rotation via move_to with yaw parameter, no XY movement."""
        d = self.drone
        yaw_before = get_yaw_deg(d.local_pos)

        t0 = time.time()
        try:
            result = d.move_to(
                x=0.0,
                y=0.0,
                yaw=target_yaw_deg,
                reference=MoveReference.BODY,
                strategy=strategy,
                precision=0.3,
                timeout=timeout,
            )
        except Exception as e:
            self.get_logger().error(f"  {name} exception: {e}")
            self._result(name, False, f"exception: {e}")
            return False
        elapsed = time.time() - t0

        yaw_after = get_yaw_deg(d.local_pos)
        delta = (yaw_after - yaw_before + 180) % 360 - 180
        d.move_velocity(0.0, 0.0, 0.0, 0.0, duration=1.0)

        # Expect rotation close to target (within 15°), including direction
        yaw_ok = abs(delta - target_yaw_deg) < 15
        passed = result and yaw_ok
        self._result(
            name,
            passed,
            f"time={elapsed:.1f}s, rotated={delta:.1f}° (target={target_yaw_deg}°), "
            f"{'REACHED' if result else 'TIMEOUT'}",
        )
        return passed

    def _header(self, title: str):
        self.get_logger().info(f"\n{'=' * 60}")
        self.get_logger().info(f"TEST: {title}")
        self.get_logger().info(f"{'=' * 60}")

    def _result(self, name: str, passed: bool, detail: str = ""):
        status = "\033[32;1mPASS\033[0m" if passed else "\033[31;1mFAIL\033[0m"
        msg = f"  [{status}] {name}"
        if detail:
            msg += f" — {detail}"
        self.get_logger().info(msg)
        self.results[name] = passed


# Registry

TESTS = {
    # L0: Sensors
    "sensors": "test_sensors",
    "set_speed": "test_set_speed",
    "heading_enu": "test_heading_enu",
    # L2: Velocity
    "vel_fwd": "test_vel_fwd",
    "vel_lat": "test_vel_lat",
    "vel_up": "test_vel_up",
    "vel_yaw": "test_vel_yaw",
    "vel_takeoff": "test_vel_takeoff",
    "vel_world": "test_vel_world",
    "vel_world_north": "test_vel_world_north",
    "vel_world_rotated": "test_vel_world_after_rotate",
    "brake": "test_brake",
    # L3: PID navigation
    "pid_fwd": "test_pid_fwd",
    "pid_lat": "test_pid_lat",
    "pid_alt": "test_pid_alt",
    "pid_yaw": "test_pid_yaw",
    "yaw_direction": "test_yaw_direction",
    "yaw_takeoff_ref": "test_yaw_takeoff_ref",
    "pid_local_fwd": "test_pid_local_fwd",
    "pid_local_lat": "test_pid_local_lat",
    "pid_local_yaw": "test_pid_local_yaw",
    # L4: Setpoint navigation
    "setpoint_fwd": "test_setpoint_fwd",
    "setpoint_lat": "test_setpoint_lat",
    "setpoint_yaw": "test_setpoint_yaw",
    "setpoint_global": "test_setpoint_global",
    "setpoint_global_yaw": "test_setpoint_global_yaw",
    "setpoint_wpnav": "test_setpoint_wpnav",
    # L5: RTL
    "rtl_pid": "test_rtl_pid",
    "rtl_ardupilot": "test_rtl_ardupilot",
    # L6: Compound
    "sequential": "test_sequential",
    "takeoff_ref": "test_takeoff_ref",
    # L7: Square patterns
    "sq_pid": "test_sq_pid",
    "sq_pid_takeoff": "test_sq_pid_takeoff",
    "sq_pid_local": "test_sq_pid_local",
    "sq_setpoint": "test_sq_setpoint",
    "sq_setpoint_global": "test_sq_setpoint_global",
    "sq_wpnav": "test_sq_wpnav",
}

GROUPS = {
    "vel": [
        "vel_fwd",
        "vel_lat",
        "vel_up",
        "vel_yaw",
        "vel_takeoff",
        "vel_world",
        "vel_world_north",
        "vel_world_rotated",
        "brake",
    ],
    "pid": ["pid_fwd", "pid_lat", "pid_alt", "pid_yaw"],
    "pid_local": ["pid_local_fwd", "pid_local_lat", "pid_local_yaw"],
    "setpoint": ["setpoint_fwd", "setpoint_lat", "setpoint_yaw"],
    "setpoint_global": ["setpoint_global", "setpoint_global_yaw"],
    "wpnav": ["setpoint_wpnav"],
    "rtl": ["rtl_pid", "rtl_ardupilot"],
    "yaw": [
        "vel_yaw",
        "pid_yaw",
        "pid_local_yaw",
        "setpoint_yaw",
        "setpoint_global_yaw",
        "yaw_direction",
        "yaw_takeoff_ref",
    ],
    "world": ["vel_world", "vel_world_north", "vel_world_rotated"],
    "nav": ["pid_fwd", "pid_lat", "pid_local_fwd", "pid_local_lat"],
    "compound": ["sequential", "takeoff_ref"],
    "square": [
        "sq_pid",
        "sq_pid_takeoff",
        "sq_pid_local",
        "sq_setpoint",
        "sq_setpoint_global",
        "sq_wpnav",
    ],
    "all": list(TESTS.keys()),
}

# Tests that don't require airborne state
PRE_FLIGHT_TESTS = {"sensors", "set_speed", "heading_enu"}

# Tests that require GPS (skipped with --indoor)
GPS_ONLY_TESTS = {
    "heading_enu",
    "setpoint_global",
    "setpoint_global_yaw",
    "sq_setpoint_global",
    "rtl_ardupilot",
}


def main():
    if "--list" in sys.argv:
        print("Tests:")
        for name, method in TESTS.items():
            gps_tag = " [GPS]" if name in GPS_ONLY_TESTS else ""
            func = getattr(SITLTest, method, None)
            doc = func.__doc__.strip().split("\n")[0] if func and func.__doc__ else ""
            print(f"  {name:20s} {doc}{gps_tag}")
        print("\nGroups:")
        for name, tests in GROUPS.items():
            print(f"  {name:20s} {', '.join(tests)}")
        print("\nFlags:")
        print("  --indoor             Use SITL_VISION_CONFIG (skip GPS-only tests)")
        print("  --fresh              Land between tests for full reset")
        return

    fresh = "--fresh" in sys.argv
    indoor = "--indoor" in sys.argv

    # Parse test names
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        args = ["all"]

    # Expand groups
    test_names = []
    for arg in args:
        if arg in GROUPS:
            test_names.extend(GROUPS[arg])
        elif arg in TESTS:
            test_names.append(arg)
        else:
            print(f"Unknown test or group: '{arg}'")
            print("Use --list to see available tests")
            sys.exit(1)

    # Deduplicate preserving order
    seen = set()
    test_names = [t for t in test_names if not (t in seen or seen.add(t))]

    # Skip GPS-only tests when indoor
    if indoor:
        skipped = [t for t in test_names if t in GPS_ONLY_TESTS]
        test_names = [t for t in test_names if t not in GPS_ONLY_TESTS]
        if skipped:
            print(f"Indoor mode: skipping GPS-only tests: {', '.join(skipped)}")

    rclpy.init()
    node = SITLTest(fresh=fresh, indoor=indoor)

    try:
        mode = "indoor (vision)" if indoor else "outdoor (GPS)"
        node.get_logger().info(f"\n{'═' * 60}")
        node.get_logger().info(f"  SITL TEST — {len(test_names)} test(s) [{mode}]")
        node.get_logger().info(f"  Tests: {', '.join(test_names)}")
        node.get_logger().info(f"  Reset: {'land/takeoff' if fresh else 'LOITER'}")
        node.get_logger().info(f"{'═' * 60}")

        # Pre-flight tests (don't need airborne)
        pre = [t for t in test_names if t in PRE_FLIGHT_TESTS]
        flight = [t for t in test_names if t not in PRE_FLIGHT_TESTS]

        for name in pre:
            node._header(name)
            method = getattr(node, TESTS[name])
            try:
                method()
            except Exception as e:
                node.get_logger().error(f"Test {name} raised: {e}")
                node.results[name] = False

        if flight:
            node.ensure_airborne()

            for i, name in enumerate(flight):
                if i > 0:
                    node.get_logger().info("\n  ── reset between tests ──")
                    node.reset_hover()

                node._header(name)
                method = getattr(node, TESTS[name])
                try:
                    method()
                except Exception as e:
                    node.get_logger().error(f"Test {name} raised: {e}")
                    import traceback

                    traceback.print_exc()
                    node.results[name] = False

        # Summary
        node.get_logger().info(f"\n{'═' * 60}")
        node.get_logger().info("  SUMMARY")
        node.get_logger().info(f"{'═' * 60}")

        passed = failed = 0
        for name, result in node.results.items():
            status = "\033[32;1mPASS\033[0m" if result else "\033[31;1mFAIL\033[0m"
            node.get_logger().info(f"  {name:25s} {status}")
            if result:
                passed += 1
            else:
                failed += 1

        node.get_logger().info(f"{'─' * 60}")
        node.get_logger().info(
            f"  Total: {passed + failed} | "
            f"\033[32;1m{passed} passed\033[0m | "
            f"\033[31;1m{failed} failed\033[0m"
        )

        if flight:
            node.get_logger().info("\nLanding...")
            node.drone.land(timeout=30.0)

    except KeyboardInterrupt:
        node.get_logger().info("Interrupted — landing")
        node.drone.land()
    except Exception as e:
        node.get_logger().error(f"Error: {e}")
        import traceback

        traceback.print_exc()
        try:
            node.drone.land()
        except Exception:
            pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
