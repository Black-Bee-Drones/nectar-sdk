"""MediaPipe tracking solutions for hands and faces."""

from .hand_tracker import (
    HandTracker,
    HandTrackerConfig,
    HandResult,
    HandLandmark,
)
from .face_tracker import (
    FaceMeshTracker,
    FaceMeshTrackerConfig,
    FaceResult,
    FaceLandmarkRegion,
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
