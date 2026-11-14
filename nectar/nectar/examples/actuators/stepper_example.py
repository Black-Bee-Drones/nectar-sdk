#!/usr/bin/env python3
"""Move a stepper motor by angle or for a finite time."""

import argparse

from nectar.actuators import StepperConfig, StepperMotor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    motion = parser.add_mutually_exclusive_group()
    motion.add_argument(
        "--degrees",
        type=float,
        default=90.0,
        help="relative angle in degrees (or absolute from home when --home-pin is set)",
    )
    motion.add_argument(
        "--duration",
        type=float,
        help="rotate at --rpm for this many seconds instead of moving by angle",
    )
    parser.add_argument("--rpm", type=float, default=1.0, help="output-shaft RPM")
    parser.add_argument(
        "--pins",
        type=int,
        nargs=4,
        default=(11, 13, 15, 16),
        metavar=("PIN1", "PIN2", "PIN3", "PIN4"),
        help="coil pins in the selected numbering mode",
    )
    parser.add_argument("--mode", choices=("BOARD", "BCM"), default="BOARD")
    parser.add_argument("--steps-per-revolution", type=int, default=4096)
    parser.add_argument(
        "--home-pin",
        type=int,
        help="optional limit-switch pin; homes before an absolute degree move",
    )
    parser.add_argument("--home-direction", type=int, choices=(-1, 1), default=-1)
    parser.add_argument("--home-rpm", type=float, default=2.0)
    parser.add_argument("--backoff-degrees", type=float, default=5.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = StepperConfig(
        pins=tuple(args.pins),
        steps_per_revolution=args.steps_per_revolution,
        gpio_mode=args.mode,
        home_pin=args.home_pin,
        home_direction=args.home_direction,
    )

    with StepperMotor(config) as motor:
        if args.home_pin is not None:
            print("Homing stepper; keep the mechanism clear and observe the limit switch.")
            motor.home(args.home_rpm, args.backoff_degrees)
            print("Home position established.")

        if args.duration is not None:
            steps = motor.rotate_by_velocity(args.rpm, args.duration)
            print(f"Issued {steps} half-steps over {args.duration:g} seconds.")
        elif args.home_pin is not None:
            steps = motor.rotate_to_degrees(args.degrees, args.rpm)
            print(f"Moved to {args.degrees:g} degrees in {steps} half-steps.")
        else:
            steps = motor.rotate_by_degrees(args.degrees, args.rpm)
            print(f"Moved {args.degrees:g} degrees in {steps} half-steps.")


if __name__ == "__main__":
    main()
