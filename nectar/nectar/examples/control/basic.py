#!/usr/bin/env python3
"""
Basic drone flight example -- works with any supported platform.

Supports three modes via --mode:
  velocity : takeoff, velocity box pattern, land (default)
  hover    : takeoff, hover for --hover-time seconds, land
  position : takeoff, position (move_to) box pattern, land

Usage:
    python basic.py --drone mavros
    python basic.py --drone crazyflie --mode hover --height 0.5
    python basic.py --drone crazyflie --mode position --height 0.5 --side 0.6
    python basic.py --drone bebop --mode velocity
    python basic.py --drone crazyflie --cf-name cf231 --backend sim
"""

import argparse

import rclpy
from rclpy.node import Node

from nectar.control import (
    BebopConfig,
    CrazyflieConfig,
    DroneFactory,
    MavrosConfig,
    PoseSource,
)


class BasicExample(Node):
    def __init__(self, args: argparse.Namespace):
        super().__init__("basic_example")
        self._args = args
        self.drone = DroneFactory.create(args.drone, self._build_config(), self)
        self.get_logger().info(f"Initialized {args.drone} drone")

    def _build_config(self):
        a = self._args
        if a.drone == "mavros":
            return MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
        if a.drone == "crazyflie":
            return CrazyflieConfig(
                start_driver=False,
                cf_name=a.cf_name,
                backend=a.backend,
            )
        return BebopConfig(start_driver=False)

    def run(self):
        if not self.drone.connect():
            self.get_logger().error("Connection failed")
            return

        mode = self._args.mode
        if mode == "hover":
            self._run_hover()
        elif mode == "position":
            self._run_position()
        else:
            self._run_velocity()

    def _run_hover(self):
        a = self._args

        if not self.drone.takeoff(altitude=a.height):
            self.get_logger().error("Takeoff failed")
            return

        self.get_logger().info(f"Hovering at {self.drone.height:.2f}m for {a.hover_time:.0f}s")
        self.drone.delay(a.hover_time)

        self.get_logger().info(f"Height after hover: {self.drone.height:.2f}m")
        self.drone.land()
        self.get_logger().info("Hover test complete")

    def _run_velocity(self):
        a = self._args

        if not self.drone.takeoff(altitude=a.height):
            self.get_logger().error("Takeoff failed")
            return

        self.get_logger().info(f"Airborne at {self.drone.height:.2f}m")
        self.drone.delay(2.0)

        v = a.velocity
        t = a.side / v if v > 0 else 2.0

        self.get_logger().info(f"Velocity box: v={v:.2f}m/s side={a.side:.1f}m")

        self.get_logger().info("Forward")
        self.drone.move_velocity(vx=v, duration=t)

        self.get_logger().info("Left")
        self.drone.move_velocity(vy=v, duration=t)

        self.get_logger().info("Backward")
        self.drone.move_velocity(vx=-v, duration=t)

        self.get_logger().info("Right")
        self.drone.move_velocity(vy=-v, duration=t)

        self.drone.land()
        self.get_logger().info("Velocity test complete")

    def _run_position(self):
        a = self._args

        if not self.drone.takeoff(altitude=a.height):
            self.get_logger().error("Takeoff failed")
            return

        self.get_logger().info(f"Airborne at {self.drone.height:.2f}m")
        self.drone.delay(2.0)

        s = a.side
        self.get_logger().info(f"Position box: side={s:.1f}m precision={a.precision:.2f}m")

        for label, x, y in [
            ("Forward", s, 0.0),
            ("Left", 0.0, s),
            ("Backward", -s, 0.0),
            ("Right", 0.0, -s),
        ]:
            self.get_logger().info(label)
            self.drone.move_to(x=x, y=y, z=0.0, precision=a.precision)
            self.drone.delay(1.0)

        self.drone.land()
        self.get_logger().info("Position test complete")


def main():
    parser = argparse.ArgumentParser(description="Basic drone flight example")
    parser.add_argument(
        "--drone",
        choices=["mavros", "bebop", "crazyflie"],
        default="mavros",
        help="Drone type (default: mavros)",
    )
    parser.add_argument(
        "--mode",
        choices=["velocity", "hover", "position"],
        default="velocity",
        help="Flight mode (default: velocity)",
    )
    parser.add_argument("--height", type=float, default=1.5, help="Takeoff height in meters")
    parser.add_argument("--side", type=float, default=1.0, help="Box side length in meters")
    parser.add_argument("--velocity", type=float, default=0.3, help="Velocity in m/s")
    parser.add_argument(
        "--precision", type=float, default=0.10, help="Position precision in meters"
    )
    parser.add_argument("--hover-time", type=float, default=10.0, help="Hover duration in seconds")
    parser.add_argument("--cf-name", default="cf231", help="Crazyflie name (default: cf231)")
    parser.add_argument("--backend", default="cpp", help="Crazyflie backend (default: cpp)")

    args = parser.parse_args()

    rclpy.init()
    node = BasicExample(args)

    try:
        node.run()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted -- landing")
        node.drone.land()
    finally:
        node.drone.cleanup()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
