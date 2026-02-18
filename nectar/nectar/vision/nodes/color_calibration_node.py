#!/usr/bin/env python3
import sys

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.algorithms.color import ColorDetector, ColorSpace
from nectar.vision.camera import ImageHandler


class ColorCalibrationNode(Node):
    """
    Interactive color calibration node with trackbar interface.

    Parameters
    ----------
    image_source : str, optional
        Camera source identifier. Default from ROS parameter.
    color_space : str, optional
        Initial color space ("hsv" or "lab").
    cap : int, optional
        Webcam index for OpenCV capture.

    Notes
    -----
    Keyboard controls:
    - 'q': Exit node
    - 's': Save current calibration values
    - 'c': Switch between HSV and LAB color spaces
    """

    def __init__(self, image_source: str = None, color_space: str = "hsv", cap: int = 0):
        super().__init__("color_calibration_node")

        if image_source is None:
            self.declare_parameter("image_source", "webcam")
            image_source = self.get_parameter("image_source").value

        self.declare_parameter("color_space", "hsv")
        color_space_param = self.get_parameter("color_space").value

        self.declare_parameter("cap", 0)
        cap_param = self.get_parameter("cap").value

        if color_space_param and not color_space:
            color_space = color_space_param

        if cap is None:
            cap = cap_param

        self.color_space = ColorSpace.HSV if color_space.upper() == "HSV" else ColorSpace.LAB

        self.image_source = image_source
        self.cap = cap

        self.get_logger().info(f"Using webcam index: {self.cap}")

        self.image_handler = ImageHandler(
            node=self,
            image_source=self.image_source,
            image_processing_callback=self.process,
        )
        self.color_detector = ColorDetector("track", color_space=self.color_space)
        self.initialized = False

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
        Process frame for color calibration display.

        Parameters
        ----------
        img : np.ndarray
            Input BGR image from camera.

        Notes
        -----
        Displays stacked view of original, mask, and filtered images.
        Handles keyboard input for save, exit, and color space switching.
        """
        try:
            if img is not None:
                if not self.initialized:
                    self.color_detector.initTrackbars()
                    self.initialized = True

                self.color_detector.filterColor(img)

                mask_bgr = (
                    cv2.cvtColor(self.color_detector.mask, cv2.COLOR_GRAY2BGR)
                    if len(self.color_detector.mask.shape) == 2
                    else self.color_detector.mask
                )
                hStack = np.hstack([img, mask_bgr, self.color_detector.result])
                hStack = cv2.resize(hStack, None, fx=0.7, fy=0.7)

                window_title = f"Color Calibration - {self.color_detector.color_space.name} Mode"
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
                    if self.color_detector.color_space == ColorSpace.HSV:
                        new_color_space = ColorSpace.LAB
                    else:
                        new_color_space = ColorSpace.HSV

                    self.get_logger().info(f"Switching to {new_color_space.name} color space")

                    self.color_detector = ColorDetector("track", color_space=new_color_space)
                    self.color_detector.initTrackbars()

        except Exception as e:
            self.get_logger().error(f"Error during image processing: {str(e)}")


def main(args=None):
    """
    Entry point for color calibration node.

    CLI Arguments
    -------------
    --image-source : str
        Image source (webcam, topic name, etc.).
    --color-space : str
        Color space to use (hsv or lab).
    --cap : int
        Webcam index for OpenCV.
    """
    rclpy.init(args=args)

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
    parser.add_argument("--cap", type=int, default=None, help="Webcam index to use with OpenCV")
    parsed_args, remaining_args = parser.parse_known_args(args=args)

    node = ColorCalibrationNode(
        image_source=parsed_args.image_source,
        color_space=parsed_args.color_space,
        cap=parsed_args.cap,
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.destroy_node()
        sys.exit(0)


if __name__ == "__main__":
    main()
