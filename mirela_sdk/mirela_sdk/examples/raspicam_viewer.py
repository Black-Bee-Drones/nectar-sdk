import rclpy
from rclpy.node import Node

from mirela_sdk.image_processing.camera.image_handler import ImageHandler


class RaspicamViewer(Node):
    def __init__(self) -> None:
        super().__init__("raspicam_test_node")
        self.image_handler = ImageHandler(
            node=self, image_source="/image_raw", show_result="Raspicam Viewer"
        )
        self.image_handler.run()


def main(args=None) -> None:
    rclpy.init()

    test = RaspicamViewer()

    rclpy.spin(test)

    rclpy.shutdown()
