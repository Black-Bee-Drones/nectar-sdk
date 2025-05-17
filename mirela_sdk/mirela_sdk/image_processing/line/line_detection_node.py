#!/usr/bin/env python3

import sys
from typing import Dict, List, Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

import cv2
from math import isnan
import numpy as np

from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.image_processing.color.color_detector import ColorDetector, ColorSpace
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

    # Base names for topic names - will be appended with color name
    LINE_STATE_TOPIC_BASE = "line_state"
    LINE_DETECTED_TOPIC_BASE = "line_detect"

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
        - line_colors: Comma-separated list of colors to detect
        - method: The line detection method to use
        - image_source: The source of the image stream
        - show_visualization: Whether to show visualization window
        - visualization_name: Name for the visualization window
        - spaces: Comma-separated list of color spaces to use (hsv, lab)
        - cap: Webcam index to use with OpenCV
        """
        super().__init__("line_detection_node")

        # Declare standard parameters with default values
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
        # Get new parameters
        spaces = self.get_parameter("spaces").get_parameter_value().string_value
        self.color_spaces = [color_space.strip() for color_space in spaces.split(",")]

        # If there are fewer color spaces than colors, use the first color space for additional colors
        if len(self.color_spaces) < len(self.line_colors):
            # If no color spaces were provided, default to "hsv"
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

        # Determine the estimation method
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
        self.angle_values: Dict[str, float] = {}
        self.line_detected_msgs: Dict[str, Bool] = {}

        # Initialize each color detector and publishers
        for i, color in enumerate(self.line_colors):
            self.initialize_color_detector(color, self.color_spaces[i])

        # Log available methods for user reference
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

        # Set up a parameter callback to handle runtime parameter changes
        self.add_on_set_parameters_callback(self.parameters_callback)

    def initialize_color_detector(self, color: str, color_space: str):
        """
        Initialize line detector and publishers for a specific color.

        Args:
            color: The color to detect
        """
        try:
            # Initialize the line detector for this color with the specified color space
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

                # Configure text positions based on the index of the color
                color_idx = len(self.line_detectors) - 1
                text_positions = {
                    "color": (10, 30 + 100 * color_idx),
                    "angle": (25, 60 + 100 * color_idx),
                    "center_x": (25, 90 + 100 * color_idx),
                }
                self.line_detectors[color].set_text_positions(text_positions)

                # Verify color detector was initialized properly
                if self.line_detectors[color].color_detector is None:
                    self.get_logger().error(
                        f"Color detector for '{color}' was not initialized properly"
                    )
                    return

                # Verify color values were loaded correctly - use color_values instead of hsv_color
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

            # Create topics with color in the name
            line_detected_topic = f"{self.LINE_DETECTED_TOPIC_BASE}/{color}"
            line_state_topic = f"{self.LINE_STATE_TOPIC_BASE}/{color}"

            # Create publishers
            self.line_detected_msgs[color] = Bool()
            self.line_detected_pubs[color] = self.create_publisher(
                Bool, line_detected_topic, 10
            )

            self.line_state_msgs[color] = LineInfo()
            self.state_pubs[color] = self.create_publisher(
                LineInfo, line_state_topic, 10
            )

            # Initialize values
            self.center_x_values[color] = float("nan")
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
                # Handle changes to the colors list
                new_colors = [color.strip() for color in param.value.split(",")]

                # Remove detectors for colors that are no longer needed
                for color in list(self.line_detectors.keys()):
                    if color not in new_colors:
                        # Clean up publishers
                        if color in self.line_detected_pubs:
                            self.destroy_publisher(self.line_detected_pubs[color])
                            del self.line_detected_pubs[color]
                        if color in self.state_pubs:
                            self.destroy_publisher(self.state_pubs[color])
                            del self.state_pubs[color]
                        # Remove detector
                        if color in self.line_detectors:
                            del self.line_detectors[color]

                        self.get_logger().info(f"Removed detector for color: {color}")

                # Add new detectors for colors that weren't already present
                for i, color in enumerate(new_colors):
                    if color not in self.line_detectors:
                        # Use the corresponding color space if available, otherwise use the first one
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
                    # Update the estimation method for all detectors
                    for i, (color, detector) in enumerate(self.line_detectors.items()):
                        # Preserve each detector's current color space
                        current_color_space = detector.color_detector.color_space
                        self.line_detectors[color] = LineDetector(
                            color=color,
                            estimation_method=estimation_class,
                            color_space=current_color_space,
                        )
                        # Reconfigure text positions
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
                # Update the color spaces
                new_color_spaces = [cs.strip() for cs in param.value.split(",")]
                self.color_spaces = new_color_spaces

                # Re-initialize all detectors with the appropriate color spaces
                for i, color in enumerate(self.line_colors):
                    # Use the corresponding color space if available, otherwise use the first one
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

            elif param.name == "cap":
                # Update the webcam index
                self.cap = param.value
                self.get_logger().warning(
                    "Changing cap parameter requires node restart to take effect."
                )

            elif param.name == "image_source":
                # Image source changes require restarting the node or special handling
                self.get_logger().warning(
                    "Changing image_source during runtime requires node restart to take effect."
                )
                self.image_source = param.value

        return result

    def process_image(self, img: np.ndarray) -> None:
        """
        Processes a single image frame, detects lines for all colors, and publishes the detection results.

        Args:
            img (np.ndarray): The input image frame to process.
        """
        # Process the image for each color
        try:
            # Resize the image once (shared operation)
            cv2.resize(img, self.IMG_SIZE, img)

            # Create a copy for display if needed
            display_img = img.copy() if self.show_visualization else None

            # Process each color
            for color in self.line_colors:
                if color not in self.line_detectors:
                    continue

                try:
                    # Process this color
                    detector = self.line_detectors[color]

                    # Get the color for visualization
                    try:
                        bgr_color = self._get_color_bgr(color)
                    except Exception as e:
                        self.get_logger().warning(
                            f"Error getting color for {color}: {e}"
                        )
                        bgr_color = (255, 255, 255)  # Default to white

                    # Detect line on a copy of the image
                    img_copy = display_img if self.show_visualization else img.copy()

                    try:
                        # Call with color parameter for custom visualization
                        (processed_img, region, center_x, angle, confidence) = (
                            detector.detect_line(
                                img_copy,
                                region=self.DETECTION_ZONE,
                                draw=self.show_visualization,  # Draw on processed_img if visualization is enabled
                                draw_color=bgr_color,  # Pass the actual color
                            )
                        )
                    except TypeError as e:
                        # Fallback if the draw_color parameter isn't supported by the detector
                        self.get_logger().debug(
                            f"Method doesn't support draw_color, using fallback: {e}"
                        )
                        (processed_img, region, center_x, angle, confidence) = (
                            detector.detect_line(
                                img_copy,
                                region=self.DETECTION_ZONE,
                                draw=self.show_visualization,  # Draw on processed_img if visualization is enabled
                            )
                        )
                    except Exception as e:
                        self.get_logger().error(
                            f"Error in line detection for {color}: {e}"
                        )
                        # Set defaults to handle the error gracefully
                        center_x = angle = float("nan")
                        confidence = 0.0
                        processed_img = img_copy  # Just use the copy as is

                    # Store values
                    self.center_x_values[color] = center_x
                    self.angle_values[color] = angle

                    # Publish line states
                    if not isnan(center_x) and not isnan(angle):
                        self.line_state_msgs[color].center_x = float(center_x)
                        self.line_state_msgs[color].angle = float(angle)
                        self.state_pubs[color].publish(self.line_state_msgs[color])

                        self.line_detected_msgs[color].data = True
                    else:
                        self.line_detected_msgs[color].data = False

                    self.line_detected_pubs[color].publish(
                        self.line_detected_msgs[color]
                    )

                except Exception as e:
                    self.get_logger().error(f"Error processing color {color}: {e}")

            # Draw a center reference and detection zone on the display image
            if self.show_visualization and display_img is not None:
                # Draw crosshair at center of image
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

                # Draw detection zone
                zone_width, zone_height = self.DETECTION_ZONE
                zone_x1 = center_x - zone_width // 2
                zone_y1 = center_y - zone_height // 2
                zone_x2 = center_x + zone_width // 2
                zone_y2 = center_y + zone_height // 2
                cv2.rectangle(
                    display_img, (zone_x1, zone_y1), (zone_x2, zone_y2), (0, 255, 0), 1
                )

                # Add color spaces information to the image
                color_spaces_str = ", ".join(
                    [
                        f"{color}: {self.line_detectors[color].color_space.name}"
                        for color in self.line_colors
                        if color in self.line_detectors
                    ]
                )
                cv2.putText(
                    display_img,
                    f"Color Spaces: {color_spaces_str}",
                    (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

                # Update the display
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
            # Check if color_values is None or empty
            if color_values is None or len(color_values) == 0:
                return (255, 255, 255)  # Default to white

            # Make sure color_values has the expected structure
            if (
                len(color_values) == 2
                and len(color_values[0]) == 3
                and len(color_values[1]) == 3
            ):
                # Use the average of min and max values for a representative color
                min_vals = color_values[0]
                max_vals = color_values[1]

                # Use middle of the range for a representative color
                val1 = (min_vals[0] + max_vals[0]) // 2
                val2 = (min_vals[1] + max_vals[1]) // 2
                val3 = (min_vals[2] + max_vals[2]) // 2

                # Ensure val3 (brightness) is high enough to be visible
                if color_space == ColorSpace.HSV:
                    val3 = max(val3, 180)  # For HSV, val3 is V
                elif color_space == ColorSpace.LAB:
                    val1 = max(val1, 180)  # For LAB, val1 is L

                # Create a color array and convert to BGR based on color space
                if color_space == ColorSpace.HSV:
                    color_arr = np.uint8([[[val1, val2, val3]]])
                    bgr_color = cv2.cvtColor(color_arr, cv2.COLOR_HSV2BGR)[0][0]
                else:  # LAB
                    color_arr = np.uint8([[[val1, val2, val3]]])
                    bgr_color = cv2.cvtColor(color_arr, cv2.COLOR_LAB2BGR)[0][0]

                # Return as a tuple
                return (int(bgr_color[0]), int(bgr_color[1]), int(bgr_color[2]))
            else:
                self.get_logger().warning(
                    f"Unexpected color values format: {color_values}"
                )
                return (255, 255, 255)  # Default to white
        except Exception as e:
            self.get_logger().warning(f"Error converting color values to BGR: {e}")
            return (255, 255, 255)  # Default to white in case of error

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
                # Get the color values from the color detector
                detector = self.line_detectors[color_name]
                color_values = detector.color_detector.color_values
                color_space = detector.color_detector.color_space

                # Convert color_values to BGR without using it in a boolean context
                if color_values is not None:
                    return self._get_color_values_to_bgr(color_values, color_space)

            # Default colors if we can't get from detector
            color_map = {
                "red": (0, 0, 255),
                "green": (0, 255, 0),
                "blue": (255, 0, 0),
                "yellow": (0, 255, 255),
                "purple": (255, 0, 255),
                "cyan": (255, 255, 0),
                "teste": (128, 128, 128),  # Add specific color for 'teste'
            }
            return color_map.get(
                color_name.lower(), (255, 255, 255)
            )  # Default to white

        except Exception as e:
            self.get_logger().warning(
                f"Error converting color {color_name} to BGR: {e}"
            )
            return (255, 255, 255)  # Default to white in case of error

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
            show_result=None,
            cap=self.cap,
        )

        # Prepare detailed running information
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

        # Close any OpenCV windows
        if self.show_visualization:
            cv2.destroyAllWindows()

        self.destroy_node()


def main(args=None):
    """
    Main entry point for the line detection node.

    Args:
        args: Command line arguments passed to rclpy.init
    """
    # Initialize ROS with any command-line arguments
    rclpy.init(args=args)

    # Parse command line arguments to override parameters
    import argparse

    parser = argparse.ArgumentParser(description="Line Detection Node")
    parser.add_argument(
        "--line-colors", type=str, help="Comma-separated list of colors to detect"
    )
    parser.add_argument("--method", type=str, help="Line detection method")
    parser.add_argument(
        "--image-source", type=str, help="Image source (webcam, topic name, etc.)"
    )
    parser.add_argument(
        "--spaces",
        type=str,
        help="Comma-separated list of color spaces (hsv, lab) for each color",
    )
    parser.add_argument("--cap", type=int, help="Webcam index to use with OpenCV")
    parsed_args, remaining_args = parser.parse_known_args(args=args)

    # Create and run the line detection node
    detector = LineDetectionNode()

    # Override node parameters with command line arguments if provided
    if parsed_args.line_colors:
        detector.declare_parameter("line_colors", parsed_args.line_colors)
    if parsed_args.method:
        detector.declare_parameter("method", parsed_args.method)
    if parsed_args.image_source:
        detector.declare_parameter("image_source", parsed_args.image_source)
    if parsed_args.spaces:
        detector.declare_parameter("spaces", parsed_args.spaces)
    if parsed_args.cap is not None:
        detector.declare_parameter("cap", parsed_args.cap)

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
