#!/usr/bin/env python3

import sys
from typing import Dict, List, Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

import cv2
from math import isnan
import numpy as np

from mirela_sdk.vision.camera import ImageHandler
from mirela_sdk.vision.algorithms.color import ColorDetector, ColorSpace
from mirela_sdk.vision.algorithms.line import (
    LineDetector,
    ILineEstimationMethod,
    RotatedRect,
    HoughLinesP,
    FitEllipse,
    RansacLine,
    AdaptiveHoughLinesP,
)
from mirela_interfaces.msg import LineInfo

from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy


class LineDetectionNode(Node):

    LINE_STATE_TOPIC_BASE = "line_state"
    LINE_DETECTED_TOPIC_BASE = "line_detect"

    # Constants for image processing
    IMG_SIZE = (640, 480)
    DETECTION_ZONE = (480, 280)

    estimation_methods: Dict[str, ILineEstimationMethod] = {
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
        - line_colors: Comma-separated list of colors to detect
        - method: The line detection method to use
        - image_source: The source of the image stream
        - show_visualization: Whether to show visualization window
        - visualization_name: Name for the visualization window
        - spaces: Comma-separated list of color spaces to use (hsv, lab)
        - cap: Webcam index to use with OpenCV
        """
        super().__init__("line_detection_node")

        self.declare_parameter("line_colors", "teste")  # multiple colors
        self.declare_parameter("method", "HoughLinesP")
        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("show_visualization", True)
        self.declare_parameter("visualization_name", "Line Detection")
        # Added new parameters
        self.declare_parameter("spaces", "hsv")  # multiple spaces
        self.declare_parameter("cap", 0)

        # Get parameters
        colors_param = (
            self.get_parameter("line_colors").get_parameter_value().string_value
        )
        self.line_colors = [color.strip() for color in colors_param.split(",")]

        self.image_source = (
            self.get_parameter("image_source").get_parameter_value().string_value
        )
        estimation_method_name = (
            self.get_parameter("method").get_parameter_value().string_value
        )
        self.show_visualization = (
            self.get_parameter("show_visualization").get_parameter_value().bool_value
        )
        self.visualization_name = (
            self.get_parameter("visualization_name").get_parameter_value().string_value
        )
        spaces = self.get_parameter("spaces").get_parameter_value().string_value
        self.color_spaces = [color_space.strip() for color_space in spaces.split(",")]

        # If there are fewer color spaces than colors, use the first color space for additional colors
        if len(self.color_spaces) < len(self.line_colors):
            # default to "hsv"
            default_space = self.color_spaces[0] if self.color_spaces else "hsv"
            additional_spaces = [default_space] * (
                len(self.line_colors) - len(self.color_spaces)
            )
            self.color_spaces.extend(additional_spaces)
            self.get_logger().warning(
                f"Fewer color spaces ({len(self.color_spaces) - len(additional_spaces)}) "
                f"than colors ({len(self.line_colors)}). "
                f"Using '{default_space}' for the additional colors."
            )

        self.cap = self.get_parameter("cap").get_parameter_value().integer_value

        if estimation_method_name in self.estimation_methods:
            self.estimation_class = self.estimation_methods[estimation_method_name]
        else:
            self.get_logger().error(
                f"Unknown estimation method '{estimation_method_name}'. Defaulting to HoughLinesP."
            )
            self.estimation_class = HoughLinesP

        # Initialize dictionaries to store detectors and publishers for each color
        self.line_detectors: Dict[str, LineDetector] = {}
        self.line_detected_pubs: Dict[str, Any] = {}
        self.state_pubs: Dict[str, Any] = {}
        self.line_state_msgs: Dict[str, LineInfo] = {}
        self.center_x_values: Dict[str, float] = {}
        self.center_y_values: Dict[str, float] = {}
        self.angle_values: Dict[str, float] = {}
        self.line_detected_msgs: Dict[str, Bool] = {}

        for i, color in enumerate(self.line_colors):
            self.initialize_color_detector(color, self.color_spaces[i])

        method_names = ", ".join(list(self.estimation_methods.keys()))
        colors_str = ", ".join(self.line_colors)
        self.get_logger().info(
            f"Line Detection Node initialized with: \
            \n - Line colors: {colors_str} \
            \n - Estimation method: {estimation_method_name} \
            \n - Image source: {self.image_source} \
            \n - Color spaces: {self.color_spaces} \
            \n - Webcam index: {self.cap} \
            \n - Show visualization: {self.show_visualization} \
            \n - Available methods: {method_names}"
        )

        self.add_on_set_parameters_callback(self.parameters_callback)

    def initialize_color_detector(self, color: str, color_space: str):
        """
        Initialize line detector and publishers for a specific color.

        Args:
            color: The color to detect
        """
        try:
            try:
                self.line_detectors[color] = LineDetector(
                    color=color,
                    estimation_method=self.estimation_class,
                    color_space=(
                        ColorSpace.HSV
                        if color_space.upper() == "HSV"
                        else ColorSpace.LAB
                    ),
                )

                color_idx = len(self.line_detectors) - 1
                text_positions = {
                    "color": (10, 30 + 100 * color_idx),
                    "angle": (25, 60 + 100 * color_idx),
                    "center_x": (25, 90 + 100 * color_idx),
                }
                self.line_detectors[color].set_text_positions(text_positions)

                if self.line_detectors[color].color_detector is None:
                    self.get_logger().error(
                        f"Color detector for '{color}' was not initialized properly"
                    )
                    return

                color_values = self.line_detectors[color].color_detector.color_values
                if color_values is None:
                    self.get_logger().warn(
                        f"Color '{color}' not found in color calibration file for {color_space} color space"
                    )
                else:
                    self.get_logger().info(
                        f"Color '{color}' {color_space} range: {color_values}"
                    )

            except Exception as e:
                self.get_logger().error(
                    f"Failed to create LineDetector for color '{color}': {e}"
                )
                return

            line_detected_topic = f"{self.LINE_DETECTED_TOPIC_BASE}/{color}"
            line_state_topic = f"{self.LINE_STATE_TOPIC_BASE}/{color}"

            self.line_detected_msgs[color] = Bool()
            self.line_detected_pubs[color] = self.create_publisher(
                Bool, line_detected_topic, 10
            )

            self.line_state_msgs[color] = LineInfo()
            self.state_pubs[color] = self.create_publisher(
                LineInfo, line_state_topic, 10
            )

            self.center_x_values[color] = float("nan")
            self.center_y_values[color] = float("nan")
            self.angle_values[color] = float("nan")

            self.get_logger().info(f"Initialized detector for color: {color}")
            self.get_logger().info(
                f"Publishing to: {line_detected_topic} and {line_state_topic}"
            )

        except Exception as e:
            self.get_logger().error(
                f"Failed to initialize detector for color {color}: {e}"
            )

    def parameters_callback(self, params):
        """
        Callback for parameter changes at runtime.

        Args:
            params: The parameters that were changed.

        Returns:
            SetParametersResult indicating success or failure.
        """
        from rclpy.parameter_service import SetParametersResult

        result = SetParametersResult()
        result.successful = True
        result.reason = ""

        for param in params:
            if param.name == "line_colors":
                new_colors = [color.strip() for color in param.value.split(",")]

                # Remove detectors for colors that are no longer needed
                for color in list(self.line_detectors.keys()):
                    if color not in new_colors:
                        if color in self.line_detected_pubs:
                            self.destroy_publisher(self.line_detected_pubs[color])
                            del self.line_detected_pubs[color]
                        if color in self.state_pubs:
                            self.destroy_publisher(self.state_pubs[color])
                            del self.state_pubs[color]
                        if color in self.line_detectors:
                            del self.line_detectors[color]

                        self.get_logger().info(f"Removed detector for color: {color}")

                # Add new detectors for colors that weren't already present
                for i, color in enumerate(new_colors):
                    if color not in self.line_detectors:
                        color_space_idx = (
                            min(i, len(self.color_spaces) - 1)
                            if self.color_spaces
                            else 0
                        )
                        color_space = (
                            self.color_spaces[color_space_idx]
                            if self.color_spaces
                            else "hsv"
                        )
                        self.initialize_color_detector(color, color_space)

                self.line_colors = new_colors
                self.get_logger().info(
                    f"Updated colors to: {', '.join(self.line_colors)}"
                )

            elif param.name == "method":
                if param.value in self.estimation_methods:
                    estimation_class = self.estimation_methods[param.value]

                    for i, (color, detector) in enumerate(self.line_detectors.items()):
                        current_color_space = detector.color_detector.color_space
                        self.line_detectors[color] = LineDetector(
                            color=color,
                            estimation_method=estimation_class,
                            color_space=current_color_space,
                        )

                        color_idx = list(self.line_detectors.keys()).index(color)
                        text_positions = {
                            "color": (10, 30 + 100 * color_idx),
                            "angle": (25, 60 + 100 * color_idx),
                            "center_x": (25, 90 + 100 * color_idx),
                        }
                        self.line_detectors[color].set_text_positions(text_positions)
                    self.estimation_class = estimation_class
                    self.get_logger().info(
                        f"Changed estimation method to {param.value} for all detectors"
                    )
                else:
                    result.successful = False
                    result.reason = f"Unknown estimation method: {param.value}"

            elif param.name == "spaces":
                new_color_spaces = [cs.strip() for cs in param.value.split(",")]
                self.color_spaces = new_color_spaces

                # Re-initialize all detectors with the appropriate color spaces
                for i, color in enumerate(self.line_colors):
                    color_space = (
                        self.color_spaces[i]
                        if i < len(self.color_spaces)
                        else self.color_spaces[0]
                    )
                    try:
                        color_space_enum = (
                            ColorSpace.HSV
                            if color_space.upper() == "HSV"
                            else ColorSpace.LAB
                        )
                        self.line_detectors[color] = LineDetector(
                            color=color,
                            estimation_method=self.estimation_class,
                            color_space=color_space_enum,
                        )
                        color_idx = list(self.line_detectors.keys()).index(color)
                        text_positions = {
                            "color": (10, 30 + 100 * color_idx),
                            "angle": (25, 60 + 100 * color_idx),
                            "center_x": (25, 90 + 100 * color_idx),
                        }
                        self.line_detectors[color].set_text_positions(text_positions)
                    except Exception as e:
                        self.get_logger().error(
                            f"Failed to update detector for color '{color}' to {color_space}: {e}"
                        )
                self.get_logger().info(
                    f"Changed color spaces to {', '.join(self.color_spaces)}"
                )

        return result

    def process_image(self, img: np.ndarray) -> None:
        """
        Processes a single image frame, detects lines for all colors, and publishes the detection results.

        Args:
            img (np.ndarray): The input image frame to process.
        """
        try:
            cv2.resize(img, self.IMG_SIZE, img)
            display_img = img.copy() if self.show_visualization else None

            for color in self.line_colors:
                if color not in self.line_detectors:
                    continue

                try:
                    detector = self.line_detectors[color]

                    try:
                        bgr_color = self._get_color_bgr(color)
                    except Exception as e:
                        self.get_logger().warning(
                            f"Error getting color for {color}: {e}"
                        )
                        bgr_color = (255, 255, 255)

                    img_copy = display_img if self.show_visualization else img.copy()

                    try:
                        (
                            processed_img,
                            region,
                            center_x,
                            center_y,
                            angle,
                            width,
                            height,
                        ) = detector.detect_line(
                            img_copy,
                            region=self.DETECTION_ZONE,
                            draw=self.show_visualization,
                            draw_color=bgr_color,
                        )
                    except TypeError as e:
                        self.get_logger().debug(
                            f"Method doesn't support draw_color, using fallback: {e}"
                        )
                        (
                            processed_img,
                            region,
                            center_x,
                            center_y,
                            angle,
                            width,
                            height,
                        ) = detector.detect_line(
                            img_copy,
                            region=self.DETECTION_ZONE,
                            draw=self.show_visualization,
                        )
                    except Exception as e:
                        self.get_logger().error(
                            f"Error in line detection for {color}: {e}"
                        )
                        center_x = center_y = angle = width = height = float("nan")

                    self.center_x_values[color] = center_x
                    self.center_y_values[color] = center_y
                    self.angle_values[color] = angle

                    if not isnan(center_x) and not isnan(center_y) and not isnan(angle):
                        self.line_state_msgs[color].center_x = float(center_x)
                        self.line_state_msgs[color].center_y = float(center_y)
                        self.line_state_msgs[color].angle = float(angle)
                        self.line_state_msgs[color].width = float(width)
                        self.line_state_msgs[color].height = float(height)
                        self.state_pubs[color].publish(self.line_state_msgs[color])
                        self.line_detected_msgs[color].data = True
                    else:
                        self.line_detected_msgs[color].data = False

                    self.line_detected_pubs[color].publish(
                        self.line_detected_msgs[color]
                    )

                except Exception as e:
                    self.get_logger().error(f"Error processing color {color}: {e}")

            if self.show_visualization and display_img is not None:
                center_x, center_y = self.IMG_SIZE[0] // 2, self.IMG_SIZE[1] // 2
                cv2.line(
                    display_img,
                    (center_x - 10, center_y),
                    (center_x + 10, center_y),
                    (0, 255, 0),
                    1,
                )
                cv2.line(
                    display_img,
                    (center_x, center_y - 10),
                    (center_x, center_y + 10),
                    (0, 255, 0),
                    1,
                )

                zone_width, zone_height = self.DETECTION_ZONE
                zone_x1 = center_x - zone_width // 2
                zone_y1 = center_y - zone_height // 2
                zone_x2 = center_x + zone_width // 2
                zone_y2 = center_y + zone_height // 2
                cv2.rectangle(
                    display_img, (zone_x1, zone_y1), (zone_x2, zone_y2), (0, 255, 0), 1
                )

                if self.show_visualization:
                    cv2.imshow(self.visualization_name, display_img)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cv2.destroyWindow(self.visualization_name)
                    self.image_handler.cleanup()

        except Exception as e:
            self.get_logger().error(f"Error in line detection: {e}")

    def _get_color_values_to_bgr(self, color_values, color_space):
        """
        Convert color values to BGR based on the provided color space.

        Args:
            color_values: Color values as [[min1, min2, min3], [max1, max2, max3]]
            color_space: The color space (ColorSpace.HSV or ColorSpace.LAB)

        Returns:
            tuple: BGR color tuple
        """
        try:
            if color_values is None or len(color_values) == 0:
                return (255, 255, 255)

            if (
                len(color_values) == 2
                and len(color_values[0]) == 3
                and len(color_values[1]) == 3
            ):
                # Use the average of min and max values for a representative color
                min_vals = color_values[0]
                max_vals = color_values[1]

                val1 = (min_vals[0] + max_vals[0]) // 2
                val2 = (min_vals[1] + max_vals[1]) // 2
                val3 = (min_vals[2] + max_vals[2]) // 2

                # Ensure val3 (brightness) is high enough to be visible
                if color_space == ColorSpace.HSV:
                    val3 = max(val3, 180)
                elif color_space == ColorSpace.LAB:
                    val1 = max(val1, 180)

                if color_space == ColorSpace.HSV:
                    color_arr = np.uint8([[[val1, val2, val3]]])
                    bgr_color = cv2.cvtColor(color_arr, cv2.COLOR_HSV2BGR)[0][0]
                else:  # LAB
                    color_arr = np.uint8([[[val1, val2, val3]]])
                    bgr_color = cv2.cvtColor(color_arr, cv2.COLOR_LAB2BGR)[0][0]

                return (int(bgr_color[0]), int(bgr_color[1]), int(bgr_color[2]))
            else:
                self.get_logger().warning(
                    f"Unexpected color values format: {color_values}"
                )
                return (255, 255, 255)  # Default to white
        except Exception as e:
            self.get_logger().warning(f"Error converting color values to BGR: {e}")
            return (255, 255, 255)

    def _get_color_bgr(self, color_name):
        """
        Helper to convert color name to BGR values for display by extracting the actual color
        from the corresponding line detector's ColorDetector.

        Args:
            color_name (str): The name of the color to get the BGR value for

        Returns:
            tuple: BGR color tuple for use with OpenCV
        """
        try:
            if color_name in self.line_detectors:
                detector = self.line_detectors[color_name]
                color_values = detector.color_detector.color_values
                color_space = detector.color_detector.color_space

                if color_values is not None:
                    return self._get_color_values_to_bgr(color_values, color_space)

            color_map = {
                "red": (0, 0, 255),
                "green": (0, 255, 0),
                "blue": (255, 0, 0),
                "yellow": (0, 255, 255),
                "purple": (255, 0, 255),
                "cyan": (255, 255, 0),
                "teste": (128, 128, 128),
            }
            return color_map.get(color_name.lower(), (255, 255, 255))

        except Exception as e:
            self.get_logger().warning(
                f"Error converting color {color_name} to BGR: {e}"
            )
            return (255, 255, 255)

    def run(self):
        """
        Run the line detection node.

        Uses the ROS parameters to determine if visualization should be shown.
        """
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.image_handler = ImageHandler(
            self,
            self.image_source,
            self.process_image,
            show_result=None,
            cap=self.cap,
        )

        colors_str = ", ".join(self.line_colors)
        spaces_str = ", ".join(self.color_spaces)
        color_space_info = ", ".join(
            [
                f"{color}: {space}"
                for color, space in zip(
                    self.line_colors,
                    self.color_spaces[: len(self.line_colors)]
                    + [self.color_spaces[0]]
                    * (len(self.line_colors) - len(self.color_spaces)),
                )
            ]
        )

        self.get_logger().info(
            f"\nDetection Node running: {colors_str}, {self.image_source}, {spaces_str}, cap={self.cap}"
        )

        self.image_handler.run()

    def cleanup(self):
        """
        Cleans up resources and shuts down the node.

        Stops the image handler and destroys the ROS node.
        """
        self.image_handler.cleanup()

        if self.show_visualization:
            cv2.destroyAllWindows()

        self.destroy_node()


def main(args=None):
    """
    Main entry point for the line detection node.

    Args:
        args: Command line arguments passed to rclpy.init
    """
    rclpy.init(args=args)

    detector = LineDetectionNode()

    detector.run()

    try:
        rclpy.spin(detector)
    except KeyboardInterrupt:
        detector.cleanup()
        rclpy.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
