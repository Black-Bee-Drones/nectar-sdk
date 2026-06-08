#!/usr/bin/env python3
import logging
from functools import partial

import nectar
from nectar.control import (
    DepthObstacleDetector,
    DroneFactory,
    MavrosConfig,
    MoveReference,
    NavigationMethod,
    PoseSource,
    strategies,
)

log = logging.getLogger("mavros_obstacles")


def setup_obstacle_detection(drone) -> None:
    detector = DepthObstacleDetector(
        max_distance_mm=1500,
        depth_threshold_mm=1300,
        min_cluster_pixels=50,
    )
    strategy = strategies.SequenceStrategy(
        partial(
            strategies.lateral_pass_return_sequence,
            lateral_distance=1.5,
            forward_distance=2.5,
            precision=0.3,
        )
    )
    drone.add_obstacle_detector("depth", detector, strategy)


def run(drone) -> None:
    log.info("Starting obstacle avoidance test")
    if not drone.takeoff(altitude=1.5):
        log.error("Takeoff failed")
        return
    drone.delay(3.0)
    drone.enable_obstacle_detector("depth")
    log.info("Obstacle detection enabled")
    log.info("Moving forward 10m with obstacle avoidance")
    drone.move_to(
        x=10.0,
        y=0.0,
        z=0.0,
        reference=MoveReference.BODY,
        method=NavigationMethod.PID,
        precision=0.5,
        timeout=60.0,
    )
    drone.disable_obstacle_detector("depth")
    drone.land()
    log.info("Test complete")


def main(args=None) -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    nectar.init()
    config = MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
    drone = DroneFactory.create("mavros", config)
    setup_obstacle_detection(drone)
    try:
        run(drone)
    except KeyboardInterrupt:
        log.info("Interrupted")
        drone.disable_all_obstacle_detectors()
        drone.land()
    finally:
        drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
