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
    RansacLine,
    AdaptiveHoughLinesP,
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
        "RansacLine": RansacLine,
        "AdaptiveHoughLinesP": AdaptiveHoughLinesP,
    }

    def __init__(self):
        """
        A ROS2 node for detecting lines in images using various estimation methods.

        This node processes images from a specified source, detects lines based on the configured estimation method,
        and publishes the line's state (e.g., center and angle) to ROS topics. It supports different line detection
        methods, such as RotatedRect, HoughLinesP, FitEllipse, RansacLine, and AdaptiveHoughLinesP.

        All configuration is handled through ROS parameters:
        - line_color: The color of the line to detect
        - method: The line detection method to use
        - image_source: The source of the image stream
        - show_visualization: Whether to show visualization window
        - visualization_name: Name for the visualization window
        """
        super().__init__("line_detection_node")

        # Declare standard parameters with default values
        self.declare_parameter("line_color", "green")
        self.declare_parameter("method", "HoughLinesP")
        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("show_visualization", True)
        self.declare_parameter("visualization_name", "Line Detection")

        # Get parameters
        self.line_color = (
            self.get_parameter("line_color").get_parameter_value().string_value
        )
        self.image_source = (
            self.get_parameter("image_source").get_parameter_value().string_value
        )
        estimation_method = (
            self.get_parameter("method").get_parameter_value().string_value
        )
        self.show_visualization = (
            self.get_parameter("show_visualization").get_parameter_value().bool_value
        )
        self.visualization_name = (
            self.get_parameter("visualization_name").get_parameter_value().string_value
        )

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

        # Log available methods for user reference
        method_names = ", ".join(list(self.estimation_methods.keys()))
        self.get_logger().info(
            f"Line Detection Node initialized with: \
            \n - Line color: {self.line_color} \
            \n - Estimation method: {estimation_method} \
            \n - Image source: {self.image_source} \
            \n - Show visualization: {self.show_visualization} \
            \n - Available methods: {method_names}"
        )

        # Set up a parameter callback to handle runtime parameter changes
        self.add_on_set_parameters_callback(self.parameters_callback)

    def parameters_callback(self, params):
        """
        Callback for parameter changes at runtime.

        Args:
            params: The parameters that were changed.

        Returns:
            SetParametersResult indicating success or failure.
        """
        from rclpy.parameter import SetParametersResult

        result = SetParametersResult()
        result.successful = True
        result.reason = ""

        for param in params:
            if param.name == "line_color":
                self.line_color = param.value
                # Recreate the line detector with the new color
                self.line_detector = LineDetector(
                    color=self.line_color,
                    estimation_method=self.line_detector.estimation_method.__class__,
                )
                self.get_logger().info(f"Changed line color to {self.line_color}")
            elif param.name == "method":
                if param.value in self.estimation_methods:
                    estimation_class = self.estimation_methods[param.value]
                    # Recreate the line detector with the new method
                    self.line_detector = LineDetector(
                        color=self.line_color, estimation_method=estimation_class
                    )
                    self.get_logger().info(
                        f"Changed estimation method to {param.value}"
                    )
                else:
                    result.successful = False
                    result.reason = f"Unknown estimation method: {param.value}"
            elif param.name == "image_source":
                # Image source changes require restarting the node or special handling
                self.get_logger().warning(
                    "Changing image_source during runtime requires node restart to take effect."
                )
                self.image_source = param.value

        return result

    def process_image(self, img: np.ndarray) -> None:
        """
        Processes a single image frame, detects lines, and publishes the detection results.

        Args:
            img (np.ndarray): The input image frame to process.
        """
        # Process the image and perform line detection
        try:
            cv2.resize(img, self.IMG_SIZE, img)
            (img, region, self.center_x, self.angle, confidence) = (
                self.line_detector.detect_line(img, region=self.DETECTION_ZONE)
            )

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

    def run(self):
        """
        Run the line detection node.

        Uses the ROS parameters to determine if visualization should be shown.
        """
        visualization_window = (
            self.visualization_name if self.show_visualization else None
        )

        self.image_handler = ImageHandler(
            self,
            self.image_source,
            self.process_image,
            show_result=visualization_window,
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
    """
    Main entry point for the line detection node.

    Args:
        args: Command line arguments passed to rclpy.init
    """
    # Initialize ROS with any command-line arguments (but we'll use ROS parameters, not argparse)
    rclpy.init(args=args)

    # Create and run the line detection node
    detector = LineDetectionNode()
    detector.run()

    try:
        # Start the line detection
        rclpy.spin(detector)
    except KeyboardInterrupt:
        # Clean up resources before shutdown
        detector.cleanup()
        rclpy.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
