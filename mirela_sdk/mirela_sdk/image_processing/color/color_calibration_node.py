#!/usr/bin/env python
import sys
import rclpy
from rclpy.node import Node
import cv2
import cvzone
import numpy as np

from mirela_sdk.image_processing.camera.image_handler import ImageHandler
from mirela_sdk.image_processing.color.color_detector import ColorDetector, ColorSpace


class ColorCalibrationNode(Node):
    def __init__(
        self, image_source: str = None, color_space: str = "hsv", cap: int = 0
    ):
        super().__init__("color_calibration_node")

        if image_source is None:
            self.declare_parameter("image_source", "webcam")
            image_source = self.get_parameter("image_source").value

        self.declare_parameter("color_space", "hsv")
        color_space_param = self.get_parameter("color_space").value

        # Declare cap parameter for webcam selection
        self.declare_parameter("cap", 0)
        cap_param = self.get_parameter("cap").value

        # Use parameter value if provided
        if color_space_param and not color_space:
            color_space = color_space_param

        # Use cap parameter value if provided
        if cap is None:
            cap = cap_param

        # Map string parameter to ColorSpace enum
        self.color_space = (
            ColorSpace.HSV if color_space.upper() == "HSV" else ColorSpace.LAB
        )

        self.image_source = image_source
        self.cap = cap

        self.get_logger().info(f"Using webcam index: {self.cap}")

        self.image_handler = ImageHandler(
            self,
            self.image_source,
            image_processing_callback=self.process,
            cap=self.cap,
        )
        self.color_detector = ColorDetector("track", color_space=self.color_space)
        self.initialized = False

        # Flag to track which mode we're in
        self.current_color_space = self.color_space

        self.get_logger().info(
            f"Color calibration node initialized with {self.color_space.name} color space"
        )
        self.get_logger().info(
            "Press 'q' to exit, 's' to save calibration values, or 'c' to switch color space"
        )

        self.image_handler.run()

    def process(self, img) -> None:
        """
        Process the image to calibrate the color detection

        :param img (np.array): the image to process
        """
        try:
            if img is not None:

                if not self.initialized:
                    self.color_detector.initTrackbars()
                    self.initialized = True

                self.color_detector.filterColor(img)

                # Stack the result images - original image, mask, and filtered result
                hStack = cvzone.stackImages(
                    [img, self.color_detector.mask, self.color_detector.result], 3, 0.7
                )

                # Display window title with color space information
                window_title = (
                    f"Color Calibration - {self.color_detector.color_space.name} Mode"
                )
                cv2.imshow(window_title, hStack)

                key = cv2.waitKey(1)

                if key == ord("q"):
                    self.image_handler.cleanup()
                    cv2.destroyAllWindows()
                    self.get_logger().info("Exiting color calibration node")

                elif key == ord("s"):
                    self.get_logger().info(
                        f"Saving {self.color_detector.color_space.name} color calibration values to file..."
                    )
                    self.color_detector.saveColorValues()
                    self.get_logger().info("Calibration values saved")

                elif key == ord("c"):
                    cv2.destroyAllWindows()
                    # Switch between HSV and LAB color spaces
                    if self.color_detector.color_space == ColorSpace.HSV:
                        new_color_space = ColorSpace.LAB
                    else:
                        new_color_space = ColorSpace.HSV

                    self.get_logger().info(
                        f"Switching to {new_color_space.name} color space"
                    )

                    # Create a new detector with the new color space
                    self.color_detector = ColorDetector(
                        "track", color_space=new_color_space
                    )
                    self.color_detector.initTrackbars()

        except Exception as e:
            self.get_logger().error(f"Error during image processing: {str(e)}")


def main(args=None):
    rclpy.init(args=args)

    # Add command line arguments parsing
    import argparse

    parser = argparse.ArgumentParser(description="Color Calibration Node")
    parser.add_argument(
        "--image-source",
        type=str,
        default=None,
        help="Image source (webcam, topic name, etc.)",
    )
    parser.add_argument(
        "--color-space",
        type=str,
        default=None,
        choices=["hsv", "lab"],
        help="Color space to use (hsv or lab)",
    )
    parser.add_argument(
        "--cap", type=int, default=None, help="Webcam index to use with OpenCV"
    )
    parsed_args, remaining_args = parser.parse_known_args(args=args)

    # Use the command line arguments if provided
    node = ColorCalibrationNode(
        image_source=parsed_args.image_source,
        color_space=parsed_args.color_space,
        cap=parsed_args.cap,
    )

    try:
        # Start the color calibration process
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.destroy_node()
        sys.exit(0)


if __name__ == "__main__":
    main()
