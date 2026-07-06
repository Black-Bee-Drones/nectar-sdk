#!/usr/bin/env python3
import argparse
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

import nectar
from nectar.vision.camera import (
    DepthCam,
    ImageHandler,
    OakdCam,
    OakDConfig,
    RealsenseCam,
    RealSenseConfig,
    ROSDepthCam,
    ROSDepthConfig,
)

log = logging.getLogger("depth_example")


class DepthDemo:
    def __init__(self, camera_type: str) -> None:
        self.window = f"{camera_type.replace('_', ' ').title()} Color"
        self.depth_window = f"{camera_type.replace('_', ' ').title()} Depth"
        self.point_uv: Optional[Tuple[int, int]] = None

        cv2.namedWindow(self.window)
        cv2.setMouseCallback(self.window, self._on_mouse)

        self.cam = self._build_camera(camera_type)
        source_key = {"oakd": "oakd", "realsense_ros": "ros_depth"}.get(camera_type, "realsense")

        self.handler = ImageHandler(
            image_source=source_key,
            camera=self.cam,
            image_processing_callback=self.process_frame,
            show_result=self.window,
        )
        self.handler.run()
        log.info("Click on the color image to select a pixel. Press 'q' to quit.")

    @staticmethod
    def _build_camera(camera_type: str) -> DepthCam:
        if camera_type == "oakd":
            cam = OakdCam(OakDConfig(cam_num=1, enable_depth=True))
            cam.start()
            return cam
        if camera_type == "realsense_ros":
            cam = ROSDepthCam(
                config=ROSDepthConfig(
                    topic="/camera/color/image_raw/compressed",
                    compressed=True,
                    depth_topic="/camera/depth/image_rect_raw/compressedDepth",
                    depth_compressed=True,
                )
            )
            cam.start()
            log.info("Using ROS topics: %s, %s", cam.color_topic, cam.depth_topic)
            return cam
        cam = RealsenseCam(
            RealSenseConfig(
                color_res=(1280, 720),
                depth_res=(1280, 720),
                fps=30,
                align_to_color=True,
            )
        )
        cam.start()
        return cam

    def _on_mouse(self, event, x, y, flags, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.point_uv = (x, y)

    def process_frame(self, img) -> None:
        if img is None:
            return
        h, w = img.shape[:2]
        u, v = self.point_uv if self.point_uv is not None else (w // 2, h // 2)
        u = max(0, min(w - 1, u))
        v = max(0, min(h - 1, v))

        distance_text = "Distance: N/A"
        if isinstance(self.cam, ROSDepthCam):
            dist_m = self.cam.get_distance(u, v, color_shape=img.shape)
        elif isinstance(self.cam, DepthCam):
            dist_m = self.cam.get_distance(u, v)
        else:
            dist_m = None
        if dist_m is not None and dist_m > 0:
            distance_text = f"Distance: {dist_m:.3f} m"

        cv2.circle(img, (u, v), 5, (0, 255, 255), thickness=-1)
        cv2.putText(
            img,
            distance_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        self._render_depth(img, u, v, w, h)

    def _render_depth(self, img, u: int, v: int, w: int, h: int) -> None:
        try:
            depth = self.cam.get_depth_frame()
        except Exception:
            return
        if depth is None:
            return
        depth_clip = depth.copy()
        depth_clip[depth_clip <= 0] = float("nan")
        depth_vis = 255 * (depth_clip - 0.1) / (3.0 - 0.1)
        depth_vis = cv2.normalize(depth_vis, None, 0, 255, cv2.NORM_MINMAX)
        depth_vis = np.nan_to_num(depth_vis, nan=0.0).astype("uint8")
        depth_vis = cv2.applyColorMap(depth_vis, cv2.COLORMAP_PLASMA)

        depth_h, depth_w = depth_vis.shape[:2]
        if isinstance(self.cam, ROSDepthCam):
            scaled_u = int(u * depth_w / w)
            scaled_v = int(v * depth_h / h)
        else:
            scaled_u, scaled_v = u, v
        if 0 <= scaled_u < depth_w and 0 <= scaled_v < depth_h:
            cv2.circle(depth_vis, (scaled_u, scaled_v), 5, (255, 255, 255), -1)
        cv2.imshow(self.depth_window, depth_vis)


def main():
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Depth camera example")
    parser.add_argument(
        "--camera",
        choices=["realsense", "realsense_ros", "oakd"],
        default="realsense",
    )
    args, _ = parser.parse_known_args()

    nectar.init()
    demo = DepthDemo(camera_type=args.camera)
    try:
        nectar.spin()
    finally:
        demo.handler.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
