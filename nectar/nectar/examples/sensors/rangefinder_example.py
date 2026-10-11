#!/usr/bin/env python3
"""Standalone Benewake TF-series rangefinder bench test (no ROS).

Wires :class:`BenewakeTF`, :class:`MavlinkConnection`, and
:class:`RangefinderPublisher` (with optional :class:`ObstacleMaskFilter`)
into a single process. Useful for verifying the sensor + transport before
running the full ROS2 node, or for non-ROS deployments.

Usage::

    python rangefinder_example.py --port /dev/ttyUSB0 \\
        --mavlink udp:127.0.0.1:14551 \\
        --filter obstacle_mask
"""

import argparse
import time

from nectar.control import MavlinkConnection
from nectar.sensors import MODELS, BenewakeTF, ObstacleMaskFilter, RangefinderPublisher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Benewake TF serial port")
    parser.add_argument(
        "--model",
        default="tfluna",
        choices=list(MODELS),
        help="TF-series model (default: tfluna)",
    )
    parser.add_argument("--baud", type=int, default=115200, help="UART baud")
    parser.add_argument(
        "--mavlink",
        default="udp:127.0.0.1:14551",
        help="MAVLink connection string (UDP/TCP/serial)",
    )
    parser.add_argument(
        "--mavlink-baud",
        type=int,
        default=921600,
        help="Serial baud for MAVLink endpoints (ignored for UDP/TCP)",
    )
    parser.add_argument(
        "--filter",
        choices=["none", "obstacle_mask"],
        default="none",
        help="Filter to apply before publishing (default: none)",
    )
    parser.add_argument(
        "--obstacle-height",
        type=float,
        default=0.0,
        help="Obstacle height in meters. <= 0 enables auto-estimation.",
    )
    parser.add_argument("--max-change", type=float, default=0.30)
    parser.add_argument("--avg-window", type=int, default=10)
    parser.add_argument("--estimate-lock-s", type=float, default=0.2)
    parser.add_argument("--timeout-s", type=float, default=5.0)
    parser.add_argument("--rate", type=float, default=50.0, help="Publish rate (Hz)")
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Run for this many seconds. 0 = run until Ctrl-C.",
    )
    return parser.parse_args()


def build_filter(args: argparse.Namespace):
    if args.filter == "none":
        return None
    timeout = args.timeout_s if args.timeout_s > 0 else None
    height = args.obstacle_height if args.obstacle_height > 0 else None
    return ObstacleMaskFilter(
        obstacle_height_m=height,
        max_change_m=args.max_change,
        avg_window=args.avg_window,
        estimate_lock_s=args.estimate_lock_s,
        timeout_s=timeout,
    )


def main() -> None:
    args = parse_args()

    sensor = BenewakeTF(port=args.port, model=args.model, baudrate=args.baud)
    connection = MavlinkConnection()
    print(f"Connecting to {args.mavlink} ...")
    connection.connect(args.mavlink, baud=args.mavlink_baud)
    print(
        f"FCU heartbeat received "
        f"(sys={connection.master.target_system}, "
        f"comp={connection.master.target_component})"
    )

    publisher = RangefinderPublisher(
        sensor=sensor,
        connection=connection,
        min_distance_m=sensor.min_range_m,
        max_distance_m=sensor.max_range_m,
        rate_hz=args.rate,
        filter=build_filter(args),
    )
    publisher.start()
    print(f"Publishing {args.model} at {args.rate} Hz. Filter: {args.filter}.")

    try:
        deadline = time.monotonic() + args.duration if args.duration > 0 else None
        while True:
            time.sleep(0.5)
            if deadline is not None and time.monotonic() >= deadline:
                break
    except KeyboardInterrupt:
        pass
    finally:
        publisher.stop()
        sensor.close()
        connection.close()
        print("Stopped.")


if __name__ == "__main__":
    main()
