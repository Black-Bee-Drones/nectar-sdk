#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from mirela_sdk.control import (
    DroneFactory,
    MavrosConfig,
    PoseSource,
    MoveReference,
    NavigationStrategy,
)


class MavrosNavigationExample(Node):
    def __init__(self):
        super().__init__("mavros_navigation_example")

        config = MavrosConfig(
            pose_source=PoseSource.GPS,
            start_driver=False,
        )

        self.drone = DroneFactory.create("mavros", config, self)
        self.get_logger().info("Drone initialized")

    def run(self):
        """Execute navigation sequence with move_to."""
        self.get_logger().info("Starting navigation test")

        # Takeoff
        if not self.drone.takeoff(altitude=2.0):
            self.get_logger().error("Takeoff failed")
            return

        self.drone.delay(3.0)

        waypoints = [
            (3.0, 0.0, 0.0),  # Forward 3m
            (0.0, 3.0, 0.0),  # Left 3m
            (-3.0, 0.0, 0.0),  # Back 3m
            (0.0, -3.0, 0.0),  # Right 3m (return)
        ]

        for i, (x, y, z) in enumerate(waypoints):
            self.get_logger().info(f"Waypoint {i+1}: x={x}, y={y}, z={z}")

            self.drone.move_to(
                x=x,
                y=y,
                z=z,
                reference=MoveReference.BODY,
                strategy=NavigationStrategy.PID,
                precision=0.2,
                timeout=30.0,
            )

            self.get_logger().info(f"Waypoint {i+1} reached")
            self.drone.delay(1.0)

        self.get_logger().info("Returning to launch")
        self.drone.rtl()


def main(args=None):
    rclpy.init(args=args)
    node = MavrosNavigationExample()

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
