#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from nectar.vision.camera import ImageHandler
from nectar.vision.camera.config_builder import ConfigBuilder


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
        source_key = camera_type

        if camera_type == "webcam":
            params = {"device_index": 0, "width": 1280, "height": 720, "fps": 30}
        elif camera_type == "imx219":
            params = {"sensor_id": 0, "width": 1280, "height": 720, "flip": 2}
        elif camera_type == "realsense":
            params = {
                "color_width": 1280,
                "color_height": 720,
                "depth_width": 1280,
                "depth_height": 720,
                "fps": 30,
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
        return config, source_key

    def process_frame(self, frame):
        if frame is not None:
            self.count += 1
            self.get_logger().info(f"Received frame with shape: {frame.shape}")
            # cv2.imwrite(f"frame_{self.count}.png", frame)

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
