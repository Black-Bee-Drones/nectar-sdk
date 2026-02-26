from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
    from mediapipe.framework.formats import landmark_pb2
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    MEDIAPIPE_AVAILABLE = True
except ImportError:
    mp = None
    landmark_pb2 = None
    python = None
    vision = None
    MEDIAPIPE_AVAILABLE = False


class FaceLandmarkRegion:
    """Predefined face landmark index groups.

    Groups of landmark indices for specific facial regions.
    Useful for extracting specific facial features.

    References
    ----------
    .. [1] MediaPipe Face Mesh Map
       https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
    """

    FACE_OVAL: List[int] = [
        10,
        338,
        297,
        332,
        284,
        251,
        389,
        356,
        454,
        323,
        361,
        288,
        397,
        365,
        379,
        378,
        400,
        377,
        152,
        148,
        176,
        149,
        150,
        136,
        172,
        58,
        132,
        93,
        234,
        127,
        162,
        21,
        54,
        103,
        67,
        109,
    ]

    LIPS: List[int] = [
        61,
        146,
        91,
        181,
        84,
        17,
        314,
        405,
        321,
        375,
        291,
        308,
        324,
        318,
        402,
        317,
        14,
        87,
        178,
        88,
        95,
        185,
        40,
        39,
        37,
        0,
        267,
        269,
        270,
        409,
        415,
        310,
        311,
        312,
        13,
        82,
        81,
        42,
        183,
        78,
    ]

    LOWER_LIPS: List[int] = [
        61,
        146,
        91,
        181,
        84,
        17,
        314,
        405,
        321,
        375,
        291,
        308,
        324,
        318,
        402,
        317,
        14,
        87,
        178,
        88,
        95,
    ]

    UPPER_LIPS: List[int] = [
        185,
        40,
        39,
        37,
        0,
        267,
        269,
        270,
        409,
        415,
        310,
        311,
        312,
        13,
        82,
        81,
        42,
        183,
        78,
    ]

    LEFT_EYE: List[int] = [
        362,
        382,
        381,
        380,
        374,
        373,
        390,
        249,
        263,
        466,
        388,
        387,
        386,
        385,
        384,
        398,
    ]

    LEFT_EYEBROW: List[int] = [336, 296, 334, 293, 300, 276, 283, 282, 295, 285]

    LEFT_IRIS: List[int] = [473]

    RIGHT_EYE: List[int] = [
        33,
        7,
        163,
        144,
        145,
        153,
        154,
        155,
        133,
        173,
        157,
        158,
        159,
        160,
        161,
        246,
    ]

    RIGHT_EYEBROW: List[int] = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]

    RIGHT_IRIS: List[int] = [468]

    # Specific landmarks for eye aspect ratio
    LEFT_EYE_VERTICAL: List[int] = [386, 374]  # Top, Bottom
    LEFT_EYE_HORIZONTAL: List[int] = [263, 362]  # Inner, Outer
    RIGHT_EYE_VERTICAL: List[int] = [159, 145]  # Top, Bottom
    RIGHT_EYE_HORIZONTAL: List[int] = [133, 33]  # Inner, Outer


@dataclass
class FaceMeshTrackerConfig:
    """Configuration for FaceMeshTracker.

    Parameters
    ----------
    model_path : str, optional
        Path to the face landmarker model file.
        If None, downloads the default model automatically.
    num_faces : int, default=1
        Maximum number of faces to detect.
    min_detection_confidence : float, default=0.5
        Minimum confidence for face detection (0.0 to 1.0).
    min_presence_confidence : float, default=0.5
        Minimum confidence for face presence (0.0 to 1.0).
    min_tracking_confidence : float, default=0.5
        Minimum confidence for face tracking (0.0 to 1.0).
    output_blendshapes : bool, default=False
        Whether to output face blendshapes (for expressions).
    running_mode : str, default="LIVE_STREAM"
        Running mode: "IMAGE" for synchronous, "LIVE_STREAM" for async.
    """

    model_path: Optional[str] = None
    num_faces: int = 1
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    output_blendshapes: bool = False
    running_mode: str = "LIVE_STREAM"


@dataclass
class FaceResult:
    """Result from face mesh detection.

    Attributes
    ----------
    landmarks : list
        478 normalized face landmarks.
    blendshapes : list or None
        Face blendshapes for expression tracking (if enabled).
    """

    landmarks: list
    blendshapes: Optional[list] = None


class FaceMeshTracker:
    """Face mesh detection and tracking using MediaPipe.

    Detects faces and provides 478 landmark points per face,
    including detailed mesh for facial features like eyes, lips, and contours.

    Parameters
    ----------
    config : FaceMeshTrackerConfig, optional
        Configuration object. If None, uses default settings.

    Attributes
    ----------
    detection_result : vision.FaceLandmarkerResult or None
        Latest detection result from MediaPipe.
    is_running : bool
        Whether the tracker has been initialized.

    Examples
    --------
    Basic usage with async detection:

    >>> from nectar.vision import FaceMeshTracker, FaceMeshTrackerConfig
    >>> config = FaceMeshTrackerConfig(num_faces=1)
    >>> tracker = FaceMeshTracker(config)
    >>> tracker.start()
    >>> frame = cv2.imread("face.jpg")
    >>> tracker.detect(frame, draw=True)
    >>> cv2.imshow("Face Mesh", frame)

    With context manager:

    >>> with FaceMeshTracker() as tracker:
    ...     frame = cv2.imread("face.jpg")
    ...     tracker.detect(frame)
    ...     landmarks = tracker.get_landmarks()

    Eye tracking example:

    >>> from nectar.vision.algorithms.pose.face_tracker import FaceLandmarkRegion
    >>> with FaceMeshTracker() as tracker:
    ...     tracker.detect(frame)
    ...     left_eye = tracker.get_landmarks(
    ...         landmark_ids=FaceLandmarkRegion.LEFT_EYE
    ...     )

    References
    ----------
    .. [1] MediaPipe Face Landmarker
       https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
    """

    # Model download URL
    _MODEL_URL = (
        "https://storage.googleapis.com/mediapipe-models/"
        "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
    )

    def __init__(self, config: Optional[FaceMeshTrackerConfig] = None):
        if not MEDIAPIPE_AVAILABLE:
            raise ImportError(
                "mediapipe is required for FaceMeshTracker. "
                "Install with: pip install nectar-sdk[vision]"
            )

        self._config = config or FaceMeshTrackerConfig()
        self._detector: Optional[vision.FaceLandmarker] = None
        self._detection_result: Optional[vision.FaceLandmarkerResult] = None
        self._is_running = False

        self._mp_face_mesh = mp.solutions.face_mesh
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._face_tesselation = self._mp_face_mesh.FACEMESH_TESSELATION
        self._face_contours = (
            self._mp_face_mesh.FACEMESH_CONTOURS
            | self._mp_face_mesh.FACEMESH_LEFT_EYE
            | self._mp_face_mesh.FACEMESH_RIGHT_EYE
            | self._mp_face_mesh.FACEMESH_LEFT_EYEBROW
            | self._mp_face_mesh.FACEMESH_RIGHT_EYEBROW
            | self._mp_face_mesh.FACEMESH_LIPS
        )
        self._face_irises = (
            self._mp_face_mesh.FACEMESH_LEFT_IRIS | self._mp_face_mesh.FACEMESH_RIGHT_IRIS
        )

    def __enter__(self) -> "FaceMeshTracker":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @property
    def detection_result(self) -> Optional[vision.FaceLandmarkerResult]:
        """Latest detection result."""
        return self._detection_result

    @property
    def is_running(self) -> bool:
        """Whether tracker is initialized."""
        return self._is_running

    def start(self) -> None:
        """Initialize the face landmarker detector.

        Downloads the model if not available locally.

        Raises
        ------
        RuntimeError
            If model download fails or detector initialization fails.
        """
        model_path = self._config.model_path
        if model_path is None:
            model_path = self._download_model()

        running_mode = (
            vision.RunningMode.LIVE_STREAM
            if self._config.running_mode == "LIVE_STREAM"
            else vision.RunningMode.IMAGE
        )

        base_options = python.BaseOptions(model_asset_path=model_path)

        options_kwargs = {
            "base_options": base_options,
            "running_mode": running_mode,
            "num_faces": self._config.num_faces,
            "min_face_detection_confidence": self._config.min_detection_confidence,
            "min_face_presence_confidence": self._config.min_presence_confidence,
            "min_tracking_confidence": self._config.min_tracking_confidence,
            "output_face_blendshapes": self._config.output_blendshapes,
        }

        if running_mode == vision.RunningMode.LIVE_STREAM:
            options_kwargs["result_callback"] = self._save_result

        options = vision.FaceLandmarkerOptions(**options_kwargs)
        self._detector = vision.FaceLandmarker.create_from_options(options)
        self._is_running = True

    def close(self) -> None:
        """Release detector resources."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        self._detection_result = None
        self._is_running = False

    def detect(self, frame: np.ndarray, draw: bool = False) -> np.ndarray:
        """Detect face mesh in the image.

        Parameters
        ----------
        frame : np.ndarray
            Input BGR image.
        draw : bool, default=False
            Whether to draw the face mesh on the image.

        Returns
        -------
        np.ndarray
            Image with mesh drawn if draw=True, otherwise original.

        Raises
        ------
        RuntimeError
            If tracker not started (call start() first).
        """
        if not self._is_running:
            raise RuntimeError("Tracker not started. Call start() first.")

        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        if self._config.running_mode == "LIVE_STREAM":
            self._detector.detect_async(mp_image, int(time.time_ns() // 1_000_000))
        else:
            self._detection_result = self._detector.detect(mp_image)

        return self.draw_landmarks(frame) if draw else frame

    def draw_landmarks(
        self,
        image: np.ndarray,
        draw_tesselation: bool = True,
        draw_contours: bool = True,
        draw_irises: bool = True,
    ) -> np.ndarray:
        """Draw face mesh on image.

        Parameters
        ----------
        image : np.ndarray
            Input BGR image to annotate.
        draw_tesselation : bool, default=True
            Draw the full face mesh tesselation.
        draw_contours : bool, default=True
            Draw face contours (outline, eyes, lips).
        draw_irises : bool, default=True
            Draw iris landmarks.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        if self._detection_result is None:
            return image

        for face_landmarks in self._detection_result.face_landmarks:
            # Convert to protobuf format for drawing (MediaPipe 0.10.18)
            face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            face_landmarks_proto.landmark.extend(
                [
                    landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z)
                    for landmark in face_landmarks
                ]
            )

            if draw_tesselation:
                self._mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks_proto,
                    connections=self._face_tesselation,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self._mp_drawing_styles.get_default_face_mesh_tesselation_style(),
                )

            if draw_contours:
                self._mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks_proto,
                    connections=self._face_contours,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self._mp_drawing_styles.get_default_face_mesh_contours_style(),
                )

            if draw_irises:
                self._mp_drawing.draw_landmarks(
                    image=image,
                    landmark_list=face_landmarks_proto,
                    connections=self._face_irises,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=self._mp_drawing_styles.get_default_face_mesh_iris_connections_style(),
                )

        return image

    def draw_region(
        self,
        image: np.ndarray,
        landmark_indices: List[int],
        color: Tuple[int, int, int] = (0, 255, 0),
        radius: int = 1,
        thickness: int = 1,
        face_idx: int = 0,
    ) -> np.ndarray:
        """Draw circles on specific landmarks.

        Parameters
        ----------
        image : np.ndarray
            Input BGR image to annotate.
        landmark_indices : list of int
            Indices of landmarks to draw.
        color : tuple, default=(0, 255, 0)
            BGR color for the circles.
        radius : int, default=1
            Radius of the circles in pixels.
        thickness : int, default=1
            Thickness of the circles (-1 for filled).
        face_idx : int, default=0
            Index of the face to draw.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        if self._detection_result is None:
            return image

        if face_idx >= len(self._detection_result.face_landmarks):
            return image

        face_landmarks = self._detection_result.face_landmarks[face_idx]
        height, width = image.shape[:2]

        for idx in landmark_indices:
            if idx < len(face_landmarks):
                lm = face_landmarks[idx]
                x = int(lm.x * width)
                y = int(lm.y * height)
                cv2.circle(image, (x, y), radius, color, thickness)

        return image

    def get_faces(self) -> List[FaceResult]:
        """Get detected faces as structured results.

        Returns
        -------
        list of FaceResult
            List of detected faces with landmarks.
        """
        if self._detection_result is None:
            return []

        results = []
        for idx, face_landmarks in enumerate(self._detection_result.face_landmarks):
            blendshapes = None
            if self._config.output_blendshapes and self._detection_result.face_blendshapes:
                blendshapes = self._detection_result.face_blendshapes[idx]

            results.append(
                FaceResult(
                    landmarks=face_landmarks,
                    blendshapes=blendshapes,
                )
            )
        return results

    def get_landmarks(self, face_idx: int = 0, landmark_ids: Optional[List[int]] = None) -> list:
        """Get face landmarks for a specific face.

        Parameters
        ----------
        face_idx : int, default=0
            Index of the face.
        landmark_ids : list of int, optional
            Specific landmark indices to return. If None, returns all 478.

        Returns
        -------
        list
            List of landmarks (normalized coordinates).
        """
        if self._detection_result is None:
            return []

        if face_idx >= len(self._detection_result.face_landmarks):
            return []

        landmarks = self._detection_result.face_landmarks[face_idx]

        if landmark_ids is None:
            return list(landmarks)

        return [landmarks[idx] for idx in landmark_ids if idx < len(landmarks)]

    def get_eye_aspect_ratio(self, eye: str = "left", face_idx: int = 0) -> float:
        """Calculate Eye Aspect Ratio (EAR) for blink detection.

        EAR is the ratio of eye height to width. It decreases
        significantly during blinks.

        Parameters
        ----------
        eye : str, default="left"
            Which eye: "left" or "right".
        face_idx : int, default=0
            Index of the face.

        Returns
        -------
        float
            Eye aspect ratio. Typical values: ~0.25 open, ~0.05 closed.

        References
        ----------
        .. [1] Soukupová, T., & Čech, J. (2016). Eye blink detection using
               facial landmarks. 21st Computer Vision Winter Workshop.
        """
        if self._detection_result is None:
            return 0.0

        if face_idx >= len(self._detection_result.face_landmarks):
            return 0.0

        landmarks = self._detection_result.face_landmarks[face_idx]

        if eye == "left":
            vertical = FaceLandmarkRegion.LEFT_EYE_VERTICAL
            horizontal = FaceLandmarkRegion.LEFT_EYE_HORIZONTAL
        else:
            vertical = FaceLandmarkRegion.RIGHT_EYE_VERTICAL
            horizontal = FaceLandmarkRegion.RIGHT_EYE_HORIZONTAL

        # Calculate vertical distance
        top = landmarks[vertical[0]]
        bottom = landmarks[vertical[1]]
        v_dist = np.sqrt((top.x - bottom.x) ** 2 + (top.y - bottom.y) ** 2)

        # Calculate horizontal distance
        inner = landmarks[horizontal[0]]
        outer = landmarks[horizontal[1]]
        h_dist = np.sqrt((inner.x - outer.x) ** 2 + (inner.y - outer.y) ** 2)

        if h_dist == 0:
            return 0.0

        return v_dist / h_dist

    def get_mouth_aspect_ratio(self, face_idx: int = 0) -> float:
        """Calculate Mouth Aspect Ratio (MAR) for mouth open detection.

        Parameters
        ----------
        face_idx : int, default=0
            Index of the face.

        Returns
        -------
        float
            Mouth aspect ratio. Higher values indicate more open mouth.
        """
        if self._detection_result is None:
            return 0.0

        if face_idx >= len(self._detection_result.face_landmarks):
            return 0.0

        landmarks = self._detection_result.face_landmarks[face_idx]

        # Upper and lower lip centers
        upper_lip = landmarks[13]  # Upper lip center
        lower_lip = landmarks[14]  # Lower lip center
        left_corner = landmarks[78]
        right_corner = landmarks[308]

        v_dist = np.sqrt((upper_lip.x - lower_lip.x) ** 2 + (upper_lip.y - lower_lip.y) ** 2)
        h_dist = np.sqrt(
            (left_corner.x - right_corner.x) ** 2 + (left_corner.y - right_corner.y) ** 2
        )

        if h_dist == 0:
            return 0.0

        return v_dist / h_dist

    def _save_result(
        self,
        result: vision.FaceLandmarkerResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        """Callback for async detection mode."""
        self._detection_result = result if result.face_landmarks else None

    @classmethod
    def _download_model(cls) -> str:
        """Download the face landmarker model.

        Returns
        -------
        str
            Path to the downloaded model file.

        Raises
        ------
        RuntimeError
            If download fails.
        """
        cache_dir = Path.home() / ".cache" / "nectar" / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)

        model_path = cache_dir / "face_landmarker.task"

        if model_path.exists():
            return str(model_path)

        try:
            urllib.request.urlretrieve(cls._MODEL_URL, model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download face landmarker model: {e}")

        return str(model_path)


def main():
    """Demo function for face mesh tracking."""
    cap = cv2.VideoCapture(0)

    config = FaceMeshTrackerConfig(num_faces=1, running_mode="LIVE_STREAM")

    with FaceMeshTracker(config) as tracker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            tracker.detect(frame, draw=True)

            # Display eye aspect ratios
            left_ear = tracker.get_eye_aspect_ratio("left")
            right_ear = tracker.get_eye_aspect_ratio("right")

            cv2.putText(
                frame,
                f"L-EAR: {left_ear:.3f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                f"R-EAR: {right_ear:.3f}",
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Face Mesh", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
