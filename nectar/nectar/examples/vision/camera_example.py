#!/usr/bin/env python3
import cv2
import rclpy
from rclpy.node import Node

from nectar.vision.camera import (
    C920Config,
    ImageHandler,
    IMX219Config,
    OakDConfig,
    OpenCVConfig,
    RealSenseConfig,
    ROSConfig,
    ROSDepthConfig,
)


class CameraExampleNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_example_node")

        self.declare_parameter("camera_type", "webcam")
        self.declare_parameter("show_result", True)

        camera_type = self.get_parameter("camera_type").get_parameter_value().string_value
        show_result = self.get_parameter("show_result").get_parameter_value().bool_value

        config, source = self._get_camera_config(camera_type)
        window_name = "Camera Viewer" if show_result else None
        self.count = 0

        self.image_handler = ImageHandler(
            node=self,
            image_source=source,
            config=config,
            show_result=window_name,
            image_processing_callback=self.process_frame,
            poll_interval=0.0003,
        )
        self.image_handler.run()
        self.get_logger().info(f"Started {camera_type} camera.")

    def _get_camera_config(self, camera_type: str) -> tuple:
        """Return (config, source_key) for the given camera type."""
        if camera_type == "webcam":
            return (
                OpenCVConfig(device_index=0, width=1280, height=720, fps=30),
                "webcam",
            )
        if camera_type == "imx219":
            return IMX219Config(sensor_id=0, width=1280, height=720, flip=2), "imx219"
        if camera_type == "realsense":
            return (
                RealSenseConfig(color_res=(1280, 720), depth_res=(1280, 720), fps=30),
                "realsense",
            )
        if camera_type == "realsense_ros":
            return (
                ROSDepthConfig(
                    topic="/camera/color/image_raw/compressed",
                    compressed=True,
                    depth_topic="/camera/depth/image_rect_raw",
                    depth_compressed=False,
                ),
                "ros_depth",
            )
        if camera_type == "c920":
            return C920Config(profile=1), "c920"
        if camera_type == "oakd":
            return OakDConfig(), "oakd"
        if camera_type == "ros":
            return (
                ROSConfig(topic="/camera/color/image_raw/compressed", compressed=True),
                "ros",
            )

        return None, camera_type

    def process_frame(self, frame):
        if frame is not None:
            self.count += 1
            self.get_logger().info(f"Received frame with shape: {frame.shape}")
            cv2.imwrite(f"frame_{self.count}.png", frame)

    def destroy_node(self):
        self.image_handler.cleanup()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = CameraExampleNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
