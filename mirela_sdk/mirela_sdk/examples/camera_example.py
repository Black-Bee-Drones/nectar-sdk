import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
import cv2

from mirela_sdk.image_processing.camera import (
    ImageHandler,
    CameraConfig,
    OpenCVConfig,
    IMX219Config,
    RealSenseConfig,
    OakDConfig,
    C920Config,
    ROSConfig,
)


class CameraExampleNode(Node):
    def __init__(self) -> None:
        super().__init__("camera_example_node")

        self.declare_parameter("camera_type", "webcam")
        self.declare_parameter("show_result", True)

        camera_type = (
            self.get_parameter("camera_type").get_parameter_value().string_value
        )
        show_result = self.get_parameter("show_result").get_parameter_value().bool_value

        config = self._get_camera_config(camera_type)
        window_name = "Camera Viewer" if show_result else None
        self.count = 0

        if camera_type == "realsense_ros":
            camera_type = "realsense"

        self.image_handler = ImageHandler(
            node=self,
            image_source=camera_type,
            config=config,
            show_result=window_name,
            image_processing_callback=self.process_frame,
            poll_interval=0.0003,
        )
        self.image_handler.run()
        self.get_logger().info(f"Started {camera_type} camera.")

    def _get_camera_config(self, camera_type: str) -> CameraConfig:
        if camera_type == "webcam":
            return OpenCVConfig(device_index=0, width=1280, height=720, fps=30)
        if camera_type == "imx219":
            return IMX219Config(sensor_id=0, width=1280, height=720, flip=2)
        if camera_type == "realsense":
            return RealSenseConfig(color_res=(1280, 720), depth_res=(1280, 720), fps=30)
        if camera_type == "realsense_ros":
            return RealSenseConfig(
                use_ros_topics=True,
                color_topic="/camera/color/image_raw",
                depth_topic="/camera/depth/image_rect_raw",
                color_compressed=True,
                depth_compressed=False,
            )
        if camera_type == "c920":
            return C920Config(profile=1)  # 1280x720
        if camera_type == "oakd":
            return OakDConfig()
        if camera_type == "ros":
            return ROSConfig(
                topic="/camera/color/image_raw/compressed", compressed=True
            )

        return None

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
