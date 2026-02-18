#!/usr/bin/env python3
import json
import os
import sys
from typing import List, Optional

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.algorithms.color import ColorSpace
from nectar.vision.camera import ImageHandler


class ClickColorCalibrationNode(Node):
    """
    Interactive color calibration with click-based sampling.

    Click on colored regions to sample pixels and automatically compute
    HSV/LAB thresholds. Trackbars allow fine-tuning of calculated values.

    Parameters
    ----------
    image_source : str, optional
        Camera source identifier.
    color_space : str, optional
        Color space ("hsv" or "lab").

    Notes
    -----
    Mouse: Left-click to sample color region
    Keys: q=quit, r=reset, z=undo, s=save, l=load, c=switch color space
    """

    TRACKBAR_CONFIG = {
        ColorSpace.HSV: {
            "convert": cv2.COLOR_BGR2HSV,
            "names": ["H min", "H max", "S min", "S max", "V min", "V max"],
            "max": [179, 179, 255, 255, 255, 255],
            "init": [0, 179, 0, 255, 0, 255],
        },
        ColorSpace.LAB: {
            "convert": cv2.COLOR_BGR2LAB,
            "names": ["L min", "L max", "A min", "A max", "B min", "B max"],
            "max": [255, 255, 255, 255, 255, 255],
            "init": [0, 255, 0, 255, 0, 255],
        },
    }

    def __init__(self, image_source: str = None, color_space: str = "hsv"):
        super().__init__("click_color_calibration")

        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("color_space", "hsv")
        self.declare_parameter("flood_tolerance", 15)

        if image_source is None:
            image_source = self.get_parameter("image_source").value
        cs_param = self.get_parameter("color_space").value
        if cs_param:
            color_space = cs_param

        self.flood_tolerance = self.get_parameter("flood_tolerance").value
        self.color_space = ColorSpace.HSV if color_space.upper() == "HSV" else ColorSpace.LAB
        self.config = self.TRACKBAR_CONFIG[self.color_space]

        self.sampled_pixels: List[np.ndarray] = []
        self.pending_clicks: List[tuple] = []
        self.lower = np.array(self.config["init"][::2])
        self.upper = np.array(self.config["init"][1::2])

        self.file_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "color_calibration.json"
        )
        self.window_initialized = False

        self.image_handler = ImageHandler(
            node=self,
            image_source=image_source,
            image_processing_callback=self._process,
        )

        self.get_logger().info(f"Click calibration: {self.color_space.name} mode")
        self.get_logger().info("Click to sample | r=reset z=undo s=save l=load c=switch q=quit")
        self.image_handler.run()

    def _mouse_cb(self, event: int, x: int, y: int, flags: int, param) -> None:
        del flags, param
        if event == cv2.EVENT_LBUTTONDOWN:
            self.pending_clicks.append((x, y))

    def _init_window(self) -> None:
        cv2.namedWindow("Calibration")
        cv2.setMouseCallback("Calibration", self._mouse_cb)

        cv2.createTrackbar("Tolerance", "Calibration", self.flood_tolerance, 50, lambda x: None)

        for i, name in enumerate(self.config["names"]):
            init_val = self.config["init"][i]
            cv2.createTrackbar(name, "Calibration", init_val, self.config["max"][i], lambda x: None)

        self.window_initialized = True

    def _get_trackbar_values(self) -> tuple:
        names = self.config["names"]
        lower = np.array(
            [
                cv2.getTrackbarPos(names[0], "Calibration"),
                cv2.getTrackbarPos(names[2], "Calibration"),
                cv2.getTrackbarPos(names[4], "Calibration"),
            ],
            dtype=np.uint8,
        )
        upper = np.array(
            [
                cv2.getTrackbarPos(names[1], "Calibration"),
                cv2.getTrackbarPos(names[3], "Calibration"),
                cv2.getTrackbarPos(names[5], "Calibration"),
            ],
            dtype=np.uint8,
        )
        return lower, upper

    def _set_trackbar_values(self, lower: np.ndarray, upper: np.ndarray) -> None:
        names = self.config["names"]
        try:
            cv2.setTrackbarPos(names[0], "Calibration", int(lower[0]))
            cv2.setTrackbarPos(names[1], "Calibration", int(upper[0]))
            cv2.setTrackbarPos(names[2], "Calibration", int(lower[1]))
            cv2.setTrackbarPos(names[3], "Calibration", int(upper[1]))
            cv2.setTrackbarPos(names[4], "Calibration", int(lower[2]))
            cv2.setTrackbarPos(names[5], "Calibration", int(upper[2]))
        except cv2.error:
            pass

    def _sample_region(self, img_converted: np.ndarray, point: tuple) -> Optional[np.ndarray]:
        """Sample pixels around click point using flood fill."""
        h, w = img_converted.shape[:2]
        x, y = point
        if not (0 <= x < w and 0 <= y < h):
            return None

        tol = cv2.getTrackbarPos("Tolerance", "Calibration")
        mask = np.zeros((h + 2, w + 2), np.uint8)

        cv2.floodFill(
            img_converted.copy(),
            mask,
            (x, y),
            255,
            (tol, tol, tol),
            (tol, tol, tol),
            cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE,
        )

        region_mask = mask[1:-1, 1:-1]
        pixels = img_converted[region_mask == 1]

        if len(pixels) == 0:
            return None

        return pixels

    def _compute_bounds(self) -> None:
        """Compute lower/upper bounds from all sampled pixels."""
        if not self.sampled_pixels:
            return

        all_pixels = np.vstack(self.sampled_pixels)

        margins = [5, 15, 15] if self.color_space == ColorSpace.HSV else [10, 10, 10]
        maxes = self.config["max"][1::2]

        lower = []
        upper = []
        for ch in range(3):
            ch_data = all_pixels[:, ch]
            lo = max(0, int(np.percentile(ch_data, 2)) - margins[ch])
            hi = min(maxes[ch], int(np.percentile(ch_data, 98)) + margins[ch])
            lower.append(lo)
            upper.append(hi)

        self.lower = np.array(lower, dtype=np.uint8)
        self.upper = np.array(upper, dtype=np.uint8)
        self._set_trackbar_values(self.lower, self.upper)

        self.get_logger().info(f"Bounds: {self.lower.tolist()} - {self.upper.tolist()}")

    def _process(self, img: np.ndarray) -> None:
        if img is None:
            return

        if not self.window_initialized:
            self._init_window()

        converted = cv2.cvtColor(img, self.config["convert"])

        for click in self.pending_clicks:
            pixels = self._sample_region(converted, click)
            if pixels is not None and len(pixels) > 10:
                self.sampled_pixels.append(pixels)
                self._compute_bounds()
                self.get_logger().debug(f"Sampled {len(pixels)} pixels at {click}")
        self.pending_clicks.clear()

        self.lower, self.upper = self._get_trackbar_values()

        mask = cv2.inRange(converted, self.lower, self.upper)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        result = cv2.bitwise_and(img, img, mask=mask)

        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        display = np.hstack([img, mask_bgr, result])

        info = f"{self.color_space.name} | Samples: {len(self.sampled_pixels)}"
        cv2.putText(display, info, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(
            display,
            f"L: {self.lower.tolist()} U: {self.upper.tolist()}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
        )

        cv2.imshow("Calibration", display)
        self._handle_keys()

    def _handle_keys(self) -> None:
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            self._cleanup()
        elif key == ord("r"):
            self._reset()
        elif key == ord("z"):
            self._undo()
        elif key == ord("s"):
            self._save()
        elif key == ord("l"):
            self._load()
        elif key == ord("c"):
            self._switch_color_space()

    def _reset(self) -> None:
        self.sampled_pixels.clear()
        self.lower = np.array(self.config["init"][::2])
        self.upper = np.array(self.config["init"][1::2])
        self._set_trackbar_values(self.lower, self.upper)
        self.get_logger().info("Reset")

    def _undo(self) -> None:
        if self.sampled_pixels:
            self.sampled_pixels.pop()
            if self.sampled_pixels:
                self._compute_bounds()
            else:
                self._reset()
            self.get_logger().info(f"Undo - {len(self.sampled_pixels)} samples remain")

    def _save(self) -> None:
        color_name = input("Color name: ").strip()
        if not color_name:
            return

        data = {}
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        if color_name not in data:
            data[color_name] = {}

        data[color_name][self.color_space.name] = [
            self.lower.tolist(),
            self.upper.tolist(),
        ]

        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        self.get_logger().info(f"Saved '{color_name}' to {self.file_path}")

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            self.get_logger().error("No calibration file")
            return

        color_name = input("Color name: ").strip()
        if not color_name:
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.get_logger().error(f"Load error: {e}")
            return

        if color_name not in data or self.color_space.name not in data[color_name]:
            self.get_logger().error(f"'{color_name}' not found for {self.color_space.name}")
            return

        values = data[color_name][self.color_space.name]
        self.lower = np.array(values[0], dtype=np.uint8)
        self.upper = np.array(values[1], dtype=np.uint8)
        self._set_trackbar_values(self.lower, self.upper)
        self.sampled_pixels.clear()

        self.get_logger().info(
            f"Loaded '{color_name}': {self.lower.tolist()} - {self.upper.tolist()}"
        )

    def _switch_color_space(self) -> None:
        cv2.destroyAllWindows()
        self.window_initialized = False
        self.sampled_pixels.clear()

        self.color_space = ColorSpace.LAB if self.color_space == ColorSpace.HSV else ColorSpace.HSV
        self.config = self.TRACKBAR_CONFIG[self.color_space]
        self.lower = np.array(self.config["init"][::2])
        self.upper = np.array(self.config["init"][1::2])

        self.get_logger().info(f"Switched to {self.color_space.name}")

    def _cleanup(self) -> None:
        self.image_handler.cleanup()
        cv2.destroyAllWindows()
        self.get_logger().info("Exiting")
        rclpy.shutdown()
        sys.exit(0)


def main(args=None) -> None:
    rclpy.init(args=args)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--image-source", type=str, default=None)
    parser.add_argument("--color-space", type=str, default="hsv", choices=["hsv", "lab"])
    parsed, _ = parser.parse_known_args(args=args)

    node = ClickColorCalibrationNode(
        image_source=parsed.image_source,
        color_space=parsed.color_space,
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
