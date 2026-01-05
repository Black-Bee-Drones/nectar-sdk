#!/usr/bin/env python3
import os
import json
import sys

import cv2
import cvzone
import numpy as np

import rclpy
from rclpy.node import Node

from mirela_sdk.vision.camera import ImageHandler
from mirela_sdk.vision.algorithms.color import ColorDetector, ColorSpace


class ClickColorCalibrationNode(Node):
    """
    Interactive color calibration node with click-based sampling.

    Combines click-to-sample color detection with trackbar-based fine-tuning.
    Click on regions to sample colors, then adjust thresholds with trackbars.

    Parameters
    ----------
    image_source : str, optional
        Camera source identifier. Default from ROS parameter.
    color_space : str, optional
        Color space to use ("hsv" or "lab"). Default is "hsv".

    Notes
    -----
    Keyboard controls:
    - 'q': Exit node
    - 'r': Reset all samples and thresholds
    - 'z': Undo last click sample
    - 's': Save current calibration to file
    - 'p': Load calibration from file
    - 'c': Switch between HSV and LAB color spaces

    Mouse controls:
    - Left click: Sample color region using flood fill
    """

    def __init__(self, image_source: str = None, color_space: str = "hsv"):
        super().__init__("click_color_calibration")

        # ROS parameters
        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("color_space", "hsv")
        self.declare_parameter("tolerance", 20)
        self.declare_parameter("coverage", 90)

        if image_source is None:
            image_source = self.get_parameter("image_source").value
        color_space_param = self.get_parameter("color_space").value
        if color_space_param:
            color_space = color_space_param

        self.tolerance = self.get_parameter("tolerance").value
        self.coverage = self.get_parameter("coverage").value

        self.color_space = (
            ColorSpace.HSV if color_space.upper() == "HSV" else ColorSpace.LAB
        )

        self.seed_points = []
        self.all_pixels = []
        self.active_mask = False

        self.color_detector = ColorDetector("track", color_space=self.color_space)
        self.trackbars_initialized = False

        self.file_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "color_calibration.json"
        )

        self.image_handler = ImageHandler(
            node=self,
            image_source=image_source,
            image_processing_callback=self._process_frame,
        )

        self.get_logger().info(
            f"Click color calibration initialized with {self.color_space.name} color space"
        )
        self.get_logger().info(
            "Controls: click=sample, r=reset, z=undo, s=save, p=load, c=switch color space, q=quit"
        )

        self.image_handler.run()

    def _mouse_callback(
        self, event: int, x: int, y: int, flags: int, param  # noqa: ARG002
    ) -> None:
        """Handle mouse click events for color sampling."""
        del flags, param  
        if event == cv2.EVENT_LBUTTONDOWN: 
            self.seed_points.append((x, y))

    def _init_windows(self) -> None:
        """Initialize OpenCV windows with trackbars and mouse callback."""
        cv2.namedWindow("Frame")
        cv2.setMouseCallback("Frame", self._mouse_callback)

        cv2.createTrackbar("Coverage %", "Frame", self.coverage, 100, lambda x: None)
        cv2.createTrackbar("Tolerance", "Frame", self.tolerance, 50, lambda x: None)

        self.color_detector.initTrackbars()
        self.trackbars_initialized = True

    def _update_threshold_from_samples(self) -> None:
        """Calculate color thresholds from sampled pixels."""
        if not self.all_pixels:
            self.active_mask = False
            self.get_logger().warn("No samples available. Mask disabled.")
            return

        combined = np.vstack(self.all_pixels)
        coverage = cv2.getTrackbarPos("Coverage %", "Frame") / 100.0

        lower = []
        upper = []
        for i in range(3):
            channel = np.sort(combined[:, i])
            n = len(channel)
            low_idx = int((1 - coverage) / 2 * n)
            high_idx = int((1 + coverage) / 2 * n) - 1
            lower.append(int(channel[low_idx]))
            upper.append(int(channel[high_idx]))

        # Update color detector with sampled values
        self.color_detector.color_values = [lower, upper]
        self._update_trackbars_from_values(lower, upper)
        self.active_mask = True

        self.get_logger().info(f"Updated thresholds: lower={lower}, upper={upper}")

    def _update_trackbars_from_values(self, lower: list, upper: list) -> None:
        """Sync trackbar positions with calculated values."""
        config = self.color_detector.color_space_config[self.color_space]
        tb_names = config["trackbar_names"]
        window_name = f"{self.color_space.name}_TrackBars"

        try:
            cv2.setTrackbarPos(tb_names[0], window_name, lower[0])
            cv2.setTrackbarPos(tb_names[1], window_name, upper[0])
            cv2.setTrackbarPos(tb_names[2], window_name, lower[1])
            cv2.setTrackbarPos(tb_names[3], window_name, upper[1])
            cv2.setTrackbarPos(tb_names[4], window_name, lower[2])
            cv2.setTrackbarPos(tb_names[5], window_name, upper[2])
        except cv2.error:
            pass

    def _process_seed_points(self, converted_img: np.ndarray) -> None:
        """Process pending seed points using flood fill."""
        tolerance = cv2.getTrackbarPos("Tolerance", "Frame")

        for point in self.seed_points:
            mask = np.zeros(
                (converted_img.shape[0] + 2, converted_img.shape[1] + 2), np.uint8
            )
            lo = (tolerance, tolerance, tolerance)
            hi = (tolerance, tolerance, tolerance)

            img_copy = converted_img.copy()
            cv2.floodFill(
                img_copy,
                mask,
                point,
                (0, 0, 0),
                lo,
                hi,
                flags=cv2.FLOODFILL_FIXED_RANGE,
            )
            mask = mask[1:-1, 1:-1]

            pixels = converted_img[mask == 1]
            if len(pixels) > 0:
                self.all_pixels.append(pixels)
                self.get_logger().debug(f"Sampled {len(pixels)} pixels at {point}")

        self.seed_points.clear()
        self._update_threshold_from_samples()

    def _process_frame(self, img: np.ndarray) -> None:
        """
        Process frame for color calibration.

        Parameters
        ----------
        img : np.ndarray
            Input BGR image from camera.
        """
        if img is None:
            return

        if not self.trackbars_initialized:
            self._init_windows()

        display = img.copy()
        config = self.color_detector.color_space_config[self.color_space]
        converted_img = cv2.cvtColor(img, config["convert_func"])

        # Process any pending click samples
        if self.seed_points:
            self._process_seed_points(converted_img)

        # Get current values from trackbars (allows manual adjustment)
        self.color_detector.color_values = self.color_detector.getTrackValues()

        # Apply color filter
        if self.color_detector.color_values is not None:
            self.color_detector.filterColor(img)
            mask = self.color_detector.mask
            result = self.color_detector.result
        else:
            mask = np.zeros(img.shape[:2], dtype=np.uint8)
            result = img.copy()

        # Display stacked view
        stacked = cvzone.stackImages([display, mask, result], 3, 0.7)
        cv2.imshow("Frame", stacked)

        self._handle_keyboard()

    def _handle_keyboard(self) -> None:
        """Handle keyboard input for controls."""
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            self._cleanup()

        elif key == ord("r"):
            self._reset()

        elif key == ord("z"):
            self._undo_last_sample()

        elif key == ord("s"):
            self._save_calibration()

        elif key == ord("p"):
            self._load_calibration()

        elif key == ord("c"):
            self._switch_color_space()

    def _reset(self) -> None:
        """Reset all samples and thresholds."""
        self.seed_points.clear()
        self.all_pixels.clear()
        self.active_mask = False
        self.get_logger().info("Reset all samples and thresholds")

    def _undo_last_sample(self) -> None:
        """Remove last sampled region."""
        if self.all_pixels:
            self.all_pixels.pop()
            self._update_threshold_from_samples()
            self.get_logger().info("Undid last sample")
        else:
            self.get_logger().warn("No samples to undo")

    def _save_calibration(self) -> None:
        """Save current calibration to JSON file."""
        values = self.color_detector.color_values
        if values is None:
            self.get_logger().error("No calibration values to save")
            return

        color_name = input("Enter color name to save: ").strip()
        if not color_name:
            self.get_logger().error("Invalid color name")
            return

        # Load existing data
        data = {}
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                self.get_logger().warn("Creating new calibration file")

        # Update with new values
        if color_name not in data:
            data[color_name] = {}

        values_list = (
            values.tolist()
            if isinstance(values, np.ndarray)
            else [list(v) for v in values]
        )
        data[color_name][self.color_space.name] = values_list

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        self.get_logger().info(
            f"Saved '{color_name}' {self.color_space.name} values to {self.file_path}"
        )

    def _load_calibration(self) -> None:
        """Load calibration from JSON file."""
        if not os.path.exists(self.file_path):
            self.get_logger().error(f"File not found: {self.file_path}")
            return

        color_name = input("Enter color name to load: ").strip()
        if not color_name:
            self.get_logger().error("Invalid color name")
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.get_logger().error("Invalid JSON file")
            return

        if color_name not in data:
            self.get_logger().error(f"Color '{color_name}' not found")
            return

        color_data = data[color_name]
        if self.color_space.name not in color_data:
            self.get_logger().error(
                f"No {self.color_space.name} values for '{color_name}'"
            )
            return

        values = color_data[self.color_space.name]
        self.color_detector.color_values = values
        self._update_trackbars_from_values(values[0], values[1])
        self.all_pixels.clear()
        self.active_mask = True

        self.get_logger().info(
            f"Loaded '{color_name}': lower={values[0]}, upper={values[1]}"
        )

    def _switch_color_space(self) -> None:
        """Switch between HSV and LAB color spaces."""
        cv2.destroyAllWindows()
        self.trackbars_initialized = False

        if self.color_space == ColorSpace.HSV:
            self.color_space = ColorSpace.LAB
        else:
            self.color_space = ColorSpace.HSV

        self.color_detector = ColorDetector("track", color_space=self.color_space)
        self.all_pixels.clear()
        self.active_mask = False

        self.get_logger().info(f"Switched to {self.color_space.name} color space")

    def _cleanup(self) -> None:
        """Clean up resources and exit."""
        self.image_handler.cleanup()
        cv2.destroyAllWindows()
        self.get_logger().info("Exiting click color calibration node")
        rclpy.shutdown()
        sys.exit(0)


def main(args=None) -> None:
    """
    Entry point for click color calibration node.

    CLI Arguments
    -------------
    --image-source : str
        Image source (webcam, topic name, etc.).
    --color-space : str
        Color space to use (hsv or lab).
    """
    rclpy.init(args=args)

    import argparse

    parser = argparse.ArgumentParser(description="Click Color Calibration Node")
    parser.add_argument(
        "--image-source",
        type=str,
        default=None,
        help="Image source (webcam, topic name, etc.)",
    )
    parser.add_argument(
        "--color-space",
        type=str,
        default="hsv",
        choices=["hsv", "lab"],
        help="Color space to use",
    )
    parsed_args, _ = parser.parse_known_args(args=args)

    node = ClickColorCalibrationNode(
        image_source=parsed_args.image_source,
        color_space=parsed_args.color_space,
    )

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
