"""Vision algorithms (markers, color, line, distance, MediaPipe)."""

from importlib import import_module
from typing import TYPE_CHECKING

from .color import ColorDetector, ColorSpace
from .distance import (
    DistanceEstimator,
    EstimationModel,
    ModelType,
    create_model,
)
from .line import (
    AdaptiveHoughLinesP,
    FitEllipse,
    HoughLinesP,
    ILineEstimationMethod,
    LineDetector,
    RansacLine,
    RotatedRect,
)
from .markers import Aruco

_LAZY_ATTRS = {
    # Distance calibration (matplotlib)
    "ModelCalibrator": "nectar.vision.algorithms.distance",
    "CalibrationResult": "nectar.vision.algorithms.distance",
    # MediaPipe (TFLite)
    "FaceLandmarkRegion": "nectar.vision.algorithms.mediapipe",
    "FaceMeshTracker": "nectar.vision.algorithms.mediapipe",
    "FaceMeshTrackerConfig": "nectar.vision.algorithms.mediapipe",
    "FaceResult": "nectar.vision.algorithms.mediapipe",
    "HandLandmark": "nectar.vision.algorithms.mediapipe",
    "HandResult": "nectar.vision.algorithms.mediapipe",
    "HandTracker": "nectar.vision.algorithms.mediapipe",
    "HandTrackerConfig": "nectar.vision.algorithms.mediapipe",
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
    from .distance import CalibrationResult, ModelCalibrator
    from .mediapipe import (
        FaceLandmarkRegion,
        FaceMeshTracker,
        FaceMeshTrackerConfig,
        FaceResult,
        HandLandmark,
        HandResult,
        HandTracker,
        HandTrackerConfig,
    )


__all__ = [
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
    "EstimationModel",
    "create_model",
    "ModelCalibrator",
    "CalibrationResult",
    # MediaPipe
    "HandTracker",
    "HandTrackerConfig",
    "HandResult",
    "HandLandmark",
    "FaceMeshTracker",
    "FaceMeshTrackerConfig",
    "FaceResult",
    "FaceLandmarkRegion",
]
