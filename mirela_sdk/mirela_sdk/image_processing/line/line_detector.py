#!/usr/bin/env python3

import cv2
import numpy as np
import math
from abc import ABC, abstractmethod
from typing import Tuple

from mirela_sdk.image_processing.color.color_detector import ColorDetector


## --- Approximation Methods --- ##
class ILineEstimationMethod(ABC):
    @staticmethod
    @abstractmethod
    def estimate(
        img_detect: np.ndarray, img_out: np.ndarray, offset: tuple, draw: bool = True
    ) -> Tuple[float, float]:
        pass


class HoughLinesP(ILineEstimationMethod):
    @staticmethod
    def estimate(
        img_detect: np.ndarray, img_out: np.ndarray, offset: tuple, draw: bool = True
    ) -> Tuple[float, float]:
        """
        Hough lines P detection method.
        Approximating a line from the probabilistic Hough transform
        together with line fitting

        Args:
            img_detect (numpy.ndarray): Image to detect lines in.
            img_out (numpy.ndarray): Image to draw detected lines on.
            offset (tuple): Offset values for drawing.
            draw (bool): Whether to draw the detected line.

        Returns:
            tuple: Tuple containing the center_x and angle of the detected line.
        """
        lines = cv2.HoughLinesP(
            img_detect,
            rho=1,
            theta=np.pi / 180,
            threshold=70,
            minLineLength=25,
            maxLineGap=10,
        )

        angle = center_x = float("nan")

        if lines is not None and len(lines) > 0:
            points = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                x1 += offset[0]
                y1 += offset[1]
                x2 += offset[0]
                y2 += offset[1]
                points.append([x1, y1])
                points.append([x2, y2])

            points = np.array(points, dtype=np.float32)
            [vx, vy, x, y] = cv2.fitLine(points, cv2.DIST_L2, 0, 0.01, 0.01)

            center_x = x[0]

            angle = math.degrees(math.atan2(vy[0], vx[0]))
            if angle <= 0:
                angle += 90.0
            else:
                angle -= 90.0

            if draw:
                # Draw the approximated line on the image
                m = 50
                cv2.line(
                    img_out,
                    (int(x[0] - m * vx[0]), int(y[0] - m * vy[0])),
                    (int(x[0] + m * vx[0]), int(y[0] + m * vy[0])),
                    (0, 255, 0),
                    2,
                )
                cv2.circle(img_out, (int(x[0]), int(y[0])), 2, (255, 0, 0), 3)

        return center_x, angle


class RotatedRect(ILineEstimationMethod):
    @staticmethod
    def estimate(
        img_detect: np.ndarray, img_out: np.ndarray, offset: tuple, draw: bool = True
    ) -> Tuple[float, float]:
        """
        Rotated rectangle detection method.
        Approximates a rectangle of minimum area on the found contour

        Args:
            img_detect (numpy.ndarray): Image to detect rotated rectangle in.
            img_out (numpy.ndarray): Image to draw detected rotated rectangle on.
            offset (tuple): Offset values for drawing.
            draw (bool): Whether to draw the detected rotated rectangle.

        Returns:
            tuple: Tuple containing the center_x and angle of the detected rotated rectangle.
        """

        contours, _ = cv2.findContours(
            img_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = sorted(contours, key=cv2.minAreaRect)

        angle = center_x = float("nan")

        if len(contours) > 0 and cv2.contourArea(contours[0]) > 1500:
            blackbox = cv2.minAreaRect(contours[0])
            (x_min, y_min), (w_min, h_min), angle_bb = blackbox

            if angle_bb < -45:
                angle_bb = 90 + angle_bb
            if w_min < h_min and angle_bb > 0:
                angle_bb = (90 - angle_bb) * -1
            if w_min > h_min and angle_bb < 0:
                angle_bb = 90 + angle_bb

            if angle_bb <= 0:
                angle = angle_bb + 90.0
            else:
                angle = angle_bb - 90.0

            blackbox = (x_min + offset[0], y_min + offset[1]), (w_min, h_min), angle_bb
            box = cv2.boxPoints(blackbox)
            box = np.intp(box)

            theta = np.radians(angle_bb)
            x1 = int(x_min - 100 * np.cos(theta)) + offset[0]
            y1 = int(y_min - 100 * np.sin(theta)) + offset[1]
            x2 = int(x_min + 100 * np.cos(theta)) + offset[0]
            y2 = int(y_min + 100 * np.sin(theta)) + offset[1]

            center = (int(x_min + offset[0]), int(y_min + offset[1]))
            center_x = center[0]

            if draw:
                cv2.line(img_out, (x1, y1), (x2, y2), (255, 0, 0), 3)
                cv2.circle(img_out, center, 2, (0, 255, 0), 3)

        return center_x, angle


class FitEllipse(ILineEstimationMethod):
    @staticmethod
    def estimate(
        img_detect: np.ndarray, img_out: np.ndarray, offset: tuple, draw: bool = True
    ) -> Tuple[float, float]:
        """
        Ellipse fitting detection method.
        Fits an ellipse to the detected contour

        Args:
            img_detect (numpy.ndarray): Image to detect ellipse in.
            img_out (numpy.ndarray): Image to draw detected ellipse on.
            offset (tuple): Offset values for drawing.
            draw (bool): Whether to draw the detected ellipse.

        Returns:
            tuple: Tuple containing the center_x and angle of the detected ellipse.
        """

        _, img_detect = cv2.threshold(img_detect, 1, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            img_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        angle = center_x = float("nan")
        direction = curvature = None

        if len(contours) > 0:
            rope_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(rope_contour) > 2000:
                M = cv2.moments(rope_contour)
                center_x = int(M["m10"] / M["m00"])
                epsilon = 0.006 * cv2.arcLength(rope_contour, True)
                approx_contour = cv2.approxPolyDP(rope_contour, epsilon, True)

                if len(approx_contour) >= 5:
                    ellipse = cv2.fitEllipse(approx_contour)
                    (xc, yc), (d1, d2), angle = ellipse
                    xc += offset[0]
                    yc += offset[1]
                    direction = np.sign(d2 - d1)
                    curvature = np.abs(d1 - d2) / max(d1, d2)

                if draw:
                    # Draw the ellipse on the image
                    cv2.ellipse(img_out, ((xc, yc), (d1, d2), angle), (0, 255, 0), 2)

        return center_x, angle


class LineDetector:
    def __init__(
        self, color="blue", estimation_method: ILineEstimationMethod = HoughLinesP
    ):
        """
        Constructor for the LineDetector class.

        Args:
            color (str, optional): Color to detect. Defaults to "blue".
        """
        self.color_detector = ColorDetector(mode="preset", color=color)
        self.estimation_method = estimation_method

    def detect_line(self, img, region=(0, 0), draw=True):
        """
        Detects the line using the specified method.

        Args:
            img (numpy.ndarray): Input image.
            method (function, optional): The line detection method to use. Defaults to None.
            region (tuple, optional): Region of interest in the format (width, height). Defaults to (0, 0) for the whole image.
            draw (bool, optional): Whether to draw the detected line on the output image. Defaults to True.

        Returns:
            tuple: Tuple containing the output image, center_x, and angle.
        """

        self.color_detector.filterColor(img)

        # Define the region of interest
        if region == (0, 0):
            region = (img.shape[1], img.shape[0])

        region_size = region
        region_center = (
            self.color_detector.mask.shape[1] // 2,
            self.color_detector.mask.shape[0] // 2,
        )
        offset = (
            region_center[0] - region_size[0] // 2,
            region_center[1] - region_size[1] // 2,
        )

        # Extract the subimage of the region of interest
        region = cv2.getRectSubPix(self.color_detector.mask, region_size, region_center)

        center_x = angle = float("nan")

        try:
            center_x, angle = self.estimation_method.estimate(region, img, offset, draw)

        except ValueError as e:
            print(f"Error in estimation method: {e}")

        if draw:
            # Draw the angle and center on the image
            cv2.putText(
                img,
                f"Angle: {angle:.2f} degrees",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

            cv2.putText(
                img,
                f"Center X: {center_x}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

        return img, region, center_x, angle


def main():
    color = "teste"  # Color to detect
    line_detector = LineDetector(color, HoughLinesP)

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        result, region, center_x, angle = line_detector.detect_line(
            frame, region=(400, 400)
        )

        print(angle)

        cv2.imshow("Line Detection", result)
        if cv2.waitKey(1) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
