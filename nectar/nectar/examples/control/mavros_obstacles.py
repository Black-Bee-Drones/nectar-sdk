#!/usr/bin/env python3
from functools import partial

import rclpy
from rclpy.node import Node

from nectar.control import (
    DepthObstacleDetector,
    DroneFactory,
    MavrosConfig,
    MoveReference,
    NavigationStrategy,
    PoseSource,
    strategies,
)


class MavrosObstaclesExample(Node):
    def __init__(self):
        super().__init__("mavros_obstacles_example")

        config = MavrosConfig(
            pose_source=PoseSource.GPS,
            start_driver=False,
        )

        self.drone = DroneFactory.create("mavros", config, self)
        self._setup_obstacle_detection()
        self.get_logger().info("Drone initialized with obstacle detection")

    def _setup_obstacle_detection(self):
        """Configure depth camera obstacle detection."""
        detector = DepthObstacleDetector(
            node=self,
            max_distance_mm=1500,
            depth_threshold_mm=1300,
            min_cluster_pixels=50,
        )

        # strategy = strategies.PauseStrategy()

        strategy = strategies.SequenceStrategy(
            partial(
                strategies.lateral_pass_return_sequence,
                lateral_distance=1.5,
                forward_distance=2.5,
                precision=0.3,
            )
        )

        self.drone.add_obstacle_detector("depth", detector, strategy)

    def run(self):
        """Execute navigation with obstacle avoidance."""
        self.get_logger().info("Starting obstacle avoidance test")

        if not self.drone.takeoff(altitude=1.5):
            self.get_logger().error("Takeoff failed")
            return

        self.drone.delay(3.0)

        self.drone.enable_obstacle_detector("depth")
        self.get_logger().info("Obstacle detection enabled")

        self.get_logger().info("Moving forward 10m with obstacle avoidance")
        self.drone.move_to(
            x=10.0,
            y=0.0,
            z=0.0,
            reference=MoveReference.BODY,
            strategy=NavigationStrategy.PID,
            precision=0.5,
            timeout=60.0,
        )

        self.drone.disable_obstacle_detector("depth")
        self.drone.land()
        self.get_logger().info("Test complete")


def main(args=None):
    rclpy.init(args=args)
    node = MavrosObstaclesExample()

    try:
        node.run()
    except KeyboardInterrupt:
        node.get_logger().info("Interrupted")
        node.drone.disable_all_obstacle_detectors()
        node.drone.land()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
