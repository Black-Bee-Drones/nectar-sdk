#!/usr/bin/env python3

import sys

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

import cv2
from math import isnan
import numpy as np

from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.image_processing.line import (
    LineDetector,
    ILineEstimationMethod,
    RotatedRect,
    HoughLinesP,
    FitEllipse,
)
from mirela_interfaces.msg import LineInfo


class LineDetectionNode(Node):

    # Constants for topic names
    LINE_STATE_TOPIC = "line_state"
    LINE_DETECTED_TOPIC = "line_detect"

    # Constants for image processing
    IMG_SIZE = (640, 480)
    DETECTION_ZONE = (640, 200)

    estimation_methods = {
        "RotatedRect": RotatedRect,
        "HoughLinesP": HoughLinesP,
        "FitEllipse": FitEllipse,
    }

    def __init__(
        self,
        line_color: str = None,
        estimation_method: str = "HoughLinesP",
        image_source: str = None,
    ):
        """
        A ROS2 node for detecting lines in images using various estimation methods.

        This node processes images from a specified source, detects lines based on the configured estimation method,
        and publishes the line's state (e.g., center and angle) to ROS topics. It supports different line detection
        methods, such as RotatedRect, HoughLinesP, and FitEllipse.

        Args:
            line_color (str, optional): The color of the line to detect. Defaults to None, which uses the ROS parameter "line_color".
            estimation_method (str, optional): The line detection method to use ("RotatedRect", "HoughLinesP", or "FitEllipse").
                                               Defaults to "HoughLinesP".
            image_source (str, optional): The source of the image stream (e.g., "webcam"). Defaults to None, which uses the ROS parameter "image_source".
        """
        super().__init__("line_detection_node")

        self.declare_parameter("line_color", "line")
        self.declare_parameter("method", "HoughLinesP")
        self.declare_parameter("image_source", "webcam")

        # Get detection parameters (line_color and image_source) from the command line
        if line_color is None:
            line_color = (
                self.get_parameter("line_color").get_parameter_value().string_value
            )

        if image_source is None:
            image_source = (
                self.get_parameter("image_source").get_parameter_value().string_value
            )

        if estimation_method is None:
            estimation_method = (
                self.get_parameter("method").get_parameter_value().string_value
            )

        self.line_color: str = line_color
        self.image_source: str = image_source

        # Determine the estimation method
        if estimation_method in self.estimation_methods:
            estimation_class = self.estimation_methods[estimation_method]
        else:
            self.get_logger().error(
                f"Unknown estimation method '{estimation_method}'. Defaulting to HoughLinesP."
            )
            estimation_class = HoughLinesP

        # Initialize the line detector
        self.line_detector = LineDetector(
            color=self.line_color, estimation_method=estimation_class
        )

        self.line_detected = Bool()
        self.line_detected_pub = self.create_publisher(
            Bool, self.LINE_DETECTED_TOPIC, 10
        )

        self.line_state_msg = LineInfo()
        self.center_x = self.angle = float()
        self.state_pub = self.create_publisher(LineInfo, self.LINE_STATE_TOPIC, 10)

        self.get_logger().info(
            f"Line Detection Node initialized with: \
            \n - Line color: {self.line_color} \
            \n - Estimation method: {estimation_method} \
            \n - Image source: {self.image_source}"
        )

    def process_image(self, img: np.ndarray) -> None:
        """
        Processes a single image frame, detects lines, and publishes the detection results.

        Args:
            img (np.ndarray): The input image frame to process.
        """
        # Process the image and perform line detection
        try:
            cv2.resize(img, self.IMG_SIZE, img)
            (
                img,
                region,
                self.center_x,
                self.angle,
            ) = self.line_detector.detect_line(img, region=self.DETECTION_ZONE)

            # Publish line states
            if not isnan(self.center_x) and not isnan(self.angle):
                self.line_state_msg.center_x = float(self.center_x)
                self.line_state_msg.angle = float(self.angle)
                self.state_pub.publish(self.line_state_msg)

                self.line_detected.data = True
            else:
                self.line_detected.data = False

            self.line_detected_pub.publish(self.line_detected)

            cv2.circle(
                img,
                (self.IMG_SIZE[0] // 2, self.IMG_SIZE[1] // 2),
                2,
                (0, 255, 0),
                3,
            )

        except Exception as e:
            self.get_logger().error(f"Error in line detection: {e}")

    def run(self, show: str = None):
        """
        Run the line detection node.

        Args:
            show (str, optional): The window name to show the processed image. Defaults to None.
        """
        self.image_handler = ImageHandler(
            self,
            self.image_source,
            self.process_image,
            show_result=show,
        )
        self.get_logger().info(
            f"\nDetection Node init: {self.line_color}, {self.image_source}"
        )

        self.image_handler.run()

    def cleanup(self):
        """
        Cleans up resources and shuts down the node.

        Stops the image handler and destroys the ROS node.
        """
        self.image_handler.cleanup()
        self.destroy_node()


def main(args=None):
    rclpy.init(args=args)

    detector = LineDetectionNode(
        line_color="teste", estimation_method="RotatedRect", image_source="webcam"
    )
    detector.run(show="Line Detection")

    try:
        # Start the line detection
        rclpy.spin(detector)
    except KeyboardInterrupt:
        # Clean up resources before shutdown
        detector.cleanup()
        detector.destroy_node()
        sys.exit(0)


if __name__ == "__main__":
    main()
