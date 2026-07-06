#!/usr/bin/env python3
r"""
Optical flow demo

Runs :class:`nectar.vision.algorithms.flow.OpticalFlowEstimator` on frames
Prints flow in px/s plus, when
``--focal``/``--altitude`` are given, angular rate in rad/s and horizontal
velocity in m/s

Usage
-----
    python -m nectar.examples.vision.optical_flow_example
    python -m nectar.examples.vision.optical_flow_example --source realsense
    python -m nectar.examples.vision.optical_flow_example \
        --source /camera/image_raw --method lucas_kanade --focal 500 --altitude 1.5

"""

from __future__ import annotations

import argparse
import logging
import time

import nectar
from nectar.vision.algorithms.flow import OpticalFlowConfig, OpticalFlowEstimator
from nectar.vision.camera import ImageHandler

log = logging.getLogger("optical_flow_example")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optical flow demo")
    parser.add_argument(
        "--source",
        default="webcam",
        help=(
            "Camera source: a registered key (webcam, realsense, oakd, c920, imx219), "
            "a ROS topic (e.g. /camera/image_raw), or an image/video file path"
        ),
    )
    parser.add_argument(
        "--method",
        choices=["farneback", "lucas_kanade"],
        default="farneback",
        help="Optical flow backend",
    )
    parser.add_argument(
        "--focal",
        type=float,
        default=0.0,
        help="Camera focal length in pixels (0 = skip rad/s and m/s decode)",
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=0.0,
        help="Camera altitude in meters (0 = skip m/s decode)",
    )
    parser.add_argument("--no-show", action="store_true", help="Disable preview window")
    return parser.parse_args()


def _format(result) -> str:
    px = result.mean_flow_px_per_s
    msg = (
        f"flow=({px[0]:+.1f},{px[1]:+.1f}) px/s  "
        f"q={result.quality:.2f}  n={result.n_vectors}  dt={result.dt_s * 1000.0:.1f}ms"
    )
    if result.angular_rate_rad_s is not None:
        w = result.angular_rate_rad_s
        msg += f"  omega=({w[0]:+.3f},{w[1]:+.3f}) rad/s"
    if result.velocity_m_s is not None:
        v = result.velocity_m_s
        msg += f"  v=({v[0]:+.3f},{v[1]:+.3f}) m/s"
    return msg


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args = _parse_args()

    estimator = OpticalFlowEstimator(OpticalFlowConfig(method=args.method))
    focal_px = args.focal if args.focal > 0.0 else None
    altitude_m = args.altitude if args.altitude > 0.0 else None
    last_print = [0.0]

    def on_frame(frame) -> None:
        if frame is None:
            return
        result = estimator.process(frame, focal_px=focal_px, altitude_m=altitude_m)
        if result is None:
            return

        frame[:] = result.visualization
        now = time.monotonic()
        if now - last_print[0] > 0.25:
            last_print[0] = now
            log.info(_format(result))

    nectar.init()
    handler = ImageHandler(
        image_source=args.source,
        show_result=None if args.no_show else "Optical Flow",
        image_processing_callback=on_frame,
        poll_interval=0.0003,
    )
    handler.run()
    log.info("Running %s flow on '%s'. Press 'q' or Ctrl+C to quit.", args.method, args.source)
    try:
        nectar.spin()
    finally:
        handler.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
