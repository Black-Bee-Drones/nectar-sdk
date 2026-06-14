#!/usr/bin/env python3
import argparse
import csv
import logging
import math
import time
from pathlib import Path
from typing import Optional

import nectar
from nectar.control import (
    DroneFactory,
    MavlinkConfig,
    MavrosConfig,
    MoveReference,
    NavigationMethod,
    PoseSource,
)
from nectar.utils.gps_calculate import GPSCalculate

log = logging.getLogger("navigation_test")

AVAILABLE_TESTS = [
    "body",
    "takeoff-ref",
    "altitude",
    "velocity",
    "gps",
    "figure8",
    "rectangle",
    "cube-xyz",
    "cube",
    "gps-rectangle",
]

STRATEGY_MAP = {
    "pid": NavigationMethod.PID,
    "pid-ekf": NavigationMethod.PID_EKF,
    "position": NavigationMethod.POSITION,
    "position-global": NavigationMethod.POSITION_GLOBAL,
}


def _fmt(v: Optional[float]) -> str:
    return f"{v:+.3f}" if isinstance(v, (int, float)) else "n/a"


def _csv_num(v: Optional[float]) -> str:
    return f"{v:.4f}" if isinstance(v, (int, float)) else ""


class NavigationTest:
    """ArduPilot (MAVROS/MAVLink) navigation test driver."""

    def __init__(self, args: argparse.Namespace):
        self.args = args

        pose_source = PoseSource.VISION if args.mode == "indoor" else PoseSource.GPS
        if args.drone == "mavlink":
            kwargs = {"pose_source": pose_source, "start_driver": False}
            if args.connection:
                kwargs["connection_string"] = args.connection
            config = MavlinkConfig(**kwargs)
        else:
            config = MavrosConfig(pose_source=pose_source, start_driver=False)
        self.drone = DroneFactory.create(args.drone, config)

        self.dist = args.distance
        self.prec = args.precision
        self.tout = args.timeout
        self.method = STRATEGY_MAP.get(args.strategy, NavigationMethod.PID)
        self._csv_path: Optional[Path] = Path(args.csv).expanduser() if args.csv else None
        self._csv_writer = None
        self._csv_file = None
        self._battery_sub = None
        self._battery_msg = None

        if self._csv_path is not None:
            new_file = not self._csv_path.exists()
            self._csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._csv_file = self._csv_path.open("a", newline="")
            self._csv_writer = csv.writer(self._csv_file)
            if new_file:
                self._csv_writer.writerow(
                    [
                        "timestamp",
                        "test",
                        "leg",
                        "label",
                        "method",
                        "reference",
                        "target_x",
                        "target_y",
                        "target_z",
                        "target_yaw_deg",
                        "actual_local_x",
                        "actual_local_y",
                        "actual_local_z",
                        "actual_yaw_deg",
                        "duration_s",
                        "reached",
                    ]
                )

        log.info(
            "Initialized | mode=%s | method=%s | no_takeoff=%s | distance=%sm | precision=%sm | timeout=%ss | csv=%s",
            args.mode,
            args.strategy,
            args.no_takeoff,
            self.dist,
            self.prec,
            self.tout,
            self._csv_path or "off",
        )

    def setup(self) -> bool:
        """
        Prepare drone for testing.

        Normal mode: arm → takeoff → stabilize.
        No-takeoff mode: set GUIDED mode → set takeoff position (hand-held testing).

        Returns
        -------
        bool
            True if setup successful.
        """
        if self.args.no_takeoff:
            if not self.drone.set_mode("GUIDED"):
                log.error("Failed to set GUIDED mode")
                return False
            self.drone.delay(1.0)
            self.drone.set_takeoff_position()
            log.info("NO-TAKEOFF MODE: takeoff position set to current; drone will NOT arm")
            return True

        if not self.drone.takeoff(altitude=self.args.altitude):
            log.error("Takeoff failed")
            return False
        self.drone.delay(3.0)
        return True

    def teardown(self) -> None:
        if self.args.no_takeoff:
            log.info("No-takeoff mode: nothing to teardown")
        else:
            log.info("Landing...")
            self.drone.land()
        if self._csv_file is not None:
            self._csv_file.close()
            log.info("CSV written: %s", self._csv_path)

    def test_body(self) -> bool:
        """BODY reference square pattern (clockwise: forward, right, back, left)."""
        d = self.dist
        self._log_test_header("BODY Square", f"{d}m sides")

        waypoints = [
            (d, 0.0, None, "Forward"),
            (0.0, -d, None, "Right"),
            (-d, 0.0, None, "Backward"),
            (0.0, d, None, "Left (return)"),
        ]

        all_reached = True
        for x, y, z, label in waypoints:
            log.info(f"  → {label}: x={x}, y={y}")
            reached = self.drone.move_to(
                x=x,
                y=y,
                z=z,
                reference=MoveReference.BODY,
                precision=self.prec,
                timeout=self.tout,
                method=self.method,
            )
            if not reached:
                log.warning(f"  ⚠ {label}: timeout")
                all_reached = False
            self.drone.delay(1.5)

        self._log_test_result("BODY Square", all_reached)
        return all_reached

    def test_takeoff_ref(self) -> bool:
        """
        TAKEOFF reference absolute positioning.
        """
        d = self.dist
        self._log_test_header("TAKEOFF Reference", f"{d}m offsets")

        waypoints = [
            (d, 0.0, None, f"{d}m forward from takeoff"),
            (d, -d, None, f"{d}m forward + {d}m right from takeoff"),
            (0.0, d, None, f"{d}m left from takeoff"),
            (0.0, 0.0, None, "Return to takeoff XY"),
        ]

        all_reached = True
        for x, y, z, label in waypoints:
            log.info(f"  → {label}: x={x}, y={y}")
            reached = self.drone.move_to(
                x=x,
                y=y,
                z=z,
                reference=MoveReference.TAKEOFF,
                precision=self.prec,
                timeout=self.tout,
                method=self.method,
            )
            if not reached:
                log.warning(f"  ⚠ {label}: timeout")
                all_reached = False
            self.drone.delay(1.5)

        self._log_test_result("TAKEOFF Reference", all_reached)
        return all_reached

    def test_altitude(self) -> bool:
        """
        Vertical-only control using BODY reference.

        Moves up then down by half the configured distance.
        x=None, y=None disables horizontal control.
        """
        dz = self.dist / 2
        self._log_test_header("Altitude", f"±{dz}m")

        log.info(f"  → Up {dz}m")
        r1 = self.drone.move_to(
            z=dz,
            precision=self.prec,
            timeout=self.tout,
            method=self.method,
        )
        self.drone.delay(1.5)

        log.info(f"  → Down {dz}m")
        r2 = self.drone.move_to(
            z=-dz,
            precision=self.prec,
            timeout=self.tout,
            method=self.method,
        )
        self.drone.delay(1.0)

        result = r1 and r2
        self._log_test_result("Altitude", result)
        return result

    def test_velocity(self) -> bool:
        """
        Timed velocity commands in BODY and TAKEOFF frames.
        """
        vel = 0.3
        dur = 2.0
        self._log_test_header("Velocity", f"{vel} m/s × {dur}s")

        steps = [
            (MoveReference.BODY, vel, 0.0, "BODY forward"),
            (MoveReference.BODY, 0.0, vel, "BODY left"),
            (MoveReference.TAKEOFF, vel, 0.0, "TAKEOFF forward"),
            (MoveReference.TAKEOFF, 0.0, vel, "TAKEOFF left"),
        ]

        for ref, vx, vy, label in steps:
            log.info(f"  → {label}: vx={vx}, vy={vy}")
            self.drone.move_velocity(vx=vx, vy=vy, duration=dur, reference=ref)
            self.drone.move_velocity(0.0, 0.0, 0.0, 0.0)
            self.drone.delay(1.5)

        self._log_test_result("Velocity", True)
        return True

    def test_gps(self) -> bool:
        """
        GPS waypoint navigation (outdoor only).
        """
        if self.args.mode == "indoor":
            log.warning("GPS test skipped: not available in indoor mode")
            return False

        self._log_test_header("GPS Navigation", f"{self.dist}m forward")

        gps = self.drone.gps
        hdg = self.drone.heading

        log.info(f"  Current: lat={gps.latitude:.6f}, lon={gps.longitude:.6f}, hdg={hdg:.1f}°")

        lat, lon, _ = GPSCalculate.calculate_gps_offset(
            self.dist,
            0.0,
            0.0,
            gps.latitude,
            gps.longitude,
            gps.altitude,
            hdg,
        )

        log.info(f"  → Target: lat={lat:.6f}, lon={lon:.6f}")
        gps_prec = max(self.prec, 0.5)

        # move_to_gps supports PID, PID_EKF, and POSITION_GLOBAL (not POSITION)
        gps_method = self.method
        if gps_method == NavigationMethod.POSITION:
            gps_method = NavigationMethod.POSITION_GLOBAL

        reached = self.drone.move_to_gps(
            latitude=lat,
            longitude=lon,
            precision=gps_prec,
            timeout=self.tout,
            method=gps_method,
        )
        if not reached:
            log.warning("  ⚠ GPS waypoint: timeout")

        self._log_test_result("GPS Navigation", reached)
        return reached

    def test_figure8(self) -> bool:
        """
        Figure-8 pattern using TAKEOFF reference.

        Two diamonds (forward and backward) sharing the origin, 8 waypoints total.
        Tests sequential precision and return-to-origin accuracy.

        ::

                  (d, 0)
                  /    \
            (d/2,-d/2) (d/2, d/2)
                  \\    /
            ─── (0, 0) ───
                  /    \
           (-d/2,-d/2) (-d/2, d/2)
                  \\    /
                 (-d, 0)
        """
        d = self.dist
        h = d / 2
        self._log_test_header("Figure-8", f"{d}m diamonds")

        waypoints = [
            (h, h, None, "Front-left"),
            (d, 0.0, None, "Front apex"),
            (h, -h, None, "Front-right"),
            (0.0, 0.0, None, "Center (cross)"),
            (-h, h, None, "Rear-left"),
            (-d, 0.0, None, "Rear apex"),
            (-h, -h, None, "Rear-right"),
            (0.0, 0.0, None, "Origin (return)"),
        ]

        return self._run_waypoints("Figure-8", waypoints, MoveReference.TAKEOFF)

    def test_rectangle(self) -> bool:
        """
        Rectangle with midpoints using TAKEOFF reference (8 waypoints).

        Visits corners and edge midpoints for denser precision sampling.

        ::

            (d, d/2) ── (d, 0) ── (d, -d/2)
               |                      |
            (0, d/2)              (0, -d/2)
               |                      |
            (-d, d/2)──(-d, 0)──(-d, -d/2)  (not visited, returns to origin)
        """
        d = self.dist
        h = d / 2
        self._log_test_header("Rectangle 8-pt", f"{d}×{d}m")

        waypoints = [
            (h, 0.0, None, "Front mid"),
            (d, 0.0, None, "Front-right corner"),
            (d, h, None, "Right mid-front"),
            (d, d, None, "Right-back corner"),
            (h, d, None, "Back mid"),
            (0.0, d, None, "Left-back corner"),
            (0.0, h, None, "Left mid-front"),
            (0.0, 0.0, None, "Origin (return)"),
        ]

        return self._run_waypoints("Rectangle 8-pt", waypoints, MoveReference.TAKEOFF)

    def test_cube_xyz(self) -> bool:
        """3-axis cube using BODY reference (8 closed-loop legs, CW, front first).

        Each leg is a relative offset from the drone's current pose. The
        offsets sum to (0, 0, 0), so the drone returns to its starting
        pose at the end of every iteration -- safe to run under ``--loop``.

        Requires ``--altitude > --distance`` so the final descend doesn't
        hit the ground-collision safety check.
        """
        d = self.dist
        self._log_test_header("Cube XYZ (BODY, no yaw)", f"{d}m side")

        waypoints = [
            # bottom face (CW from above)
            (d, 0.0, 0.0, "1: forward"),
            (0.0, -d, 0.0, "2: right"),
            (-d, 0.0, 0.0, "3: back"),
            # vertical
            (0.0, 0.0, d, "4: climb"),
            # top face (CW from above)
            (d, 0.0, 0.0, "5: forward (top)"),
            (0.0, d, 0.0, "6: left (top)"),
            (-d, 0.0, 0.0, "7: back (top)"),
            # close
            (0.0, 0.0, -d, "8: descend home"),
        ]

        return self._run_waypoints("Cube XYZ", waypoints, MoveReference.BODY)

    def test_cube(self) -> bool:
        """4-axis cube using BODY reference (10 closed-loop legs, CW, front first).

        Same 8-corner geometry as :meth:`test_cube_xyz` plus two
        pure-rotation legs (+90, -90) at the top altitude to stress yaw
        control without polluting the translation geometry. All offsets
        sum to (0, 0, 0, 0deg), so position and heading return to start
        every iteration -- safe under ``--loop``.

        Requires ``--altitude > --distance``.
        """
        d = self.dist
        self._log_test_header("Cube 4-axis (BODY)", f"{d}m side, yaw +/-90 at top")

        waypoints = [
            # x,    y,    z,    yaw_deg,  label
            (d, 0.0, 0.0, None, "1: forward"),
            (0.0, -d, 0.0, None, "2: right"),
            (-d, 0.0, 0.0, None, "3: back"),
            (0.0, 0.0, d, None, "4: climb"),
            (None, None, None, 90.0, "5: yaw +90 (pure rotation)"),
            (None, None, None, -90.0, "6: yaw -90 (back to home heading)"),
            (d, 0.0, 0.0, None, "7: forward (top)"),
            (0.0, d, 0.0, None, "8: left (top)"),
            (-d, 0.0, 0.0, None, "9: back (top)"),
            (0.0, 0.0, -d, None, "10: descend home"),
        ]

        return self._run_waypoints("Cube 4-axis", waypoints, MoveReference.BODY)

    def test_gps_rectangle(self) -> bool:
        """
        GPS rectangle using move_to_gps (outdoor only, 4 corners).

        Computes GPS waypoints offset from current position at current heading.
        """
        if self.args.mode == "indoor":
            log.warning("GPS rectangle skipped: not available in indoor mode")
            return False

        d = self.dist
        self._log_test_header("GPS Rectangle", f"{d}m sides")

        gps = self.drone.gps
        hdg = self.drone.heading
        gps_prec = max(self.prec, 0.5)

        gps_method = self.method
        if gps_method == NavigationMethod.POSITION:
            gps_method = NavigationMethod.POSITION_GLOBAL

        offsets = [
            (d, 0.0, "Forward"),
            (d, d, "Forward+Left"),
            (0.0, d, "Left"),
            (0.0, 0.0, "Return"),
        ]

        all_reached = True
        for fx, fy, label in offsets:
            lat, lon, _ = GPSCalculate.calculate_gps_offset(
                fx,
                fy,
                0.0,
                gps.latitude,
                gps.longitude,
                gps.altitude,
                hdg,
            )
            log.info(f"  → {label}: lat={lat:.6f}, lon={lon:.6f}")
            reached = self.drone.move_to_gps(
                latitude=lat,
                longitude=lon,
                precision=gps_prec,
                timeout=self.tout,
                method=gps_method,
            )
            if not reached:
                log.warning(f"  ⚠ {label}: timeout")
                all_reached = False
            self.drone.delay(1.5)

        self._log_test_result("GPS Rectangle", all_reached)
        return all_reached

    def _run_waypoints(self, name: str, waypoints: list, reference: MoveReference) -> bool:
        """Navigate ``waypoints`` (tuples of ``(x, y, z, label)`` or
        ``(x, y, z, yaw_deg, label)``) and report per-leg precision."""
        all_reached = True
        for i, wp in enumerate(waypoints, 1):
            if len(wp) == 4:
                x, y, z, label = wp
                yaw = None
            else:
                x, y, z, yaw, label = wp
            log.info(f"  → [{i}/{len(waypoints)}] {label}: x={x}, y={y}, z={z}, yaw={yaw}")
            t0 = time.time()
            reached = self.drone.move_to(
                x=x,
                y=y,
                z=z,
                yaw=yaw,
                reference=reference,
                precision=self.prec,
                timeout=self.tout,
                method=self.method,
            )
            dur = time.time() - t0
            self._record_leg(name, i, label, reference, x, y, z, yaw, reached, dur)
            if not reached:
                log.warning(f"  ⚠ {label}: timeout")
                all_reached = False
            self.drone.delay(1.5)

        self._log_test_result(name, all_reached)
        return all_reached

    def _record_leg(
        self,
        test: str,
        leg: int,
        label: str,
        reference: MoveReference,
        tx: Optional[float],
        ty: Optional[float],
        tz: Optional[float],
        tyaw_deg: Optional[float],
        reached: bool,
        duration_s: float,
    ) -> None:
        """Log per-leg arrival and optionally append to the CSV.

        EKF local pose (always ENU absolute) is logged as-is. Per-axis errors
        against the call-time target are only meaningful for absolute references
        (TAKEOFF/WORLD); for BODY they are offsets at call time. The boolean
        ``reached`` from ``move_to`` is the authoritative pass/fail per leg.
        """
        ax, ay, az, ayaw_deg = self._current_local_pose()
        log.info(
            "    actual local: x=%s, y=%s, z=%s, yaw=%s | reached=%s in %.1fs",
            _fmt(ax),
            _fmt(ay),
            _fmt(az),
            _fmt(ayaw_deg),
            reached,
            duration_s,
        )
        if self._csv_writer is not None:
            self._csv_writer.writerow(
                [
                    f"{time.time():.3f}",
                    test,
                    leg,
                    label,
                    self.args.strategy,
                    reference.name,
                    _csv_num(tx),
                    _csv_num(ty),
                    _csv_num(tz),
                    _csv_num(tyaw_deg),
                    _csv_num(ax),
                    _csv_num(ay),
                    _csv_num(az),
                    _csv_num(ayaw_deg),
                    f"{duration_s:.2f}",
                    int(bool(reached)),
                ]
            )
            self._csv_file.flush()

    def _current_local_pose(self) -> tuple:
        """Return absolute ENU local pose as ``(x, y, z, yaw_deg)``."""
        pose = self.drone.local_pose
        if pose is None:
            return (None, None, None, None)
        p = pose.position
        return (p.x, p.y, p.z, math.degrees(pose.yaw))

    def _log_test_header(self, name: str, detail: str) -> None:
        log.info(f"\n{'─' * 50}")
        log.info(f"  TEST: {name} ({detail})")
        log.info(f"{'─' * 50}")

    def _log_test_result(self, name: str, passed: bool) -> None:
        if passed:
            log.info(f"\033[32;1m  ✓ {name}: PASSED\033[0m")
        else:
            log.warning(
                f"\033[33;1m  ✗ {name}: INCOMPLETE (timeout on one or more waypoints)\033[0m"
            )

    def run(self) -> None:
        """Execute setup, selected tests, and teardown."""
        test_map = {
            "body": self.test_body,
            "takeoff-ref": self.test_takeoff_ref,
            "altitude": self.test_altitude,
            "velocity": self.test_velocity,
            "gps": self.test_gps,
            "figure8": self.test_figure8,
            "rectangle": self.test_rectangle,
            "cube-xyz": self.test_cube_xyz,
            "cube": self.test_cube,
            "gps-rectangle": self.test_gps_rectangle,
        }

        tests_to_run = self.args.test
        if "all" in tests_to_run:
            tests_to_run = list(test_map.keys())

        log.info(
            f"\n{'═' * 50}\n"
            f"  ArduPilot Navigation Test ({self.args.drone})\n"
            f"  Mode: {self.args.mode} | Tests: {', '.join(tests_to_run)}\n"
            f"{'═' * 50}"
        )

        if not self.setup():
            return

        loop_n = self.args.loop
        infinite = loop_n is not None and loop_n <= 0
        iterations = []
        iteration = 0
        try:
            while True:
                iteration += 1
                log.info(f"\n══ Iteration {iteration}{' (∞)' if infinite else f'/{loop_n}'} ══")
                results = {}
                for name in tests_to_run:
                    if name not in test_map:
                        log.warning(f"Unknown test: {name}, skipping")
                        continue
                    results[name] = test_map[name]()
                    self.drone.delay(2.0)
                iterations.append(results)
                self._log_battery()
                if loop_n is None or (not infinite and iteration >= loop_n):
                    break
        except KeyboardInterrupt:
            log.info("Loop interrupted by user")

        log.info(f"\n{'═' * 50}")
        log.info(f"  RESULTS ({iteration} iteration{'s' if iteration != 1 else ''})")
        log.info(f"{'═' * 50}")
        for i, results in enumerate(iterations, 1):
            for name, passed in results.items():
                status = "\033[32;1mPASSED\033[0m" if passed else "\033[33;1mINCOMPLETE\033[0m"
                log.info(f"  [{i}] {name:15s} {status}")

        self.teardown()

    def _log_battery(self) -> None:
        """One-shot snapshot of /mavros/battery (MAVROS only; no-op otherwise)."""
        if self.args.drone != "mavros":
            return
        if self._battery_sub is None:
            try:
                from rclpy.qos import qos_profile_sensor_data
                from sensor_msgs.msg import BatteryState
            except Exception:
                return
            self._battery_msg = None

            def _cb(msg):
                self._battery_msg = msg

            self._battery_sub = self.drone._node.create_subscription(
                BatteryState, "/mavros/battery", _cb, qos_profile_sensor_data
            )
            deadline = time.time() + 2.0
            while self._battery_msg is None and time.time() < deadline:
                time.sleep(0.1)
        msg = self._battery_msg
        if msg is None:
            log.info("  battery: (no /mavros/battery yet)")
            return
        pct = msg.percentage * 100 if msg.percentage and msg.percentage > 0 else None
        log.info(
            "  battery: V=%.2f I=%sA pct=%s",
            msg.voltage,
            f"{msg.current:.2f}" if msg.current is not None else "n/a",
            f"{pct:.0f}%" if pct is not None else "n/a",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ArduPilot Navigation Test (MAVROS/MAVLink)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 navigation.py --mode outdoor\n"
            "  python3 navigation.py --drone mavlink --test body\n"
            "  python3 navigation.py --mode indoor --no-takeoff --test body\n"
            "  python3 navigation.py --strategy pid-ekf --test body\n"
            "  python3 navigation.py --strategy position --test takeoff-ref\n"
            "  python3 navigation.py --mode outdoor --test gps --strategy position-global\n"
            "  python3 navigation.py --no-takeoff --test body --distance 1.0\n"
            "  python3 navigation.py --test figure8 --distance 3.0\n"
            "  python3 navigation.py --test rectangle --strategy pid-ekf --distance 4.0\n"
            "  python3 navigation.py --test cube-xyz --strategy pid-ekf --distance 1.5\n"
            "  python3 navigation.py --test cube --strategy pid-ekf --distance 1.5 --timeout 60\n"
            "  python3 navigation.py --test cube-xyz cube --csv runs/cube.csv\n"
            "  python3 navigation.py --test gps-rectangle --strategy position-global --distance 5.0\n"
            "  python3 navigation.py --test body --loop 5 --csv runs/battery_loop.csv\n"
            "  python3 navigation.py --test cube-xyz --loop --csv runs/endurance.csv  # forever\n"
        ),
    )
    parser.add_argument(
        "--drone",
        choices=["mavros", "mavlink"],
        default="mavros",
        help="ArduPilot transport: mavros (ROS) or mavlink (direct pymavlink). Default: mavros",
    )
    parser.add_argument(
        "--mode",
        choices=["indoor", "outdoor"],
        default="outdoor",
        help="Pose source: indoor (vision) or outdoor (GPS). Default: outdoor",
    )
    parser.add_argument(
        "--connection",
        default=None,
        help="MAVLink endpoint override (mavlink only), e.g. tcp:127.0.0.1:5762 for SITL",
    )
    parser.add_argument(
        "--no-takeoff",
        action="store_true",
        help=(
            "Skip takeoff for hand-held testing. Sets GUIDED mode and "
            "takeoff position without arming. Safe to hold the drone."
        ),
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=2.0,
        help="Takeoff altitude in meters (ignored with --no-takeoff). Default: 2.0",
    )
    parser.add_argument(
        "--test",
        nargs="+",
        default=["all"],
        choices=["all"] + AVAILABLE_TESTS,
        metavar="TEST",
        help=(f"Tests to run. Choices: all, {', '.join(AVAILABLE_TESTS)}. Default: all"),
    )
    parser.add_argument(
        "--distance",
        type=float,
        default=2.0,
        help="Navigation distance per waypoint in meters. Default: 2.0",
    )
    parser.add_argument(
        "--precision",
        type=float,
        default=0.2,
        help="Arrival precision radius in meters. Default: 0.2",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout per waypoint in seconds. Default: 30.0",
    )
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGY_MAP.keys()),
        default="pid",
        help="Navigation method. Default: pid",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Append per-leg results to this CSV file (created if missing).",
    )
    parser.add_argument(
        "--loop",
        type=int,
        nargs="?",
        const=0,
        default=None,
        help=(
            "Repeat the selected tests. ``--loop N`` runs N iterations; "
            "``--loop`` with no value loops forever until Ctrl+C. "
            "Takeoff happens once before the first iteration; landing once at the end."
        ),
    )

    args, _ = parser.parse_known_args()
    return args


def main(args=None):
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    nectar.init()
    parsed = parse_args()
    tester = NavigationTest(parsed)

    try:
        tester.run()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        if not parsed.no_takeoff:
            tester.drone.land()
    finally:
        tester.drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
