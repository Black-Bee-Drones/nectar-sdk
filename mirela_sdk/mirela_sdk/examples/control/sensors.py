#!/usr/bin/env python3
import argparse
import rclpy
from rclpy.node import Node

from mirela_sdk.control import DroneFactory, MavrosConfig, PoseSource


class SensorsExample(Node):
    def __init__(self, source: str):
        super().__init__("sensors_example")

        pose_source = PoseSource.VISION if source == "vision" else PoseSource.GPS
        config = MavrosConfig(pose_source=pose_source, start_driver=False)

        self.drone = DroneFactory.create("mavros", config, self)
        self.source = source
        self.get_logger().info(f"Initialized with {source} source")

    def run(self, duration: float = 30.0):
        """Monitor sensor data for specified duration."""
        self.get_logger().info(f"Monitoring {self.source} data for {duration}s...")

        iterations = int(duration * 10)

        for i in range(iterations):
            self.drone.delay(0.1)

            if (i + 1) % 10 == 0:
                self._log_data()

        self.get_logger().info("Monitoring complete")

    def _log_data(self):
        """Log current sensor data."""
        height = self.drone.height
        lidar = self.drone.lidar_alt

        if self.source == "gps":
            gps = self.drone.gps
            heading = self.drone.heading
            rel_alt = self.drone.rel_alt

            self.get_logger().info(
                f"GPS: lat={gps.latitude:.6f}, lon={gps.longitude:.6f}, "
                f"alt={gps.altitude:.1f}m | heading={heading:.1f}° | "
                f"rel_alt={rel_alt:.2f}m | height={height:.2f}m | lidar={lidar}"
            )
        else:
            vision = self.drone.vision_pos
            if vision:
                pos = vision.pose.pose.position
                self.get_logger().info(
                    f"Vision: x={pos.x:.2f}, y={pos.y:.2f}, z={pos.z:.2f} | "
                    f"height={height:.2f}m | lidar={lidar}"
                )
            else:
                self.get_logger().warn("No vision data")


def main():
    parser = argparse.ArgumentParser(description="Sensor monitoring example")
    parser.add_argument(
        "--source",
        choices=["gps", "vision"],
        default="gps",
        help="Position source (default: gps)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Monitoring duration in seconds (default: 30)",
    )
    args = parser.parse_args()

    rclpy.init()
    node = SensorsExample(args.source)

    try:
        node.run(args.duration)
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
