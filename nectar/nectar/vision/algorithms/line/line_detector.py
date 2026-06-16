#!/usr/bin/env python3
import math
from abc import ABC, abstractmethod
from typing import Tuple

import cv2
import numpy as np

from nectar.vision.algorithms.color.color_detector import ColorDetector, ColorSpace


class ILineEstimationMethod(ABC):
    """
    Abstract interface for line estimation strategies.

    All estimation methods must implement the estimate() method
    to detect lines from binary masks.
    """

    @staticmethod
    @abstractmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Estimate a line in the image.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect the line in.
        img_out : np.ndarray
            Output image to draw on.
        offset : tuple
            Offset values (x, y) for drawing.
        draw : bool, default=True
            Whether to draw visualization.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
            - center_x, center_y: Line center coordinates
            - angle: Line angle in degrees
            - width, height: Average line dimensions in pixels
            - x, y, w, h: Bounding box coordinates
            - rotated_box: Points of the rotated bounding box
        """
        pass


def calc_width_height(
    mask: np.ndarray,
) -> Tuple[float, float, int, int, int, int, np.ndarray]:
    """
    Calculate average width and height of detected region.

    Parameters
    ----------
    mask : np.ndarray
        Binary mask image.

    Returns
    -------
    tuple
        (width, height, x, y, w, h, box)
        - width, height: Average dimensions of white pixels
        - x, y, w, h: Bounding rectangle coordinates
        - box: Rotated bounding box points
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0, 0.0, 0, 0, 0, 0, None

    largest_contour = max(contours, key=cv2.contourArea)

    rect = cv2.minAreaRect(largest_contour)
    (x_center, y_center), (w_rect, h_rect), angle_rect = rect

    box = cv2.boxPoints(rect)
    box = np.intp(box)

    x, y, w, h = cv2.boundingRect(box)

    y = max(0, y)
    x = max(0, x)
    h = min(h, mask.shape[0] - y)
    w = min(w, mask.shape[1] - x)

    if w > 0 and h > 0:
        roi = mask[y : y + h, x : x + w]

        threshold = 128  # Consider pixels with values > 128 as white
        white_pixels = roi > threshold

        if np.any(white_pixels):
            # Calculate non-zero columns (for height) using the threshold
            col_sums = np.sum(white_pixels, axis=0)
            non_zero_cols = col_sums[col_sums > 0]
            height = float(np.mean(non_zero_cols)) if len(non_zero_cols) > 0 else 0.0

            # Calculate non-zero rows (for width) using the threshold
            row_sums = np.sum(white_pixels, axis=1)
            non_zero_rows = row_sums[row_sums > 0]
            width = float(np.mean(non_zero_rows)) if len(non_zero_rows) > 0 else 0.0
        else:
            # If no white pixels found with threshold, try using the contour directly
            contour_area = cv2.contourArea(largest_contour)
            if contour_area > 0:
                # Estimate width and height from contour
                width = h_rect if h_rect > w_rect else w_rect
                height = w_rect if h_rect > w_rect else h_rect
            else:
                width = height = 0.0
    else:
        print(f"Invalid ROI dimensions: x={x}, y={y}, w={w}, h={h}")
        width = height = 0.0

    return (
        width,
        height,
        x,
        y,
        w,
        h,
        box,
    )


class HoughLinesP(ILineEstimationMethod):
    """
    Probabilistic Hough transform line detection.

    Uses cv2.HoughLinesP combined with cv2.fitLine for robust
    line estimation from multiple detected segments.
    """

    @staticmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Detect line using probabilistic Hough transform.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect lines in.
        img_out : np.ndarray
            Output image to draw detected lines on.
        offset : tuple
            Offset values for drawing.
        draw : bool, default=True
            Whether to draw the detected line.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
        """
        lines = cv2.HoughLinesP(
            img_detect,
            rho=1,
            theta=np.pi / 180,
            threshold=70,
            minLineLength=25,
            maxLineGap=10,
        )

        angle = center_x = center_y = float("nan")

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
            center_y = y[0]

            angle = math.degrees(math.atan2(vy[0], vx[0]))
            if angle <= 0:
                angle += 90.0
            else:
                angle -= 90.0

            if draw:
                line_color = draw_color if draw_color is not None else (0, 255, 0)

                if draw_color is not None:
                    center_color = (
                        max(0, draw_color[0] // 2),
                        max(0, draw_color[1] // 2),
                        max(0, draw_color[2] // 2),
                    )
                else:
                    center_color = (255, 0, 0)

                m = 50
                cv2.line(
                    img_out,
                    (int(x[0] - m * vx[0]), int(y[0] - m * vy[0])),
                    (int(x[0] + m * vx[0]), int(y[0] + m * vy[0])),
                    line_color,
                    2,
                )
                cv2.circle(img_out, (int(x[0]), int(y[0])), 2, center_color, 3)

        width, height, x, y, w, h, rotated_box = calc_width_height(img_detect)

        return center_x, center_y, angle, width, height, x, y, w, h, rotated_box


class RotatedRect(ILineEstimationMethod):
    """
    Minimum area rotated rectangle detection.

    Fits a rotated rectangle to the largest contour for
    line orientation estimation.
    """

    @staticmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Detect line using minimum area rotated rectangle.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect rotated rectangle in.
        img_out : np.ndarray
            Output image to draw on.
        offset : tuple
            Offset values for drawing.
        draw : bool, default=True
            Whether to draw the detected rectangle.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
        """

        contours, _ = cv2.findContours(img_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        largest_contour = max(contours, key=cv2.contourArea)

        angle = center_x = center_y = float("nan")

        if len(contours) > 0 and cv2.contourArea(largest_contour) > 1500:
            blackbox = cv2.minAreaRect(largest_contour)
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
            center_y = center[1]

            if draw:
                line_color = draw_color if draw_color is not None else (255, 0, 0)

                if draw_color is not None:
                    center_color = (
                        min(255, draw_color[0] + 50),
                        min(255, draw_color[1] + 50),
                        min(255, draw_color[2] + 50),
                    )
                else:
                    center_color = (0, 255, 0)

                cv2.line(img_out, (x1, y1), (x2, y2), line_color, 3)
                cv2.circle(img_out, center, 2, center_color, 3)

        width, height, x, y, w, h, rotated_box = calc_width_height(img_detect)

        return center_x, center_y, angle, width, height, x, y, w, h, rotated_box


class FitEllipse(ILineEstimationMethod):
    """
    Ellipse fitting line detection.

    Fits an ellipse to the detected contour for curved
    line estimation.
    """

    @staticmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Detect line by fitting ellipse to contour.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect ellipse in.
        img_out : np.ndarray
            Output image to draw on.
        offset : tuple
            Offset values for drawing.
        draw : bool, default=True
            Whether to draw the detected ellipse.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
        """

        _, img_detect = cv2.threshold(img_detect, 1, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(img_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        angle = center_x = center_y = float("nan")
        _direction = _curvature = None

        if len(contours) > 0:
            rope_contour = max(contours, key=cv2.contourArea)
            if cv2.contourArea(rope_contour) > 2000:
                M = cv2.moments(rope_contour)
                center_x = int(M["m10"] / M["m00"])
                center_y = int(M["m01"] / M["m00"])
                epsilon = 0.006 * cv2.arcLength(rope_contour, True)
                approx_contour = cv2.approxPolyDP(rope_contour, epsilon, True)

                if len(approx_contour) >= 5:
                    ellipse = cv2.fitEllipse(approx_contour)
                    (xc, yc), (d1, d2), angle = ellipse
                    xc += offset[0]
                    yc += offset[1]
                    center_x = xc
                    center_y = yc
                    _direction = np.sign(d2 - d1)
                    _curvature = np.abs(d1 - d2) / max(d1, d2)

                if draw:
                    cv2.ellipse(img_out, ((xc, yc), (d1, d2), angle), (0, 255, 0), 2)

        width, height, x, y, w, h, rotated_box = calc_width_height(img_detect)

        return center_x, center_y, angle, width, height, x, y, w, h, rotated_box


class AdaptiveHoughLinesP(ILineEstimationMethod):
    """
    Adaptive Hough transform with dynamic parameter tuning.

    Automatically adjusts threshold and line length parameters
    based on image characteristics.
    """

    @staticmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Detect line using adaptive Hough transform.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect lines in.
        img_out : np.ndarray
            Output image to draw on.
        offset : tuple
            Offset values for drawing.
        draw : bool, default=True
            Whether to draw the detected line.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
        """
        mean_val = np.mean(img_detect)
        std_val = np.std(img_detect)

        threshold = max(30, min(100, int(mean_val + std_val)))
        min_line_length = max(15, min(50, int(img_detect.shape[1] * 0.05)))
        max_line_gap = max(5, min(20, int(min_line_length * 0.4)))

        lines = cv2.HoughLinesP(
            img_detect,
            rho=1,
            theta=np.pi / 180,
            threshold=threshold,
            minLineLength=min_line_length,
            maxLineGap=max_line_gap,
        )

        angle = center_x = center_y = float("nan")

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
            center_y = y[0]

            angle = math.degrees(math.atan2(vy[0], vx[0]))
            if angle <= 0:
                angle += 90.0
            else:
                angle -= 90.0

            if draw:
                m = 50
                cv2.line(
                    img_out,
                    (int(x[0] - m * vx[0]), int(y[0] - m * vy[0])),
                    (int(x[0] + m * vx[0]), int(y[0] + m * vy[0])),
                    (0, 255, 0),
                    2,
                )
                cv2.circle(img_out, (int(x[0]), int(y[0])), 2, (255, 0, 0), 3)

                cv2.putText(
                    img_out,
                    f"Threshold: {threshold}",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    1,
                )
                cv2.putText(
                    img_out,
                    f"MinLen: {min_line_length}, MaxGap: {max_line_gap}",
                    (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    1,
                )

        width, height, x, y, w, h, rotated_box = calc_width_height(img_detect)

        return center_x, center_y, angle, width, height, x, y, w, h, rotated_box


class RansacLine(ILineEstimationMethod):
    """
    RANSAC-based robust line fitting.

    Uses contour points with line fitting for outlier-resistant
    line detection.
    """

    @staticmethod
    def _fit_line_ransac(
        points: np.ndarray,
        residual_threshold: float = 4.0,
        max_iterations: int = 100,
    ) -> Tuple[float, float]:
        """
        Estimate a line direction from 2D points using RANSAC.

        Samples point pairs to build candidate lines, scores each by the
        number of inliers within ``residual_threshold`` (perpendicular
        distance), then refits the largest consensus set with least squares.
        Robust to outliers and handles arbitrary orientations.

        Parameters
        ----------
        points : np.ndarray
            Array of shape (N, 2) with point coordinates.
        residual_threshold : float, default=4.0
            Maximum perpendicular distance (pixels) for an inlier.
        max_iterations : int, default=100
            Number of RANSAC sampling iterations.

        Returns
        -------
        tuple of float
            (vx, vy) unit direction vector of the fitted line.
        """
        pts = points.astype(np.float64).reshape(-1, 2)

        best_inliers = None
        best_count = 0
        rng = np.random.default_rng(0)

        for _ in range(max_iterations):
            i, j = rng.choice(len(pts), size=2, replace=False)
            direction = pts[j] - pts[i]
            norm = np.hypot(direction[0], direction[1])
            if norm < 1e-6:
                continue

            normal = np.array([-direction[1], direction[0]]) / norm
            distances = np.abs((pts - pts[i]) @ normal)
            inliers = distances < residual_threshold
            count = int(np.count_nonzero(inliers))

            if count > best_count:
                best_count = count
                best_inliers = inliers

        fit_points = pts[best_inliers] if best_count >= 2 else pts
        vx, vy, _, _ = cv2.fitLine(fit_points.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01)
        return float(vx[0]), float(vy[0])

    @staticmethod
    def estimate(
        img_detect: np.ndarray,
        img_out: np.ndarray,
        offset: tuple,
        draw: bool = True,
        draw_color=None,
    ) -> Tuple[float, float, float, float, float, int, int, int, int, np.ndarray]:
        """
        Detect line using RANSAC-based fitting.

        Parameters
        ----------
        img_detect : np.ndarray
            Binary image to detect lines in.
        img_out : np.ndarray
            Output image to draw on.
        offset : tuple
            Offset values for drawing.
        draw : bool, default=True
            Whether to draw the detected line.
        draw_color : tuple, optional
            BGR color tuple for drawing.

        Returns
        -------
        tuple
            (center_x, center_y, angle, width, height, x, y, w, h, rotated_box)
        """
        contours, _ = cv2.findContours(img_detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        angle = center_x = center_y = float("nan")

        if len(contours) > 0:
            largest_contour = max(contours, key=cv2.contourArea)
            points = largest_contour.reshape(-1, 2)
            moments = cv2.moments(largest_contour)

            if cv2.contourArea(largest_contour) > 1500 and len(points) >= 5 and moments["m00"] != 0:
                vx, vy = RansacLine._fit_line_ransac(points)

                center_x = moments["m10"] / moments["m00"] + offset[0]
                center_y = moments["m01"] / moments["m00"] + offset[1]

                angle = math.degrees(math.atan2(vy, vx))
                if angle <= 0:
                    angle += 90.0
                else:
                    angle -= 90.0

                if draw:
                    m = 100
                    cv2.line(
                        img_out,
                        (int(center_x - m * vx), int(center_y - m * vy)),
                        (int(center_x + m * vx), int(center_y + m * vy)),
                        (0, 255, 0),
                        2,
                    )
                    cv2.circle(img_out, (int(center_x), int(center_y)), 3, (0, 0, 255), -1)

        width, height, x, y, w, h, rotated_box = calc_width_height(img_detect)

        return center_x, center_y, angle, width, height, x, y, w, h, rotated_box


class LineDetector:
    """
    High-level line detector with color filtering.

    Combines color detection with line estimation methods
    for detecting colored lines in images.

    Parameters
    ----------
    color : str, optional
        Color name to detect (must exist in calibration file).
        If None, uses external_mask for detection.
    estimation_method : ILineEstimationMethod, default=HoughLinesP
        Strategy class for line estimation.
    color_space : ColorSpace, optional
        Color space for detection (HSV or LAB).

    Attributes
    ----------
    color_detector : ColorDetector
        Instance for color filtering.
    estimation_method : ILineEstimationMethod
        Active estimation strategy.
    prev_angle : float
        Previous angle for exponential smoothing.
    external_mask : np.ndarray
        External binary mask to use instead of color detection.
    """

    def __init__(
        self,
        color="blue",
        estimation_method: ILineEstimationMethod = HoughLinesP,
        color_space=None,
    ):
        if color_space is None:
            color_space = ColorSpace.HSV

        self.color = color
        self.color_space = color_space
        self._external_mask = None

        if color is not None:
            self.color_detector = ColorDetector(mode="preset", color=color, color_space=color_space)
        else:
            self.color_detector = None

        self.estimation_method = estimation_method
        self.text_positions = {
            "color": (10, 90),
            "angle": (10, 30),
            "center_x": (10, 60),
        }
        self.prev_angle = float("nan")

    @property
    def external_mask(self) -> np.ndarray:
        """External binary mask for line detection."""
        return self._external_mask

    @external_mask.setter
    def external_mask(self, mask: np.ndarray) -> None:
        self._external_mask = mask

    def set_text_positions(self, positions_dict):
        """
        Set positions for text labels on output image.

        Parameters
        ----------
        positions_dict : dict
            Dictionary with keys 'angle', 'center_x', 'color'
            and (x, y) tuple values.
        """
        if positions_dict and isinstance(positions_dict, dict):
            for key, value in positions_dict.items():
                if key in self.text_positions and isinstance(value, tuple) and len(value) == 2:
                    self.text_positions[key] = value

    def detect_line(self, img, region=(0, 0), draw=True, draw_color=None):
        """
        Detect line in image using color filtering and estimation.

        Parameters
        ----------
        img : np.ndarray
            Input BGR image.
        region : tuple, default=(0, 0)
            Region of interest size (width, height).
            (0, 0) uses full image.
        draw : bool, default=True
            Whether to draw visualizations.
        draw_color : tuple, optional
            BGR color for drawing.

        Returns
        -------
        tuple
            (output_img, mask, center_x, center_y, angle, width, height)
            - output_img: Image with drawings
            - mask: Binary region mask
            - center_x, center_y: Line center coordinates
            - angle: Line angle in degrees
            - width, height: Line dimensions in pixels
        """
        if self._external_mask is not None:
            mask = self._external_mask
        elif self.color_detector is not None:
            self.color_detector.filterColor(img)
            mask = self.color_detector.mask
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        if region == (0, 0):
            region = (img.shape[1], img.shape[0])

        region_size = region
        region_center = (
            mask.shape[1] // 2,
            mask.shape[0] // 2,
        )
        offset = (
            region_center[0] - region_size[0] // 2,
            region_center[1] - region_size[1] // 2,
        )

        region = cv2.getRectSubPix(mask, region_size, region_center)
        _, region = cv2.threshold(region, 128, 255, cv2.THRESH_BINARY)

        center_x = center_y = angle = float("nan")
        width = height = float("nan")
        x = y = w = h = 0
        rotated_box = None

        try:
            line_color = draw_color if draw_color is not None else (0, 255, 0)
            try:
                center_x, center_y, angle, width, height, x, y, w, h, rotated_box = (
                    self.estimation_method.estimate(region, img, offset, draw, line_color)
                )
            except (TypeError, ValueError):
                try:
                    (
                        center_x,
                        center_y,
                        angle,
                        width,
                        height,
                        x,
                        y,
                        w,
                        h,
                        rotated_box,
                    ) = self.estimation_method.estimate(region, img, offset, draw)
                except ValueError:
                    center_x, center_y, angle, width, height, x, y, w, h = (
                        self.estimation_method.estimate(region, img, offset, draw)
                    )
        except ValueError as e:
            print(f"Error in estimation method: {e}")

        # angle smoothing, exponential moving average
        alpha = 0.1
        if not math.isnan(angle):
            if not math.isnan(self.prev_angle):
                angle = alpha * angle + (1 - alpha) * self.prev_angle
            self.prev_angle = angle

        if draw:
            text_color = draw_color if draw_color is not None else (0, 0, 255)
            cv2.putText(
                img,
                f"Angle: {angle:.2f}",
                self.text_positions["angle"],
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                1,
            )

            cv2.putText(
                img,
                f"Center X: {center_x:.2f}",
                self.text_positions["center_x"],
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                1,
            )

            if hasattr(self, "color") and self.color:
                cv2.putText(
                    img,
                    f"Color: {self.color}, {self.color_space.name}",
                    self.text_positions["color"],
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    text_color,
                    1,
                )

            if w > 0 and h > 0:
                if rotated_box is not None:
                    cv2.drawContours(
                        img,
                        [rotated_box + np.array([offset[0], offset[1]])],
                        0,
                        (0, 255, 255),
                        2,
                    )
                else:
                    cv2.rectangle(
                        img,
                        (x + offset[0], y + offset[1]),
                        (x + w + offset[0], y + h + offset[1]),
                        (0, 255, 255),
                        2,
                    )

        return img, region, center_x, center_y, angle, width, height


def main():
    """Demo function for line detection."""
    color = "teste"
    line_detector = LineDetector(color, HoughLinesP)

    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        result, region, center_x, center_y, angle, width, height = line_detector.detect_line(
            frame, region=(400, 400)
        )

        print(f"Angle: {angle:.2f}, Width: {width:.2f}, Height: {height:.2f}")

        cv2.imshow("Line Detection", result)
        cv2.imshow("Mask", region)
        if cv2.waitKey(1) == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
