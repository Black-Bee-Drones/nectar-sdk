"""
Line detection algorithms with multiple estimation strategies.

Classes
-------
LineDetector
    High-level line detector with color filtering.
ILineEstimationMethod
    Abstract interface for line estimation strategies.
HoughLinesP
    Probabilistic Hough transform detection.
RotatedRect
    Minimum area rotated rectangle detection.
FitEllipse
    Ellipse fitting for curved lines.
AdaptiveHoughLinesP
    Adaptive Hough with dynamic parameters.
RansacLine
    RANSAC-based robust line fitting.
"""

from nectar.vision.algorithms.line.line_detector import (
    AdaptiveHoughLinesP,
    FitEllipse,
    HoughLinesP,
    ILineEstimationMethod,
    LineDetector,
    RansacLine,
    RotatedRect,
)

__all__ = [
    "LineDetector",
    "ILineEstimationMethod",
    "HoughLinesP",
    "RotatedRect",
    "FitEllipse",
    "AdaptiveHoughLinesP",
    "RansacLine",
]
