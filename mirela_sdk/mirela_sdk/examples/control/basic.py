#!/usr/bin/env python3
import argparse

import rclpy
from rclpy.node import Node

from mirela_sdk.control import BebopConfig, DroneFactory, MavrosConfig, PoseSource


class BasicExample(Node):
    def __init__(self, drone_type: str):
        super().__init__("basic_example")

        if drone_type == "mavros":
            config = MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
        else:
            config = BebopConfig(start_driver=False)

        self.drone = DroneFactory.create(drone_type, config, self)
        self.get_logger().info(f"Initialized {drone_type} drone")

    def run(self):
        """Execute basic flight: takeoff, move, land."""
        if not self.drone.takeoff(altitude=2.0):
            self.get_logger().error("Takeoff failed")
            return

        self.get_logger().info(f"Airborne at {self.drone.height:.2f}m")
        self.drone.delay(3.0)

        self.get_logger().info("Forward")
        self.drone.move_velocity(vx=0.5, duration=3.0)

        self.get_logger().info("Left")
        self.drone.move_velocity(vy=0.5, duration=2.0)

        self.get_logger().info("Right")
        self.drone.move_velocity(vy=-0.5, duration=2.0)

        self.get_logger().info("Backward")
        self.drone.move_velocity(vx=-0.5, duration=3.0)

        self.drone.land()
        self.get_logger().info("Complete")


def main():
    parser = argparse.ArgumentParser(description="Basic drone example")
    parser.add_argument(
        "--drone",
        choices=["mavros", "bebop"],
        default="mavros",
        help="Drone type (default: mavros)",
    )
    args = parser.parse_args()

    rclpy.init()
    node = BasicExample(args.drone)

    try:
        node.run()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted")
        node.drone.land()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
