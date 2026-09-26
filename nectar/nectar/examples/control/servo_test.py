#!/usr/bin/env python3
"""
Pre-flight ArduPilot servo / PWM tester (MAV_CMD_DO_SET_SERVO).

Never arms. Keep props off.

Usage:
    python3 servo_test.py
    python3 servo_test.py --drone mavlink --connection /dev/ttyAMA1
    python3 servo_test.py --drone mavlink --connection tcp:127.0.0.1:5762 --channel 3
"""

import argparse
import shlex
import time

import nectar
from nectar.control import (
    Capability,
    DroneFactory,
    MavlinkConfig,
    MavrosConfig,
    PoseSource,
)

HELP_TEXT = """
Commands:
  <pwm>                       Send PWM to current channel (e.g. 1500)
  pwm <pwm>                   Same as above
  ch <n>                      Switch AUX OUT channel (1-8; FCU ch = n+8)
  hold | close                Send 'hold' preset PWM
  release | open              Send 'release' preset PWM
  mid | center                Send 1500
  sweep <a> <b> [step] [delay]
                              Step from a to b in 'step' us (default 50)
                              sleeping 'delay' s between writes (default 0.2)
                              Ctrl+C aborts the sweep without exiting.
  cycle [n] [delay]           Toggle hold<->release n times (default 5, 1.0s)
  set hold <pwm>              Update 'hold' preset
  set release <pwm>           Update 'release' preset
  status                      Channel, last PWM, presets, FCU state
  help                        This help
  quit | exit                 Exit (FCU keeps last commanded PWM)

Tips:
  * If a write returns OK but the servo does not move, check the safety
    switch and that SERVOx_FUNCTION = 0 in ArduPilot.
  * Typical hobby servo range: 1000-2000 us. Always probe slowly.
  * The script does NOT arm the drone. Keep props off when bench-testing.
"""


def build_config(args: argparse.Namespace):
    kwargs = dict(
        pose_source=PoseSource.GPS,
        start_driver=False,
        expect_lidar=False,
        sensor_timeout=args.sensor_timeout,
    )
    if args.connection:
        kwargs["connection_string"] = args.connection
    if args.drone == "mavlink":
        return MavlinkConfig(**kwargs)
    return MavrosConfig(**kwargs)


class ServoTester:
    def __init__(self, args: argparse.Namespace) -> None:
        self.drone = DroneFactory.create(args.drone, build_config(args))
        self.channel: int = args.channel
        self.hold_pwm: int = args.hold
        self.release_pwm: int = args.release
        self.last_pwm: int = -1

    def send(self, pwm: int) -> bool:
        ok = self.drone.do_servo(self.channel, int(pwm))
        if ok:
            self.last_pwm = int(pwm)
        return ok

    def handle_command(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return True

        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return True

        cmd = parts[0].lower()

        if cmd in ("quit", "exit"):
            return False
        if cmd == "help":
            print(HELP_TEXT)
            return True
        if cmd == "status":
            self._print_status()
            return True
        if cmd == "ch":
            self._handle_channel(parts[1:])
            return True
        if cmd in ("hold", "close"):
            self._send_named("hold", self.hold_pwm)
            return True
        if cmd in ("release", "open"):
            self._send_named("release", self.release_pwm)
            return True
        if cmd in ("mid", "center"):
            self._send_named("mid", 1500)
            return True
        if cmd == "pwm":
            self._handle_pwm(parts[1:])
            return True
        if cmd == "sweep":
            self._handle_sweep(parts[1:])
            return True
        if cmd == "cycle":
            self._handle_cycle(parts[1:])
            return True
        if cmd == "set":
            self._handle_set(parts[1:])
            return True

        self._handle_pwm(parts)
        return True

    def _handle_channel(self, parts: list) -> None:
        if not parts:
            print("Usage: ch <n>")
            return
        try:
            n = int(parts[0])
        except ValueError:
            print(f"Invalid channel: {parts[0]}")
            return
        if n < 1 or n > 8:
            print(f"Channel out of range: {n} (expected 1-8)")
            return
        self.channel = n
        print(f"Channel: {self.channel}  (FCU ch {self.channel + 8})")

    def _handle_pwm(self, parts: list) -> None:
        if not parts:
            print("Usage: pwm <value>")
            return
        try:
            pwm = int(float(parts[0]))
        except ValueError:
            print(f"Invalid PWM: {parts[0]}")
            return
        if pwm < 800 or pwm > 2200:
            print(f"PWM out of safe range: {pwm} (expected 800-2200)")
            return
        ok = self.send(pwm)
        print(f"do_servo(ch={self.channel}, pwm={pwm}) -> {'OK' if ok else 'FAILED'}")

    def _send_named(self, name: str, pwm: int) -> None:
        ok = self.send(pwm)
        print(f"{name}: do_servo(ch={self.channel}, pwm={pwm}) -> {'OK' if ok else 'FAILED'}")

    def _handle_sweep(self, parts: list) -> None:
        if len(parts) < 2:
            print("Usage: sweep <start> <end> [step] [delay]")
            return
        try:
            start = int(parts[0])
            end = int(parts[1])
            step = int(parts[2]) if len(parts) > 2 else 50
            delay = float(parts[3]) if len(parts) > 3 else 0.2
        except ValueError as e:
            print(f"Bad sweep args: {e}")
            return
        if step == 0:
            print("step must be non-zero")
            return

        step = abs(step) * (1 if end >= start else -1)
        print(f"Sweep {start}->{end} step={step} delay={delay}s on ch {self.channel}")
        try:
            cur = start
            while (step > 0 and cur <= end) or (step < 0 and cur >= end):
                self.send(cur)
                print(f"  pwm={cur}")
                time.sleep(delay)
                cur += step
        except KeyboardInterrupt:
            print("\nSweep aborted")
            return
        print("Sweep done")

    def _handle_cycle(self, parts: list) -> None:
        try:
            n = int(parts[0]) if parts else 5
            delay = float(parts[1]) if len(parts) > 1 else 1.0
        except ValueError as e:
            print(f"Bad cycle args: {e}")
            return
        print(
            f"Cycle hold({self.hold_pwm}) <-> release({self.release_pwm}) "
            f"x{n} delay={delay}s on ch {self.channel}"
        )
        try:
            for i in range(n):
                self.send(self.hold_pwm)
                print(f"  [{i + 1}/{n}] hold={self.hold_pwm}")
                time.sleep(delay)
                self.send(self.release_pwm)
                print(f"  [{i + 1}/{n}] release={self.release_pwm}")
                time.sleep(delay)
        except KeyboardInterrupt:
            print("\nCycle aborted")
            return
        print("Cycle done")

    def _handle_set(self, parts: list) -> None:
        if not parts or len(parts) < 2:
            print("Usage: set hold|release <pwm>")
            return
        key, val = parts[0].lower(), parts[1]
        try:
            pwm = int(float(val))
        except ValueError:
            print(f"Invalid PWM: {val}")
            return
        if key == "hold":
            self.hold_pwm = pwm
        elif key == "release":
            self.release_pwm = pwm
        else:
            print(f"Unknown preset '{key}'. Options: hold, release")
            return
        print(f"{key} preset -> {pwm}")

    def _print_status(self) -> None:
        last = self.last_pwm if self.last_pwm >= 0 else "-"
        print(f"\n{'-' * 40}")
        print(f"  Backend        : {self.drone.config.name}")
        print(f"  Channel        : {self.channel}  (FCU ch {self.channel + 8})")
        print(f"  Last PWM       : {last}")
        print(f"  hold preset    : {self.hold_pwm}")
        print(f"  release preset : {self.release_pwm}")
        print(f"  FCU connected  : {self.drone.is_fcu_connected}")
        print(f"  Armed          : {self.drone.is_armed}")
        print(f"  Mode           : {self.drone.flight_mode}")
        print(f"{'-' * 40}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-flight ArduPilot servo tester (MAV_CMD_DO_SET_SERVO).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "REPL examples:\n"
            "  1500            -> send PWM 1500 to current channel\n"
            "  ch 3            -> switch to AUX OUT 3 (FCU ch 11)\n"
            "  hold | release  -> send the configured presets\n"
            "  sweep 1000 2000 100 0.3\n"
            "  cycle 3 0.8\n"
            "  help            -> full command list\n"
        ),
    )
    parser.add_argument(
        "--drone",
        choices=["mavros", "mavlink"],
        default="mavros",
        help="ArduPilot transport (default: mavros)",
    )
    parser.add_argument(
        "--connection",
        default=None,
        help="Override connection string. mavlink: /dev/ttyUSB0, /dev/ttyAMA1, "
        "tcp:127.0.0.1:5762. mavros: MAVROS fcu_url (serial:///dev/ttyUSB0:921600).",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=3,
        help="initial AUX OUT number (default: 3 -> FCU ch 11)",
    )
    parser.add_argument(
        "--hold",
        type=int,
        default=1000,
        help="'hold' preset PWM in us (default: 1000)",
    )
    parser.add_argument(
        "--release",
        type=int,
        default=2000,
        help="'release' preset PWM in us (default: 2000)",
    )
    parser.add_argument(
        "--sensor-timeout",
        type=float,
        default=2.0,
        help="sensor wait timeout in seconds (default: 2.0)",
    )
    args, _ = parser.parse_known_args()
    return args


def main(args=None) -> None:
    parsed = parse_args()
    nectar.init()
    tester = None
    try:
        tester = ServoTester(parsed)
        if not tester.drone.supports(Capability.SERVO):
            print("This drone has no Capability.SERVO (ArduPilot mavros/mavlink only)")
            return
        print(HELP_TEXT)
        print(
            f"Ready. {parsed.drone} ch={tester.channel} (FCU ch {tester.channel + 8}), "
            f"hold={tester.hold_pwm}, release={tester.release_pwm}"
        )
        print("Type a PWM value or 'help'.\n")
        while True:
            try:
                line = input("servo> ")
            except EOFError:
                break
            if not tester.handle_command(line):
                break
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        if tester is not None:
            tester.drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
