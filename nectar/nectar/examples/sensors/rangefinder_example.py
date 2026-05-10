#!/usr/bin/env python3
"""Standalone TF-Luna rangefinder bench test (no ROS).

Wires :class:`TFLuna`, :class:`MavlinkConnection`, and
:class:`RangefinderPublisher` (with optional :class:`ObstacleMaskFilter`)
into a single process. Useful for verifying the sensor + transport before
running the full ROS2 node, or for non-ROS deployments.

Usage::

    python rangefinder_example.py --port /dev/ttyUSB0 \\
        --mavlink udp:127.0.0.1:14551 \\
        --filter obstacle_mask --obstacle-height 1.7
"""

import argparse
import time

from nectar.control import MavlinkConnection
from nectar.sensors import ObstacleMaskFilter, RangefinderPublisher, TFLuna


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ttyUSB0", help="TF-Luna serial port")
    parser.add_argument("--baud", type=int, default=115200, help="TF-Luna baud")
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
        "--obstacle-height", type=float, default=1.7, help="Obstacle height in meters"
    )
    parser.add_argument("--max-change", type=float, default=0.30)
    parser.add_argument("--avg-window", type=int, default=10)
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
    return ObstacleMaskFilter(
        obstacle_height_m=args.obstacle_height,
        max_change_m=args.max_change,
        avg_window=args.avg_window,
        timeout_s=timeout,
    )


def main() -> None:
    args = parse_args()

    sensor = TFLuna(port=args.port, baudrate=args.baud)
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
        rate_hz=args.rate,
        filter=build_filter(args),
    )
    publisher.start()
    print(f"Publishing at {args.rate} Hz. Filter: {args.filter}.")

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
