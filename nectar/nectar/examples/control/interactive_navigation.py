#!/usr/bin/env python3
"""
Interactive ArduPilot (MAVROS/MAVLink) navigation REPL.

Type waypoints in the terminal and the drone executes them immediately.
Supports move_to (local) and move_to_gps commands with configurable
method, precision, and reference frame — changeable at runtime.

Usage:
    python3 interactive_navigation.py --mode outdoor
    python3 interactive_navigation.py --drone mavlink --mode outdoor
    python3 interactive_navigation.py --mode outdoor --strategy pid-ekf --altitude 3.0
    python3 interactive_navigation.py --mode indoor --no-takeoff
"""

import argparse
import logging
import shlex

import nectar
from nectar.control import (
    DroneFactory,
    MavlinkConfig,
    MavrosConfig,
    MoveReference,
    NavigationMethod,
    PoseSource,
)

log = logging.getLogger("interactive_navigation")

STRATEGY_MAP = {
    "pid": NavigationMethod.PID,
    "pid-ekf": NavigationMethod.PID_EKF,
    "position": NavigationMethod.POSITION,
    "position-global": NavigationMethod.POSITION_GLOBAL,
}

REF_MAP = {
    "body": MoveReference.BODY,
    "takeoff": MoveReference.TAKEOFF,
}

HELP_TEXT = """
Commands:
  x y [z]             Move to relative position (current reference frame)
  gps lat lon [alt]   Move to GPS coordinate
  set ref body|takeoff       Change reference frame
  set method pid|pid-ekf|position|position-global
  set precision <meters>
  set timeout <seconds>
  status              Show drone state and current settings
  land                Land the drone
  rtl                 Return to launch
  help                Show this help
  quit / exit         Land and exit

Examples:
  2 0                 2m forward
  2 1 0               2m forward, 1m left, hold altitude
  0 0                 Return to origin (TAKEOFF ref) or hold (BODY ref)
  gps -22.413 -45.449 15
  set method pid-ekf
  set ref takeoff
  set precision 0.3
"""


class InteractiveNav:
    def __init__(self, args: argparse.Namespace):
        pose_source = PoseSource.VISION if args.mode == "indoor" else PoseSource.GPS
        if args.drone == "mavlink":
            config = MavlinkConfig(pose_source=pose_source, start_driver=False)
        else:
            config = MavrosConfig(pose_source=pose_source, start_driver=False)
        self.drone = DroneFactory.create(args.drone, config)
        self.method = STRATEGY_MAP.get(args.strategy, NavigationMethod.PID)
        self.reference = MoveReference.BODY
        self.precision = args.precision
        self.timeout = args.timeout
        self.is_outdoor = args.mode == "outdoor"
        self._no_takeoff = args.no_takeoff

    def setup(self, altitude: float) -> bool:
        if self._no_takeoff:
            if not self.drone.set_mode("GUIDED"):
                log.error("Failed to set GUIDED mode")
                return False
            self.drone.delay(1.0)
            self.drone.set_takeoff_position()
            log.info("No-takeoff mode: takeoff position set to current")
            return True
        if not self.drone.takeoff(altitude=altitude):
            log.error("Takeoff failed")
            return False
        self.drone.delay(3.0)
        return True

    def handle_input(self, line: str) -> bool:
        """Parse and execute one command. Returns False to quit."""
        line = line.strip()
        if not line:
            return True

        parts = shlex.split(line)
        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            return False

        if cmd == "help":
            print(HELP_TEXT)
            return True

        if cmd == "land":
            log.info("Landing...")
            self.drone.land()
            return True

        if cmd == "rtl":
            log.info("RTL...")
            self.drone.rtl()
            return True

        if cmd == "status":
            self._print_status()
            return True

        if cmd == "set":
            self._handle_set(parts[1:])
            return True

        if cmd == "gps":
            self._handle_gps(parts[1:])
            return True

        self._handle_move(parts)
        return True

    def _handle_move(self, parts: list) -> None:
        try:
            vals = [float(v) for v in parts]
        except ValueError:
            print(f"Invalid input. Expected: x y [z]  (got: {' '.join(parts)})")
            return

        if len(vals) < 2:
            print("Need at least x y. Example: 2 0")
            return

        x, y = vals[0], vals[1]
        z = vals[2] if len(vals) >= 3 else None

        log.info(
            "move_to x=%s y=%s z=%s ref=%s method=%s prec=%sm",
            x,
            y,
            z,
            self.reference.name,
            self.method.name,
            self.precision,
        )
        reached = self.drone.move_to(
            x=x,
            y=y,
            z=z,
            reference=self.reference,
            precision=self.precision,
            timeout=self.timeout,
            method=self.method,
        )
        if reached:
            log.info("Target reached")
        else:
            log.warning("Timeout - target not reached within precision")

    def _handle_gps(self, parts: list) -> None:
        if not self.is_outdoor:
            print("GPS navigation not available in indoor mode")
            return

        try:
            vals = [float(v) for v in parts]
        except ValueError:
            print(f"Invalid GPS input. Expected: lat lon [alt]  (got: {' '.join(parts)})")
            return

        if len(vals) < 2:
            print("Need at least lat lon. Example: gps -22.413 -45.449 15")
            return

        lat, lon = vals[0], vals[1]
        alt = vals[2] if len(vals) >= 3 else None

        gps_method = self.method
        if gps_method == NavigationMethod.POSITION:
            gps_method = NavigationMethod.POSITION_GLOBAL
            log.info("POSITION not supported for GPS, using POSITION_GLOBAL")

        gps_prec = max(self.precision, 0.5)
        log.info(
            "move_to_gps lat=%.6f lon=%.6f alt=%s method=%s prec=%sm",
            lat,
            lon,
            alt,
            gps_method.name,
            gps_prec,
        )
        reached = self.drone.move_to_gps(
            latitude=lat,
            longitude=lon,
            altitude=alt,
            precision=gps_prec,
            timeout=self.timeout,
            method=gps_method,
        )
        if reached:
            log.info("GPS target reached")
        else:
            log.warning("Timeout - GPS target not reached")

    def _handle_set(self, parts: list) -> None:
        if len(parts) < 2:
            print("Usage: set ref|method|precision|timeout <value>")
            return

        key, val = parts[0].lower(), parts[1].lower()

        if key == "ref":
            if val in REF_MAP:
                self.reference = REF_MAP[val]
                print(f"Reference: {self.reference.name}")
            else:
                print(f"Unknown ref '{val}'. Options: {', '.join(REF_MAP)}")

        elif key == "method":
            if val in STRATEGY_MAP:
                self.method = STRATEGY_MAP[val]
                print(f"Method: {self.method.name}")
            else:
                print(f"Unknown method '{val}'. Options: {', '.join(STRATEGY_MAP)}")

        elif key == "precision":
            try:
                self.precision = float(val)
                print(f"Precision: {self.precision}m")
            except ValueError:
                print(f"Invalid precision: {val}")

        elif key == "timeout":
            try:
                self.timeout = float(val)
                print(f"Timeout: {self.timeout}s")
            except ValueError:
                print(f"Invalid timeout: {val}")

        else:
            print(f"Unknown setting '{key}'. Options: ref, method, precision, timeout")

    def _print_status(self) -> None:
        print(f"\n{'─' * 40}")
        print(f"  Reference : {self.reference.name}")
        print(f"  Method    : {self.method.name}")
        print(f"  Precision : {self.precision}m")
        print(f"  Timeout   : {self.timeout}s")
        print(f"  Armed     : {self.drone.is_armed}")
        print(f"  Mode      : {self.drone.flight_mode}")
        if self.is_outdoor:
            gps = self.drone.gps
            if gps:
                print(f"  GPS       : {gps.latitude:.6f}, {gps.longitude:.6f}")
            print(f"  Heading   : {self.drone.heading:.1f}°")
            print(f"  Rel alt   : {self.drone.rel_alt:.2f}m")
        alt = self.drone.get_altitude()
        if alt is not None:
            print(f"  Altitude  : {alt:.2f}m")
        print(f"{'─' * 40}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive ArduPilot navigation REPL (MAVROS/MAVLink)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Once running, type waypoints directly:\n"
            "  2 0          → 2m forward\n"
            "  0 3 0        → 3m left\n"
            "  gps -22.4 -45.4 15\n"
            "  set method pid-ekf\n"
            "  help         → full command list\n"
        ),
    )
    parser.add_argument("--drone", choices=["mavros", "mavlink"], default="mavros")
    parser.add_argument("--mode", choices=["indoor", "outdoor"], default="outdoor")
    parser.add_argument("--no-takeoff", action="store_true", help="Hand-held testing")
    parser.add_argument(
        "--altitude", type=float, default=2.0, help="Takeoff altitude. Default: 2.0"
    )
    parser.add_argument("--strategy", choices=list(STRATEGY_MAP.keys()), default="pid")
    parser.add_argument("--precision", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=30.0)
    args, _ = parser.parse_known_args()
    return args


def main(args=None):
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    nectar.init()
    parsed = parse_args()
    nav = InteractiveNav(parsed)

    if not nav.setup(parsed.altitude):
        nav.drone.cleanup()
        nectar.shutdown()
        return

    print(HELP_TEXT)
    print("Ready. Type waypoints (x y [z]) or 'help'.\n")

    try:
        while True:
            try:
                line = input("nav> ")
            except EOFError:
                break
            if not nav.handle_input(line):
                break
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        if not parsed.no_takeoff:
            log.info("Landing...")
            nav.drone.land()
        nav.drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
