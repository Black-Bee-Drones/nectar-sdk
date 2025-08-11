from mirela_sdk.image_processing.camera import (
    ImageHandler,
    DepthCam,
    RealsenseCam,
    OakdCam,
)
import rclpy
from rclpy.node import Node
import cv2
import numpy as np
from typing import Optional, Tuple
import argparse


class DepthDemoNode(Node):
    def __init__(self, camera_type: str) -> None:
        super().__init__("depth_example")

        self.window: str = f"{camera_type.capitalize()} Color"
        self.depth_window: str = f"{camera_type.capitalize()} Depth"
        self.point_uv: Optional[Tuple[int, int]] = None  # (u, v)

        cv2.namedWindow(self.window)
        cv2.setMouseCallback(self.window, self._on_mouse)

        # Select and start camera using the DepthCam interface
        if camera_type == "oakd":
            cam = OakdCam()
            cam.start(cam_num=1, enable_depth=True, usb_full_speed=True)
        else:
            cam = RealsenseCam(fps=30)
            cam.start()

        self.cam = cam
        self.img_handler = ImageHandler(
            self,
            image_source=camera_type,
            camera=self.cam,
            image_processing_callback=self.process_frame,
            show_result=self.window,
        )
        self.img_handler.run()

        self.get_logger().info(
            "Click on the color image to select a pixel for distance measurement. Press 'q' to quit."
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
        if isinstance(self.cam, DepthCam):
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

        # Depth visualization (expects meters for both RealSense and Oak-D)
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

                if 0 <= u < depth_vis.shape[1] and 0 <= v < depth_vis.shape[0]:
                    cv2.circle(depth_vis, (u, v), 5, (255, 255, 255), -1)
                cv2.imshow(self.depth_window, depth_vis)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="Unified depth example for RealSense or Oak-D"
    )
    parser.add_argument("--camera", choices=["realsense", "oakd"], default="realsense")
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
