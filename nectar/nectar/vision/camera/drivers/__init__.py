"""Camera driver implementations."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    "C920Cam": "nectar.vision.camera.drivers.c920_cam",
    "FileImageCam": "nectar.vision.camera.drivers.file_cam",
    "IMX219Cam": "nectar.vision.camera.drivers.imx219_cam",
    "OakdCam": "nectar.vision.camera.drivers.oakd_cam",
    "OakdCameraResolution": "nectar.vision.camera.drivers.oakd_cam",
    "OpenCVCam": "nectar.vision.camera.drivers.opencv_cam",
    "RealsenseCam": "nectar.vision.camera.drivers.realsense_cam",
    "ROSCam": "nectar.vision.camera.drivers.ros_cam",
    "ROSDepthCam": "nectar.vision.camera.drivers.ros_depth_cam",
    "T265Cam": "nectar.vision.camera.drivers.t265_cam",
    "T265Pose": "nectar.vision.camera.drivers.t265_cam",
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
    from .c920_cam import C920Cam
    from .file_cam import FileImageCam
    from .imx219_cam import IMX219Cam
    from .oakd_cam import OakdCam, OakdCameraResolution
    from .opencv_cam import OpenCVCam
    from .realsense_cam import RealsenseCam
    from .ros_cam import ROSCam
    from .ros_depth_cam import ROSDepthCam
    from .t265_cam import T265Cam, T265Pose


__all__ = [
    "FileImageCam",
    "OpenCVCam",
    "ROSCam",
    "ROSDepthCam",
    "C920Cam",
    "IMX219Cam",
    "RealsenseCam",
    "OakdCam",
    "OakdCameraResolution",
    "T265Cam",
    "T265Pose",
]
