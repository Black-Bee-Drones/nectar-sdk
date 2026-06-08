#!/usr/bin/env python3
import json
import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node

from nectar.vision.algorithms.color import ColorSpace
from nectar.vision.camera import ImageHandler


class ColorCalibrationNode(Node):
    """
    Interactive color calibration node.

    Combines click-to-sample and trackbar fine-tuning in a single window.
    Click colored regions to auto-compute HSV/LAB thresholds via flood fill,
    then adjust the trackbars for fine control. Named colors are saved to the
    shared calibration file consumed by ``ColorDetector(mode="preset")``.

    Parameters (ROS)
    ----------------
    image_source : str
        Camera source identifier (default: ``webcam``).
    color_space : str
        Initial color space, ``hsv`` or ``lab`` (default: ``hsv``).
    flood_tolerance : int
        Initial flood-fill tolerance for click sampling (default: 15).

    Notes
    -----
    Mouse: left-click to sample a region.
    Keys: ``q`` quit, ``r`` reset, ``z`` undo, ``s`` save, ``l`` load,
    ``c`` switch color space.
    """

    WINDOW = "Color Calibration"

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

    def __init__(self) -> None:
        super().__init__("color_calibration_node")

        self.declare_parameter("image_source", "webcam")
        self.declare_parameter("color_space", "hsv")
        self.declare_parameter("flood_tolerance", 15)

        image_source = str(self.get_parameter("image_source").value)
        color_space = str(self.get_parameter("color_space").value)
        self.flood_tolerance = int(self.get_parameter("flood_tolerance").value)

        self.color_space = ColorSpace.HSV if color_space.upper() == "HSV" else ColorSpace.LAB
        self.config = self.TRACKBAR_CONFIG[self.color_space]

        self.sampled_pixels: List[np.ndarray] = []
        self.pending_clicks: List[tuple] = []
        self.lower = np.array(self.config["init"][::2])
        self.upper = np.array(self.config["init"][1::2])

        self.file_path = self._calibration_file_path()
        self.window_initialized = False

        if not self._gui_available():
            self.get_logger().error(
                "Color calibration needs an OpenCV GUI (mouse + trackbars) but none "
                "is available. Run on a machine with a display."
            )
            raise SystemExit(1)

        self.image_handler = ImageHandler(
            image_source=image_source,
            image_processing_callback=self._process,
        )

        self.get_logger().info(f"Color calibration: {self.color_space.name} mode")
        self.get_logger().info("Click to sample | r=reset z=undo s=save l=load c=switch q=quit")
        self.image_handler.run()

    @staticmethod
    def _calibration_file_path() -> str:
        """Resolve the canonical color calibration file shared with ColorDetector."""
        import nectar.vision.algorithms.color.color_detector as _cd_mod

        return os.path.join(
            os.path.dirname(os.path.realpath(_cd_mod.__file__)), "color_calibration.json"
        )

    @staticmethod
    def _gui_available() -> bool:
        try:
            cv2.namedWindow("__nectar_gui_probe__")
            cv2.destroyWindow("__nectar_gui_probe__")
            return True
        except cv2.error:
            return False

    def _mouse_cb(self, event: int, x: int, y: int, flags: int, param) -> None:
        del flags, param
        if event == cv2.EVENT_LBUTTONDOWN:
            self.pending_clicks.append((x, y))

    def _init_window(self) -> None:
        cv2.namedWindow(self.WINDOW)
        cv2.setMouseCallback(self.WINDOW, self._mouse_cb)
        cv2.createTrackbar("Tolerance", self.WINDOW, self.flood_tolerance, 50, lambda x: None)
        for i, name in enumerate(self.config["names"]):
            cv2.createTrackbar(
                name, self.WINDOW, self.config["init"][i], self.config["max"][i], lambda x: None
            )
        self.window_initialized = True

    def _get_trackbar_values(self) -> Tuple[np.ndarray, np.ndarray]:
        names = self.config["names"]
        lower = np.array(
            [cv2.getTrackbarPos(names[i], self.WINDOW) for i in (0, 2, 4)],
            dtype=np.uint8,
        )
        upper = np.array(
            [cv2.getTrackbarPos(names[i], self.WINDOW) for i in (1, 3, 5)],
            dtype=np.uint8,
        )
        return lower, upper

    def _set_trackbar_values(self, lower: np.ndarray, upper: np.ndarray) -> None:
        names = self.config["names"]
        try:
            for idx, value in zip((0, 2, 4), lower):
                cv2.setTrackbarPos(names[idx], self.WINDOW, int(value))
            for idx, value in zip((1, 3, 5), upper):
                cv2.setTrackbarPos(names[idx], self.WINDOW, int(value))
        except cv2.error:
            pass

    def _sample_region(self, converted: np.ndarray, point: tuple) -> Optional[np.ndarray]:
        """Sample pixels around a click using flood fill."""
        h, w = converted.shape[:2]
        x, y = point
        if not (0 <= x < w and 0 <= y < h):
            return None

        tol = cv2.getTrackbarPos("Tolerance", self.WINDOW)
        mask = np.zeros((h + 2, w + 2), np.uint8)
        cv2.floodFill(
            converted.copy(),
            mask,
            (x, y),
            255,
            (tol, tol, tol),
            (tol, tol, tol),
            cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE,
        )
        pixels = converted[mask[1:-1, 1:-1] == 1]
        return pixels if len(pixels) else None

    def _compute_bounds(self) -> None:
        """Compute lower/upper bounds from all sampled pixels."""
        if not self.sampled_pixels:
            return

        all_pixels = np.vstack(self.sampled_pixels)
        margins = [5, 15, 15] if self.color_space == ColorSpace.HSV else [10, 10, 10]
        maxes = self.config["max"][1::2]

        lower, upper = [], []
        for ch in range(3):
            ch_data = all_pixels[:, ch]
            lower.append(max(0, int(np.percentile(ch_data, 2)) - margins[ch]))
            upper.append(min(maxes[ch], int(np.percentile(ch_data, 98)) + margins[ch]))

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
        self.pending_clicks.clear()

        self.lower, self.upper = self._get_trackbar_values()

        mask = cv2.inRange(converted, self.lower, self.upper)
        mask = self._apply_morphology(mask)
        result = cv2.bitwise_and(img, img, mask=mask)

        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        display = np.hstack([img, mask_bgr, result])

        cv2.putText(
            display,
            f"{self.color_space.name} | Samples: {len(self.sampled_pixels)}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            display,
            f"L: {self.lower.tolist()} U: {self.upper.tolist()}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
        )

        cv2.imshow(self.WINDOW, display)
        self._handle_keys()

    @staticmethod
    def _apply_morphology(mask: np.ndarray) -> np.ndarray:
        """Match ColorDetector.filterColor morphology so the preview reflects runtime."""
        mask = cv2.dilate(mask, np.ones((11, 11), np.uint8), iterations=1)
        mask = cv2.erode(mask, np.ones((7, 7), np.uint8), iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((8, 8), np.uint8))
        _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
        return mask

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
        if not self.sampled_pixels:
            self.get_logger().info("No samples to undo")
            return
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

        data.setdefault(color_name, {})
        data[color_name][self.color_space.name] = [self.lower.tolist(), self.upper.tolist()]

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
        if rclpy.ok():
            rclpy.shutdown()


def main(args=None) -> None:
    """Entry point for the color calibration node."""
    import nectar

    rclpy.init(args=args)
    nectar.use_executor(rclpy.get_global_executor())

    node = ColorCalibrationNode()

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
