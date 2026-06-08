#!/usr/bin/env python3
r"""
Optical flow demo (headless, no ROS).

Captures from a local camera with OpenCV and runs the
:class:`nectar.vision.algorithms.flow.OpticalFlowEstimator` on every
frame. Prints flow rate in px/s plus (optionally) angular rate in rad/s
and horizontal velocity in m/s, mirroring the MTF-01 + ArduPilot EKF
pipeline documented in ``drone/3-optical-flow.md``.

Usage
-----
    python -m nectar.examples.vision.optical_flow_example
    python -m nectar.examples.vision.optical_flow_example \
        --method lucas_kanade --focal 500 --altitude 1.5

"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

import cv2

from nectar.vision.algorithms.flow import (
    OpticalFlowConfig,
    OpticalFlowEstimator,
)

log = logging.getLogger("optical_flow_example")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", type=int, default=0, help="Camera device index (default: 0)")
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
        help="Camera focal length in pixels (0 = disable rad/s and m/s decode)",
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=0.0,
        help="Camera altitude in meters (0 = disable m/s decode)",
    )
    parser.add_argument("--width", type=int, default=640, help="Capture width (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Capture height (default: 480)")
    parser.add_argument("--no-show", action="store_true", help="Disable preview window")
    return parser.parse_args()


def _open_camera(device: int, width: int, height: int) -> Optional[cv2.VideoCapture]:
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        log.error("Could not open camera device %d", device)
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
    return cap


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args = _parse_args()

    cap = _open_camera(args.device, args.width, args.height)
    if cap is None:
        return 1

    estimator = OpticalFlowEstimator(OpticalFlowConfig(method=args.method))
    focal_px = args.focal if args.focal > 0.0 else None
    altitude_m = args.altitude if args.altitude > 0.0 else None

    log.info("Running %s flow. Press 'q' or Ctrl+C to quit.", args.method)
    last_print = 0.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            result = estimator.process(frame, focal_px=focal_px, altitude_m=altitude_m)

            display = result.visualization if result is not None else frame

            if not args.no_show:
                cv2.imshow("Optical Flow Demo", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.monotonic()
            if result is not None and now - last_print > 0.25:
                last_print = now
                px = result.mean_flow_px_per_s
                msg = (
                    f"flow=({px[0]:+.1f},{px[1]:+.1f}) px/s  "
                    f"q={result.quality:.2f}  n={result.n_vectors}  "
                    f"dt={result.dt_s * 1000.0:.1f}ms"
                )
                if result.angular_rate_rad_s is not None:
                    w = result.angular_rate_rad_s
                    msg += f"  omega=({w[0]:+.3f},{w[1]:+.3f}) rad/s"
                if result.velocity_m_s is not None:
                    v = result.velocity_m_s
                    msg += f"  v=({v[0]:+.3f},{v[1]:+.3f}) m/s"
                log.info(msg)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if not args.no_show:
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
