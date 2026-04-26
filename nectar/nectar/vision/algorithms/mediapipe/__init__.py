"""MediaPipe tracking solutions for hands and faces."""

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_ATTRS = {
    # Pull mediapipe (TFLite)
    "FaceLandmarkRegion": "nectar.vision.algorithms.mediapipe.face_tracker",
    "FaceMeshTracker": "nectar.vision.algorithms.mediapipe.face_tracker",
    "FaceMeshTrackerConfig": "nectar.vision.algorithms.mediapipe.face_tracker",
    "FaceResult": "nectar.vision.algorithms.mediapipe.face_tracker",
    "HandLandmark": "nectar.vision.algorithms.mediapipe.hand_tracker",
    "HandResult": "nectar.vision.algorithms.mediapipe.hand_tracker",
    "HandTracker": "nectar.vision.algorithms.mediapipe.hand_tracker",
    "HandTrackerConfig": "nectar.vision.algorithms.mediapipe.hand_tracker",
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
    from .face_tracker import (
        FaceLandmarkRegion,
        FaceMeshTracker,
        FaceMeshTrackerConfig,
        FaceResult,
    )
    from .hand_tracker import (
        HandLandmark,
        HandResult,
        HandTracker,
        HandTrackerConfig,
    )


__all__ = [
    # Hand tracking
    "HandTracker",
    "HandTrackerConfig",
    "HandResult",
    "HandLandmark",
    # Face mesh tracking
    "FaceMeshTracker",
    "FaceMeshTrackerConfig",
    "FaceResult",
    "FaceLandmarkRegion",
]
