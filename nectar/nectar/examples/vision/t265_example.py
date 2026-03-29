#!/usr/bin/env python3
"""
T265 tracking camera example: fisheye stereo display, stereo depth
visualization with click-to-measure, and 6DOF pose overlay.

Usage:
    # Direct pyrealsense2 (T265 not shared with realsense_ros)
    ros2 run nectar t265_example.py

    # ROS topic mode (realsense2_camera already running)
    ros2 run nectar t265_example.py --mode ros

    # Depth disabled (fisheye + pose only)
    ros2 run nectar t265_example.py --no-depth
"""

import argparse
from typing import Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.camera import T265Cam, T265Config


class T265DemoNode(Node):
    def __init__(self, mode: str, enable_depth: bool) -> None:
        super().__init__("t265_example")

        self.enable_depth = enable_depth
        self.fisheye_window = "T265 Fisheye (L | R)"
        self.depth_window = "T265 Stereo Depth (click to measure)"
        self.depth_point: Optional[Tuple[int, int]] = None

        use_ros = mode == "ros"
        config = T265Config(
            enable_depth=enable_depth,
            enable_pose=True,
            use_ros_topics=use_ros,
        )

        self.cam = T265Cam(config, node=self if use_ros else None)
        self.cam.start()

        cv2.namedWindow(self.fisheye_window)
        if enable_depth:
            cv2.namedWindow(self.depth_window)
            cv2.setMouseCallback(self.depth_window, self._on_depth_click)

        period = 1.0 / 30.0
        self.timer = self.create_timer(period, self._tick)
        self.get_logger().info(
            f"T265 started ({'ROS topics' if use_ros else 'direct pyrealsense2'}, "
            f"depth={'on' if enable_depth else 'off'}). "
            "Click on depth window to measure distance. Press 'q' to quit."
        )

    def _on_depth_click(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.depth_point = (x, y)

    def _tick(self) -> None:
        stereo = self.cam.get_stereo_frames()
        if stereo is None:
            return
        left, right = stereo

        left_bgr = cv2.cvtColor(left, cv2.COLOR_GRAY2BGR)
        right_bgr = cv2.cvtColor(right, cv2.COLOR_GRAY2BGR)
        combined = np.hstack((left_bgr, right_bgr))

        pose = self.cam.get_pose()
        t = pose.translation
        v = pose.velocity
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

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            self.cam.close()
            cv2.destroyAllWindows()
            raise SystemExit

    def _show_depth(self, depth: np.ndarray) -> None:
        depth_vis = depth.copy()
        depth_vis[depth_vis <= 0] = float("nan")
        max_m, min_m = 3.0, 0.1
        depth_vis = 255 * (depth_vis - min_m) / (max_m - min_m)
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


def main():
    parser = argparse.ArgumentParser(description="T265 tracking camera example")
    parser.add_argument(
        "--mode",
        choices=["direct", "ros"],
        default="direct",
        help="'direct' for pyrealsense2, 'ros' for ROS topic mode",
    )
    parser.add_argument(
        "--no-depth",
        action="store_true",
        help="Disable stereo depth computation (fisheye + pose only)",
    )
    args, _ = parser.parse_known_args()

    rclpy.init()
    node = T265DemoNode(mode=args.mode, enable_depth=not args.no_depth)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.cam.close()
        cv2.destroyAllWindows()
        rclpy.shutdown()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
