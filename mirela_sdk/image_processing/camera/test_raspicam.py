import rclpy
from rclpy.node import Node

import cv2

from mirela_sdk.image_processing.camera.image_handler import ImageHandler

class TestRaspicam(Node):
    def __init__(self) -> None:
        super().__init__("raspicam_test_node")
        self.image_handler = ImageHandler(node=self, image_source='/image_raw', image_processing_callback=lambda img: cv2.imshow('Raspicam', img))
    
    def run(self) -> None:
        self.image_handler.run()

def main(args=None) -> None:
    rclpy.init()

    test = TestRaspicam()
    test.run()

    rclpy.spin(test)

    rclpy.shutdown()