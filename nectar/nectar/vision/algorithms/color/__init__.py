"""
Color detection and filtering algorithms.

Classes
-------
ColorDetector
    Detect colors using HSV or LAB thresholding.
ColorSpace
    Enum of supported color spaces (HSV, LAB).
"""

from nectar.vision.algorithms.color.color_detector import (
    ColorDetector,
    ColorSpace,
    default_calibration_path,
    load_calibration_data,
    resolve_calibration_path,
    save_calibration_data,
)

__all__ = [
    "ColorDetector",
    "ColorSpace",
    "default_calibration_path",
    "load_calibration_data",
    "resolve_calibration_path",
    "save_calibration_data",
]
