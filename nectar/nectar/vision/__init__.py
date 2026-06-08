"""Nectar SDK - Vision module."""

from importlib import import_module
from typing import TYPE_CHECKING

from nectar.vision.algorithms import (
    AdaptiveHoughLinesP,
    Aruco,
    ColorDetector,
    ColorSpace,
    DistanceEstimator,
    FitEllipse,
    HoughLinesP,
    ILineEstimationMethod,
    LineDetector,
    ModelType,
    OpticalFlowConfig,
    OpticalFlowEstimator,
    OpticalFlowResult,
    RansacLine,
    RotatedRect,
)
from nectar.vision.camera import (
    AbstractCam,
    C920Config,
    CameraCalibration,
    CameraConfig,
    CameraFactory,
    DepthCam,
    FileImageConfig,
    ImageHandler,
    IMX219Config,
    OakDConfig,
    OpenCVConfig,
    QoSDurability,
    QoSReliability,
    RealSenseConfig,
    ROSConfig,
    ROSDepthConfig,
    T265Config,
)

_LAZY_ATTRS = {
    # ImageCalculus pulls geopy (geodesic distance helpers)
    "ImageCalculus": "nectar.vision.utils",
    # Distance calibration (matplotlib)
    "ModelCalibrator": "nectar.vision.algorithms",
    "CalibrationResult": "nectar.vision.algorithms",
    # MediaPipe (TFLite)
    "FaceLandmarkRegion": "nectar.vision.algorithms",
    "FaceMeshTracker": "nectar.vision.algorithms",
    "FaceMeshTrackerConfig": "nectar.vision.algorithms",
    "FaceResult": "nectar.vision.algorithms",
    "HandLandmark": "nectar.vision.algorithms",
    "HandResult": "nectar.vision.algorithms",
    "HandTracker": "nectar.vision.algorithms",
    "HandTrackerConfig": "nectar.vision.algorithms",
    # Camera drivers (pyrealsense2 / depthai / cv2 backends)
    "C920Cam": "nectar.vision.camera",
    "FileImageCam": "nectar.vision.camera",
    "IMX219Cam": "nectar.vision.camera",
    "OakdCam": "nectar.vision.camera",
    "OakdCameraResolution": "nectar.vision.camera",
    "OpenCVCam": "nectar.vision.camera",
    "RealsenseCam": "nectar.vision.camera",
    "ROSCam": "nectar.vision.camera",
    "ROSDepthCam": "nectar.vision.camera",
    "T265Cam": "nectar.vision.camera",
    "T265Pose": "nectar.vision.camera",
    # ROS 2 nodes (entry points; imported only when explicitly requested)
    "ArucoNode": "nectar.vision.nodes",
    "CameraPublisherNode": "nectar.vision.nodes",
    "ColorCalibrationNode": "nectar.vision.nodes",
    "LineDetectionNode": "nectar.vision.nodes",
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
    from nectar.vision.algorithms import (
        CalibrationResult,
        FaceLandmarkRegion,
        FaceMeshTracker,
        FaceMeshTrackerConfig,
        FaceResult,
        HandLandmark,
        HandResult,
        HandTracker,
        HandTrackerConfig,
        ModelCalibrator,
    )
    from nectar.vision.camera import (
        C920Cam,
        FileImageCam,
        IMX219Cam,
        OakdCam,
        OakdCameraResolution,
        OpenCVCam,
        RealsenseCam,
        ROSCam,
        ROSDepthCam,
        T265Cam,
        T265Pose,
    )
    from nectar.vision.nodes import (
        ArucoNode,
        CameraPublisherNode,
        ColorCalibrationNode,
        LineDetectionNode,
    )
    from nectar.vision.utils import ImageCalculus


__all__ = [
    # Camera
    "AbstractCam",
    "CameraCalibration",
    "DepthCam",
    "CameraConfig",
    "ROSConfig",
    "ROSDepthConfig",
    "FileImageConfig",
    "OpenCVConfig",
    "C920Config",
    "IMX219Config",
    "RealSenseConfig",
    "OakDConfig",
    "QoSReliability",
    "QoSDurability",
    "CameraFactory",
    "ImageHandler",
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
    "T265Config",
    "T265Pose",
    # Markers
    "Aruco",
    # Color
    "ColorDetector",
    "ColorSpace",
    # Line
    "LineDetector",
    "ILineEstimationMethod",
    "HoughLinesP",
    "RotatedRect",
    "FitEllipse",
    "RansacLine",
    "AdaptiveHoughLinesP",
    # Distance
    "DistanceEstimator",
    "ModelType",
    "ModelCalibrator",
    "CalibrationResult",
    # Flow
    "OpticalFlowEstimator",
    "OpticalFlowConfig",
    "OpticalFlowResult",
    # MediaPipe
    "HandTracker",
    "HandTrackerConfig",
    "HandResult",
    "HandLandmark",
    "FaceMeshTracker",
    "FaceMeshTrackerConfig",
    "FaceResult",
    "FaceLandmarkRegion",
    # Utils
    "ImageCalculus",
    # Nodes
    "ArucoNode",
    "ColorCalibrationNode",
    "LineDetectionNode",
    "CameraPublisherNode",
]
