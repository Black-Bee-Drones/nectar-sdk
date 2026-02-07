import argparse
from typing import Optional, Tuple

import rclpy
from rclpy.node import Node
import cv2
import numpy as np

from mirela_sdk.vision.camera import (
    ImageHandler,
    DepthCam,
    RealsenseCam,
    OakdCam,
    ROSDepthCam,
    RealSenseConfig,
    OakDConfig,
    ROSDepthConfig,
)


class DepthDemoNode(Node):
    def __init__(self, camera_type: str) -> None:
        super().__init__("depth_example")

        self.window: str = f"{camera_type.replace('_', ' ').title()} Color"
        self.depth_window: str = f"{camera_type.replace('_', ' ').title()} Depth"
        self.point_uv: Optional[Tuple[int, int]] = None

        cv2.namedWindow(self.window)
        cv2.setMouseCallback(self.window, self._on_mouse)

        if camera_type == "oakd":
            config = OakDConfig(cam_num=1, enable_depth=True)
            cam = OakdCam(config)
            cam.start()
            source_key = "oakd"
        elif camera_type == "realsense_ros":
            config = ROSDepthConfig(
                topic="/camera/color/image_raw/compressed",
                compressed=True,
                depth_topic="/camera/depth/image_rect_raw/compressedDepth",
                depth_compressed=True,
            )
            cam = ROSDepthCam(self, config)
            cam.start()
            source_key = "ros_depth"
            self.get_logger().info(
                f"Using ROS topics: {config.topic}, {cam.depth_topic}"
            )
        else:
            config = RealSenseConfig(
                color_res=(1280, 720),
                depth_res=(1280, 720),
                fps=30,
                align_to_color=True,
            )
            cam = RealsenseCam(config)
            cam.start()
            source_key = "realsense"

        self.cam = cam
        self.img_handler = ImageHandler(
            self,
            image_source=source_key,
            camera=self.cam,
            image_processing_callback=self.process_frame,
            show_result=self.window,
        )
        self.img_handler.run()

        self.get_logger().info(
            "Click on the color image to select a pixel for distance measurement. "
            "Press 'q' to quit."
        )

    def _on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.point_uv = (x, y)

    def process_frame(self, img):
        if img is None:
            return

        h, w = img.shape[:2]
        u = w // 2
        v = h // 2
        if self.point_uv is not None:
            u, v = self.point_uv
            u = max(0, min(w - 1, u))
            v = max(0, min(h - 1, v))

        distance_text = "Distance: N/A"
        if isinstance(self.cam, ROSDepthCam):
            dist_m = self.cam.get_distance(u, v, color_shape=img.shape)
            if dist_m is not None and dist_m > 0:
                distance_text = f"Distance: {dist_m:.3f} m"
        elif isinstance(self.cam, DepthCam):
            dist_m = self.cam.get_distance(u, v)
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

        try:
            depth = self.cam.get_depth_frame()
            if depth is not None:
                depth_clip = depth.copy()
                depth_clip[depth_clip <= 0] = float("nan")
                max_m = 3.0
                min_m = 0.1
                depth_vis = 255 * (depth_clip - min_m) / (max_m - min_m)
                depth_vis = depth_vis.astype("float32")
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
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Depth camera example for RealSense (SDK or ROS topics) or OAK-D"
    )
    parser.add_argument(
        "--camera",
        choices=["realsense", "realsense_ros", "oakd"],
        default="realsense",
        help="Camera type: 'realsense' (pyrealsense2), 'realsense_ros' (ROSDepthCam), "
        "or 'oakd'",
    )
    args, _ = parser.parse_known_args()

    rclpy.init()
    node = DepthDemoNode(camera_type=args.camera)
    try:
        rclpy.spin(node)
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
