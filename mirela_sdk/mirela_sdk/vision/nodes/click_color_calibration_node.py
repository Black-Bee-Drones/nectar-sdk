#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

import cv2
import numpy as np
import json
import os

class ClickColorCalibrationNode(Node):
    def __init__(self):
        super().__init__('click_color_calibration')

        self.seed_points = []
        self.all_pixels = []
        self.lower = None
        self.upper = None
        self.active_mask = False

        self.filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "color_calibration.json")

        cv2.namedWindow("Frame")
        cv2.setMouseCallback("Frame", self.mouse_callback)
        cv2.createTrackbar("Coverage %", "Frame", 90, 100, lambda x: None)
        cv2.createTrackbar("Tolerance", "Frame", 20, 50, lambda x: None)

        self.cap = cv2.VideoCapture(0)  # Change camera index if needed
        self.run()

    def mouse_callback(self, event, x, y, flags, param=None):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.seed_points.append((x, y))

    def save_to_json(self, color_name, lower, upper):
        data = {}
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    self.get_logger().warn("Empty or corrupted JSON. Creating a new one.")

        data[color_name] = {
            "HSV": [lower.tolist(), upper.tolist()]
        }

        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=4)
        self.get_logger().info(f"Color '{color_name}' saved to {self.filename}.")

    def load_from_json(self, color_name):
        if not os.path.exists(self.filename):
            self.get_logger().error("File not found.")
            return None, None

        with open(self.filename, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                self.get_logger().error("Invalid JSON.")
                return None, None

        color_data = data.get(color_name)
        if color_data is None or "HSV" not in color_data:
            self.get_logger().error(f"Color '{color_name}' not found or invalid.")
            return None, None

        lower = np.array(color_data["HSV"][0], dtype=np.uint8)
        upper = np.array(color_data["HSV"][1], dtype=np.uint8)
        self.get_logger().info(f"Loaded color '{color_name}': lower={lower.tolist()}, upper={upper.tolist()}")
        return lower, upper

    def update_threshold(self):
        if self.all_pixels:
            combined = np.vstack(self.all_pixels)
            p = cv2.getTrackbarPos("Coverage %", "Frame") / 100
            lower = []
            upper = []
            for i in range(3):  # For H, S, V channels
                channel = np.sort(combined[:, i])
                n = len(channel)
                low_idx = int((1 - p) / 2 * n)
                high_idx = int((1 + p) / 2 * n) - 1
                lower.append(channel[low_idx])
                upper.append(channel[high_idx])
            self.lower = np.array(lower, dtype=np.uint8)
            self.upper = np.array(upper, dtype=np.uint8)
            self.active_mask = True
            self.get_logger().info(f"Updated: lower={self.lower.tolist()}, upper={self.upper.tolist()}")
        else:
            self.lower = None
            self.upper = None
            self.active_mask = False
            self.get_logger().warn("No active points. Mask disabled.")

    def run(self):
        while rclpy.ok():
            ret, frame = self.cap.read()
            if not ret:
                self.get_logger().error("Failed to capture frame.")
                break

            display = frame.copy()
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            tolerance = cv2.getTrackbarPos("Tolerance", "Frame")

            if self.seed_points:
                for point in self.seed_points:
                    mask = np.zeros((hsv.shape[0]+2, hsv.shape[1]+2), np.uint8)
                    lo = (tolerance, tolerance, tolerance)
                    hi = (tolerance, tolerance, tolerance)

                    _img = hsv.copy()
                    cv2.floodFill(_img, mask, point, (0, 0, 0), lo, hi, flags=cv2.FLOODFILL_FIXED_RANGE)
                    mask = mask[1:-1, 1:-1]
                    hsv_pixels = hsv[mask == 1]
                    if len(hsv_pixels) > 0:
                        self.all_pixels.append(hsv_pixels)

                self.seed_points = []
                self.update_threshold()

            if self.active_mask and self.lower is not None and self.upper is not None:
                mask_thresh = cv2.inRange(hsv, self.lower, self.upper)

                kernel1 = np.ones((11, 11), np.uint8)
                kernel2 = np.ones((7, 7), np.uint8)
                kernel3 = np.ones((8, 8), np.uint8)

                mask_thresh = cv2.dilate(mask_thresh, kernel1, iterations=1)
                mask_thresh = cv2.erode(mask_thresh, kernel2, iterations=1)
                mask_thresh = cv2.morphologyEx(mask_thresh, cv2.MORPH_CLOSE, kernel3)

                result = cv2.bitwise_and(frame, frame, mask=mask_thresh)

                cv2.imshow("Mask", mask_thresh)
                cv2.imshow("Result", result)

            cv2.imshow("Frame", display)

            key = cv2.waitKey(1)
            if key == ord('r'):
                self.seed_points.clear()
                self.all_pixels.clear()
                self.lower = None
                self.upper = None
                self.active_mask = False
                self.get_logger().info("Reset.")
            elif key == ord('z'):
                if self.all_pixels:
                    self.all_pixels.pop()
                    self.update_threshold()
                else:
                    self.get_logger().warn("No clicks to undo.")
            elif key == ord('s'):
                if self.lower is not None and self.upper is not None:
                    color_name = input("Enter color name to save: ").strip()
                    if color_name:
                        self.save_to_json(color_name, self.lower, self.upper)
                else:
                    self.get_logger().error("No active HSV range to save.")
            elif key == ord('p'):
                color_name = input("Enter color name to load: ").strip()
                if color_name:
                    l, u = self.load_from_json(color_name)
                    if l is not None and u is not None:
                        self.lower = l
                        self.upper = u
                        self.active_mask = True
                        self.all_pixels.clear()
            elif key == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()


def main(args=None):
    rclpy.init(args=args)
    node = ClickColorCalibrationNode()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
