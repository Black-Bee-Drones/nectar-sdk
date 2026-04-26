"""ROS 2 vision nodes."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "ArucoNode": "nectar.vision.nodes.aruco_node",
    "CameraPublisherNode": "nectar.vision.nodes.camera_publisher_node",
    "ClickColorCalibrationNode": "nectar.vision.nodes.click_color_calibration_node",
    "ColorCalibrationNode": "nectar.vision.nodes.color_calibration_node",
    "LineDetectionNode": "nectar.vision.nodes.line_detection_node",
}


def __getattr__(name: str):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_ATTRS})


if TYPE_CHECKING:
    from .aruco_node import ArucoNode
    from .camera_publisher_node import CameraPublisherNode
    from .click_color_calibration_node import ClickColorCalibrationNode
    from .color_calibration_node import ColorCalibrationNode
    from .line_detection_node import LineDetectionNode


__all__ = [
    "ArucoNode",
    "CameraPublisherNode",
    "ClickColorCalibrationNode",
    "ColorCalibrationNode",
    "LineDetectionNode",
]
