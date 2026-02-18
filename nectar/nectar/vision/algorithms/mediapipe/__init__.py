"""MediaPipe tracking solutions for hands and faces."""

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
