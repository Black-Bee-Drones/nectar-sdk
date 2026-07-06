#!/usr/bin/env python3
"""T265 tracking camera demo: fisheye stereo, stereo depth, 6DOF pose overlay.

Run:
    ros2 run nectar t265_example.py
    ros2 run nectar t265_example.py --mode ros
    ros2 run nectar t265_example.py --no-depth
"""

import argparse
import logging
import threading
from typing import Optional, Tuple

import cv2
import numpy as np

import nectar
from nectar.vision.camera import T265Cam, T265Config

log = logging.getLogger("t265_example")


class T265Demo:
    def __init__(self, mode: str, enable_depth: bool) -> None:
        self.enable_depth = enable_depth
        self.fisheye_window = "T265 Fisheye (L | R)"
        self.depth_window = "T265 Stereo Depth (click to measure)"
        self.depth_point: Optional[Tuple[int, int]] = None
        self._stop = threading.Event()

        self.cam = T265Cam(
            T265Config(
                enable_depth=enable_depth,
                enable_pose=True,
                use_ros_topics=mode == "ros",
            )
        )
        self.cam.start()

        cv2.namedWindow(self.fisheye_window)
        if enable_depth:
            cv2.namedWindow(self.depth_window)
            cv2.setMouseCallback(self.depth_window, self._on_depth_click)

        log.info(
            "T265 started (%s, depth=%s). Click depth window to measure. Press 'q' to quit.",
            "ROS topics" if mode == "ros" else "direct pyrealsense2",
            "on" if enable_depth else "off",
        )

    def _on_depth_click(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.depth_point = (x, y)

    def run(self) -> None:
        period = 1.0 / 30.0
        while not self._stop.is_set():
            self._tick()
            cv2.waitKey(int(period * 1000))

    def _tick(self) -> None:
        stereo = self.cam.get_stereo_frames()
        if stereo is None:
            return
        left, right = stereo
        combined = np.hstack(
            (cv2.cvtColor(left, cv2.COLOR_GRAY2BGR), cv2.cvtColor(right, cv2.COLOR_GRAY2BGR))
        )

        pose = self.cam.get_pose()
        t, v = pose.translation, pose.velocity
        cv2.putText(
            combined,
            f"pos: ({t[0]:+.2f}, {t[1]:+.2f}, {t[2]:+.2f})  conf: {pose.tracker_confidence}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            combined,
            f"vel: ({v[0]:+.2f}, {v[1]:+.2f}, {v[2]:+.2f})",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

        cv2.imshow(self.fisheye_window, combined)

        if self.enable_depth:
            depth = self.cam.get_depth_frame()
            if depth is not None:
                self._show_depth(depth)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            self._stop.set()

    def _show_depth(self, depth: np.ndarray) -> None:
        depth_vis = depth.copy()
        depth_vis[depth_vis <= 0] = float("nan")
        depth_vis = 255 * (depth_vis - 0.1) / (3.0 - 0.1)
        depth_vis = np.nan_to_num(depth_vis, nan=0.0).astype("uint8")
        depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

        if self.depth_point is not None:
            u, v = self.depth_point
            dh, dw = depth_color.shape[:2]
            u = max(0, min(dw - 1, u))
            v = max(0, min(dh - 1, v))
            dist = self.cam.get_distance(u, v)
            label = f"{dist:.2f}m" if dist else "N/A"
            cv2.circle(depth_color, (u, v), 4, (255, 255, 255), -1)
            cv2.putText(
                depth_color,
                label,
                (u + 8, v - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        cv2.imshow(self.depth_window, depth_color)

    def close(self) -> None:
        self._stop.set()
        self.cam.close()
        cv2.destroyAllWindows()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="T265 tracking camera example")
    parser.add_argument("--mode", choices=["direct", "ros"], default="direct")
    parser.add_argument("--no-depth", action="store_true")
    args, _ = parser.parse_known_args()

    nectar.init()
    demo = T265Demo(mode=args.mode, enable_depth=not args.no_depth)
    try:
        demo.run()
    except KeyboardInterrupt:
        pass
    finally:
        demo.close()
        nectar.shutdown()


if __name__ == "__main__":
    main()
