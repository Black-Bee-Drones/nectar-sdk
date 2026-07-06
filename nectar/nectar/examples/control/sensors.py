#!/usr/bin/env python3
import argparse
import logging

import nectar
from nectar.control import AltitudeSource, DroneFactory, MavrosConfig, PoseSource

log = logging.getLogger("sensors_example")


def run(drone, source: str, duration: float) -> None:
    log.info("Monitoring %s data for %.0fs...", source, duration)
    iterations = int(duration * 10)
    for i in range(iterations):
        drone.delay(0.1)
        if (i + 1) % 10 == 0:
            _log_data(drone, source)
    log.info("Monitoring complete")


def _log_data(drone, source: str) -> None:
    altitude = drone.get_altitude()
    lidar = drone.get_altitude(AltitudeSource.LIDAR)
    local = drone.local_pose
    local_str = (
        f"x={local.position.x:.2f}, y={local.position.y:.2f}, z={local.position.z:.2f}"
        if local
        else "N/A"
    )
    if source == "gps":
        gps = drone.gps
        log.info(
            "GPS: lat=%.6f, lon=%.6f, alt=%.1fm | heading=%.1f deg | rel_alt=%.2fm | lidar=%s | local=[%s]",
            gps.latitude,
            gps.longitude,
            gps.altitude,
            drone.heading,
            drone.rel_alt,
            lidar,
            local_str,
        )
    else:
        vision = drone.vision_pose
        if vision:
            p = vision.position
            log.info(
                "Vision: x=%.2f, y=%.2f, z=%.2f | altitude=%s | lidar=%s | local=[%s]",
                p.x,
                p.y,
                p.z,
                altitude,
                lidar,
                local_str,
            )
        else:
            log.warning("No vision data")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Sensor monitoring example")
    parser.add_argument("--source", choices=["gps", "vision"], default="gps")
    parser.add_argument("--duration", type=float, default=30.0)
    args = parser.parse_args()

    nectar.init()
    pose_source = PoseSource.VISION if args.source == "vision" else PoseSource.GPS
    drone = DroneFactory.create(
        "mavros",
        MavrosConfig(pose_source=pose_source, start_driver=False),
    )
    try:
        run(drone, args.source, args.duration)
    except KeyboardInterrupt:
        log.info("Interrupted")
    finally:
        drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
