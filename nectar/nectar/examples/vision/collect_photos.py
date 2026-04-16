#!/usr/bin/env python3
"""
Usage:
    # Default (webcam, 1 photo/sec, auto-named run)
    ros2 run nectar collect_photos.py

    # USB camera with custom output and interval
    ros2 run nectar collect_photos.py --ros-args \
        -p camera_type:=webcam \
        -p output_dir:=hook_photos \
        -p capture_interval:=0.5

    # Named run for a specific flight session
    ros2 run nectar collect_photos.py --ros-args \
        -p output_dir:=hook_photos \
        -p run_name:=flight_01_low_alt

    # RealSense camera, JPEG quality 95, with preview
    ros2 run nectar collect_photos.py --ros-args \
        -p camera_type:=realsense \
        -p jpeg_quality:=95 \
        -p show_preview:=true

    # Higher resolution webcam
    ros2 run nectar collect_photos.py --ros-args \
        -p camera_type:=webcam \
        -p width:=1920 -p height:=1080
"""

import time
from datetime import datetime
from pathlib import Path

import cv2
import rclpy
from rclpy.node import Node

from nectar.vision.camera.config_builder import ConfigBuilder
from nectar.vision.camera.handler import ImageHandler


class CollectPhotosNode(Node):
    """ROS 2 node that captures and saves camera frames."""

    def __init__(self) -> None:
        super().__init__("collect_photos")

        self.declare_parameter("camera_type", "webcam")
        self.declare_parameter("output_dir", "collected_photos")
        self.declare_parameter("run_name", "")
        self.declare_parameter("capture_interval", 1.0)
        self.declare_parameter("image_format", "jpg")
        self.declare_parameter("jpeg_quality", 90)
        self.declare_parameter("show_preview", False)
        self.declare_parameter("max_photos", 0)
        self.declare_parameter("width", 1280)
        self.declare_parameter("height", 720)
        self.declare_parameter("fps", 30)

        camera_type = self.get_parameter("camera_type").value
        output_dir = self.get_parameter("output_dir").value
        run_name = self.get_parameter("run_name").value
        self._capture_interval: float = self.get_parameter("capture_interval").value
        self._image_format: str = self.get_parameter("image_format").value
        self._jpeg_quality: int = self.get_parameter("jpeg_quality").value
        show_preview: bool = self.get_parameter("show_preview").value
        self._max_photos: int = self.get_parameter("max_photos").value

        self._output_path = self._setup_output_dir(output_dir, run_name)
        self._photo_count = 0
        self._last_capture_time = 0.0

        config, source = self._get_camera_config(camera_type)
        window_name = "Collect Photos" if show_preview else None

        self.image_handler = ImageHandler(
            node=self,
            image_source=source,
            config=config,
            show_result=window_name,
            image_processing_callback=self._on_frame,
            poll_interval=0.01,
        )
        self.image_handler.run()

        self.get_logger().info(
            f"Collecting photos — camera: {camera_type}, "
            f"interval: {self._capture_interval}s, "
            f"output: {self._output_path}"
        )

    def _setup_output_dir(self, output_dir: str, run_name: str) -> Path:
        """Create output directory: ~/<output_dir>/<run_name>/"""
        if not run_name:
            run_name = datetime.now().strftime("%Y%m%d_%H%M%S")

        path = Path.home() / output_dir / run_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_camera_config(self, camera_type: str) -> tuple:
        """Return (config, source_key) using declared ROS params directly."""
        source_key = camera_type
        w = self.get_parameter("width").value
        h = self.get_parameter("height").value
        fps = self.get_parameter("fps").value

        if camera_type == "webcam":
            params = {"device_index": 0, "width": w, "height": h, "fps": fps}
        elif camera_type == "realsense":
            params = {
                "color_width": w,
                "color_height": h,
                "depth_width": w,
                "depth_height": h,
                "fps": fps,
            }
        elif camera_type == "realsense_ros":
            params = {
                "topic": "/camera/color/image_raw/compressed",
                "compressed": True,
                "depth_topic": "/camera/depth/image_rect_raw",
                "depth_compressed": False,
            }
            source_key = "ros_depth"
        elif camera_type == "c920":
            params = {"profile": 1}
        elif camera_type == "imx219":
            params = {"sensor_id": 0, "width": w, "height": h, "flip": 2, "fps": fps}
        elif camera_type == "oakd":
            params = {}
        elif camera_type == "ros":
            params = {
                "topic": "/camera/color/image_raw/compressed",
                "compressed": True,
            }
        else:
            return None, camera_type

        config = ConfigBuilder.build(source_key, params)
        self.get_logger().info(f"Camera config: {camera_type} {w}x{h} @ {fps}fps")
        return config, source_key

    def _on_frame(self, frame) -> None:
        """Save frame if the capture interval has elapsed."""
        if frame is None:
            return

        now = time.time()
        if now - self._last_capture_time < self._capture_interval:
            return

        self._photo_count += 1
        self._last_capture_time = now

        ext = self._image_format
        filename = f"frame_{self._photo_count:05d}.{ext}"
        filepath = self._output_path / filename

        params = []
        if ext in ("jpg", "jpeg"):
            params = [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        elif ext == "png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

        cv2.imwrite(str(filepath), frame, params)
        self.get_logger().info(
            f"[{self._photo_count}] Saved {filename} ({frame.shape[1]}x{frame.shape[0]})"
        )

        if self._max_photos > 0 and self._photo_count >= self._max_photos:
            self.get_logger().info(f"Reached max_photos ({self._max_photos}). Stopping.")
            raise SystemExit(0)

    def destroy_node(self) -> None:
        self.image_handler.cleanup()
        self.get_logger().info(
            f"Collection finished — {self._photo_count} photos saved to {self._output_path}"
        )
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = CollectPhotosNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        if node:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
