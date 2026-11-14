#!/usr/bin/env python3
"""Move a PWM servo through a sequence of angles or set a pulse directly."""

import argparse
import time

from nectar.actuators import ServoConfig, ServoMotor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", type=int, default=32, help="PWM output pin")
    parser.add_argument("--mode", choices=("BOARD", "BCM"), default="BOARD")
    parser.add_argument(
        "--angles",
        type=float,
        nargs="+",
        default=(0.0, 90.0, 180.0, 90.0),
        help="angles to command in order",
    )
    parser.add_argument(
        "--pulse-us",
        type=float,
        help="send one pulse width directly instead of an angle sequence",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=1.0,
        help="seconds to wait after each angle command",
    )
    parser.add_argument("--min-pulse-us", type=float, default=500.0)
    parser.add_argument("--max-pulse-us", type=float, default=2500.0)
    parser.add_argument(
        "--clamp",
        action="store_true",
        help="clamp angles to the configured range instead of rejecting them",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.settle < 0:
        raise ValueError("--settle must be non-negative")
    config = ServoConfig(
        pin=args.pin,
        gpio_mode=args.mode,
        min_pulse_us=args.min_pulse_us,
        max_pulse_us=args.max_pulse_us,
    )

    with ServoMotor(config) as servo:
        if args.pulse_us is not None:
            servo.set_pulse_width_us(args.pulse_us)
            print(f"Commanded {args.pulse_us:g} microseconds.")
            return

        for angle in args.angles:
            commanded = servo.set_angle(angle, clamp=args.clamp)
            print(f"Commanded {commanded:g} degrees.")
            time.sleep(args.settle)


if __name__ == "__main__":
    main()
