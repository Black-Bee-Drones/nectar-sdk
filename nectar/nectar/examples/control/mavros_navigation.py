#!/usr/bin/env python3
import argparse

import rclpy
from rclpy.node import Node

from nectar.control import (
    DroneFactory,
    MavrosConfig,
    MoveReference,
    NavigationMethod,
    PoseSource,
)
from nectar.utils.gps_calculate import GPSCalculate

AVAILABLE_TESTS = ["body", "takeoff-ref", "altitude", "velocity", "gps"]

STRATEGY_MAP = {
    "pid": NavigationMethod.PID,
    "pid-ekf": NavigationMethod.PID_EKF,
    "position": NavigationMethod.POSITION,
    "position-global": NavigationMethod.POSITION_GLOBAL,
}


class NavigationTest(Node):
    """
    MAVROS navigation test node.
    """

    def __init__(self, args: argparse.Namespace):
        super().__init__("mavros_nav_test")
        self.args = args

        pose_source = PoseSource.VISION if args.mode == "indoor" else PoseSource.GPS
        config = MavrosConfig(pose_source=pose_source, start_driver=False)

        self.drone = DroneFactory.create("mavros", config, self)

        self.dist = args.distance
        self.prec = args.precision
        self.tout = args.timeout
        self.method = STRATEGY_MAP.get(args.strategy, NavigationMethod.PID)

        self.get_logger().info(
            f"Initialized | mode={args.mode} | method={args.strategy} | "
            f"no_takeoff={args.no_takeoff} | "
            f"distance={self.dist}m | precision={self.prec}m | timeout={self.tout}s"
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
                self.get_logger().error("Failed to set GUIDED mode")
                return False

            self.drone.delay(1.0)
            self.drone.set_takeoff_position()
            self.get_logger().info("Takeoff position set to current position")
            self.get_logger().info(
                "╔══════════════════════════════════════════════════╗\n"
                "║  NO-TAKEOFF MODE (hand-held testing)            ║\n"
                "║  Drone will NOT arm. Pick it up by hand and     ║\n"
                "║  move it to verify navigation logic via logs.   ║\n"
                "╚══════════════════════════════════════════════════╝"
            )
            return True

        if not self.drone.takeoff(altitude=self.args.altitude):
            self.get_logger().error("Takeoff failed")
            return False

        self.drone.delay(3.0)
        return True

    def teardown(self) -> None:
        """Land (normal) or just log"""
        if self.args.no_takeoff:
            self.get_logger().info("No-takeoff mode: nothing to teardown")
        else:
            self.get_logger().info("Landing...")
            self.drone.land()

    def test_body(self) -> bool:
        """
        BODY reference square pattern.
        """
        d = self.dist
        self._log_test_header("BODY Square", f"{d}m sides")

        waypoints = [
            (d, 0.0, None, "Forward"),
            (0.0, d, None, "Left"),
            (-d, 0.0, None, "Backward"),
            (0.0, -d, None, "Right (return)"),
        ]

        all_reached = True
        for x, y, z, label in waypoints:
            self.get_logger().info(f"  → {label}: x={x}, y={y}")
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
                self.get_logger().warn(f"  ⚠ {label}: timeout")
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
            (d, d, None, f"{d}m forward + {d}m left from takeoff"),
            (0.0, d, None, f"{d}m left from takeoff"),
            (0.0, 0.0, None, "Return to takeoff XY"),
        ]

        all_reached = True
        for x, y, z, label in waypoints:
            self.get_logger().info(f"  → {label}: x={x}, y={y}")
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
                self.get_logger().warn(f"  ⚠ {label}: timeout")
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

        self.get_logger().info(f"  → Up {dz}m")
        r1 = self.drone.move_to(
            z=dz,
            precision=self.prec,
            timeout=self.tout,
            method=self.method,
        )
        self.drone.delay(1.5)

        self.get_logger().info(f"  → Down {dz}m")
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
            self.get_logger().info(f"  → {label}: vx={vx}, vy={vy}")
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
            self.get_logger().warn("GPS test skipped: not available in indoor mode")
            return False

        self._log_test_header("GPS Navigation", f"{self.dist}m forward")

        gps = self.drone.gps
        hdg = self.drone.heading

        self.get_logger().info(
            f"  Current: lat={gps.latitude:.6f}, lon={gps.longitude:.6f}, hdg={hdg:.1f}°"
        )

        lat, lon, _ = GPSCalculate.calculate_gps_offset(
            self.dist,
            0.0,
            0.0,
            gps.latitude,
            gps.longitude,
            gps.altitude,
            hdg,
        )

        self.get_logger().info(f"  → Target: lat={lat:.6f}, lon={lon:.6f}")
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
            self.get_logger().warn("  ⚠ GPS waypoint: timeout")

        self._log_test_result("GPS Navigation", reached)
        return reached

    def _log_test_header(self, name: str, detail: str) -> None:
        self.get_logger().info(f"\n{'─' * 50}")
        self.get_logger().info(f"  TEST: {name} ({detail})")
        self.get_logger().info(f"{'─' * 50}")

    def _log_test_result(self, name: str, passed: bool) -> None:
        if passed:
            self.get_logger().info(f"\033[32;1m  ✓ {name}: PASSED\033[0m")
        else:
            self.get_logger().warn(
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
        }

        tests_to_run = self.args.test
        if "all" in tests_to_run:
            tests_to_run = list(test_map.keys())

        self.get_logger().info(
            f"\n{'═' * 50}\n"
            f"  MAVROS Navigation Test\n"
            f"  Mode: {self.args.mode} | Tests: {', '.join(tests_to_run)}\n"
            f"{'═' * 50}"
        )

        if not self.setup():
            return

        results = {}
        for name in tests_to_run:
            if name not in test_map:
                self.get_logger().warn(f"Unknown test: {name}, skipping")
                continue

            results[name] = test_map[name]()
            self.drone.delay(2.0)

        self.get_logger().info(f"\n{'═' * 50}")
        self.get_logger().info("  RESULTS")
        self.get_logger().info(f"{'═' * 50}")
        for name, passed in results.items():
            status = "\033[32;1mPASSED\033[0m" if passed else "\033[33;1mINCOMPLETE\033[0m"
            self.get_logger().info(f"  {name:15s} {status}")

        self.teardown()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MAVROS Navigation Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 mavros_navigation.py --mode outdoor\n"
            "  python3 mavros_navigation.py --mode indoor --no-takeoff --test body\n"
            "  python3 mavros_navigation.py --strategy pid-ekf --test body\n"
            "  python3 mavros_navigation.py --strategy position --test takeoff-ref\n"
            "  python3 mavros_navigation.py --mode outdoor --test gps --strategy position-global\n"
            "  python3 mavros_navigation.py --no-takeoff --test body --distance 1.0\n"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["indoor", "outdoor"],
        default="outdoor",
        help="Pose source: indoor (vision) or outdoor (GPS). Default: outdoor",
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

    args, _ = parser.parse_known_args()
    return args


def main(args=None):
    rclpy.init(args=args)
    parsed = parse_args()
    node = NavigationTest(parsed)

    try:
        node.run()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted by user")
        if not parsed.no_takeoff:
            node.drone.land()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
