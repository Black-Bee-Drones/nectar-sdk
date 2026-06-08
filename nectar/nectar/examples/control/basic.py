#!/usr/bin/env python3
"""
Basic drone flight example -- works with any supported platform.

Three modes via --mode:
  velocity : takeoff, velocity box pattern, land (default)
  hover    : takeoff, hover for --hover-time seconds, land
  position : takeoff, position (move_to) box pattern, land

Usage:
    python basic.py --drone mavros
    python basic.py --drone crazyflie --mode hover --height 0.5
    python basic.py --drone crazyflie --mode position --height 0.5 --side 0.6
    python basic.py --drone bebop --mode velocity
"""

import argparse
import logging

import nectar
from nectar.control import (
    BebopConfig,
    CrazyflieConfig,
    DroneFactory,
    MavrosConfig,
    PoseSource,
)

log = logging.getLogger("basic_example")


def build_config(args: argparse.Namespace):
    if args.drone == "mavros":
        return MavrosConfig(pose_source=PoseSource.GPS, start_driver=False)
    if args.drone == "crazyflie":
        return CrazyflieConfig(
            start_driver=False,
            cf_name=args.cf_name,
            backend=args.backend,
        )
    return BebopConfig(start_driver=False)


def _height(drone) -> float:
    if hasattr(drone, "height"):
        return drone.height
    alt = drone.get_altitude() if hasattr(drone, "get_altitude") else None
    return alt if alt is not None else 0.0


def run_hover(drone, args: argparse.Namespace) -> None:
    if not drone.takeoff(altitude=args.height):
        log.error("Takeoff failed")
        return
    log.info("Hovering at %.2fm for %.0fs", _height(drone), args.hover_time)
    drone.delay(args.hover_time)
    log.info("Height after hover: %.2fm", _height(drone))
    drone.land()


def run_velocity(drone, args: argparse.Namespace) -> None:
    if not drone.takeoff(altitude=args.height):
        log.error("Takeoff failed")
        return
    log.info("Airborne at %.2fm", _height(drone))
    drone.delay(2.0)
    v = args.velocity
    t = args.side / v if v > 0 else 2.0
    log.info("Velocity box: v=%.2fm/s side=%.1fm", v, args.side)
    for label, vx, vy in [
        ("Forward", v, 0.0),
        ("Left", 0.0, v),
        ("Backward", -v, 0.0),
        ("Right", 0.0, -v),
    ]:
        log.info(label)
        drone.move_velocity(vx=vx, vy=vy, duration=t)
    drone.land()


def run_position(drone, args: argparse.Namespace) -> None:
    if not drone.takeoff(altitude=args.height):
        log.error("Takeoff failed")
        return
    log.info("Airborne at %.2fm", _height(drone))
    drone.delay(2.0)
    s = args.side
    log.info("Position box: side=%.1fm precision=%.2fm", s, args.precision)
    for label, x, y in [
        ("Forward", s, 0.0),
        ("Left", 0.0, s),
        ("Backward", -s, 0.0),
        ("Right", 0.0, -s),
    ]:
        log.info(label)
        drone.move_to(x=x, y=y, z=0.0, precision=args.precision)
        drone.delay(1.0)
    drone.land()


_RUNNERS = {"hover": run_hover, "velocity": run_velocity, "position": run_position}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Basic drone flight example")
    parser.add_argument("--drone", choices=["mavros", "bebop", "crazyflie"], default="mavros")
    parser.add_argument("--mode", choices=list(_RUNNERS), default="velocity")
    parser.add_argument("--height", type=float, default=1.5)
    parser.add_argument("--side", type=float, default=1.0)
    parser.add_argument("--velocity", type=float, default=0.3)
    parser.add_argument("--precision", type=float, default=0.10)
    parser.add_argument("--hover-time", type=float, default=10.0)
    parser.add_argument("--cf-name", default="cf231")
    parser.add_argument("--backend", default="cpp")
    args = parser.parse_args()

    nectar.init()
    drone = DroneFactory.create(args.drone, build_config(args))
    try:
        if not drone.connect():
            log.error("Connection failed")
            return
        _RUNNERS[args.mode](drone, args)
    except KeyboardInterrupt:
        log.info("Interrupted -- landing")
        drone.land()
    finally:
        drone.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
