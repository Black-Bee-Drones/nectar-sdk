import math
import urllib.request
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import (
    HandLandmarksConnections,
)

try:
    from mediapipe.tasks.python.vision import (
        drawing_styles as mp_styles,
    )
    from mediapipe.tasks.python.vision import (
        drawing_utils as mp_drawing,
    )
except ImportError:
    from mediapipe.python.solutions import (
        drawing_styles as mp_styles,
    )
    from mediapipe.python.solutions import (
        drawing_utils as mp_drawing,
    )


class HandLandmark(IntEnum):
    """MediaPipe hand landmark indices.

    Reference: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
    """

    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_FINGER_MCP = 5
    INDEX_FINGER_PIP = 6
    INDEX_FINGER_DIP = 7
    INDEX_FINGER_TIP = 8
    MIDDLE_FINGER_MCP = 9
    MIDDLE_FINGER_PIP = 10
    MIDDLE_FINGER_DIP = 11
    MIDDLE_FINGER_TIP = 12
    RING_FINGER_MCP = 13
    RING_FINGER_PIP = 14
    RING_FINGER_DIP = 15
    RING_FINGER_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


@dataclass
class HandTrackerConfig:
    """Configuration for HandTracker.

    Parameters
    ----------
    model_path : str, optional
        Path to the hand landmarker model file.
        If None, downloads the default model automatically.
    num_hands : int, default=2
        Maximum number of hands to detect.
    min_detection_confidence : float, default=0.5
        Minimum confidence for hand detection (0.0 to 1.0).
    min_presence_confidence : float, default=0.5
        Minimum confidence for hand presence (0.0 to 1.0).
    min_tracking_confidence : float, default=0.5
        Minimum confidence for hand tracking (0.0 to 1.0).
    running_mode : str, default="IMAGE"
        Running mode: "IMAGE" for synchronous, "LIVE_STREAM" for async.
    """

    model_path: Optional[str] = None
    num_hands: int = 2
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    running_mode: str = "IMAGE"


@dataclass
class HandResult:
    """Result from hand detection.

    Attributes
    ----------
    landmarks : list
        Normalized hand landmarks (21 points).
    world_landmarks : list
        3D world landmarks in meters.
    handedness : str
        Hand type: "Left" or "Right".
    confidence : float
        Detection confidence score.
    """

    landmarks: list
    world_landmarks: list
    handedness: str
    confidence: float


class HandTracker:
    """Hand tracking and landmark detection using MediaPipe.

    Detects hands in images and provides 21 landmark points per hand,
    along with handedness classification and gesture recognition utilities.

    Parameters
    ----------
    config : HandTrackerConfig, optional
        Configuration object. If None, uses default settings.

    Attributes
    ----------
    detection_result : vision.HandLandmarkerResult or None
        Latest detection result from MediaPipe.
    is_running : bool
        Whether the tracker has been initialized.

    Examples
    --------
    Basic usage with synchronous detection:

    >>> from nectar.vision import HandTracker, HandTrackerConfig
    >>> config = HandTrackerConfig(num_hands=2)
    >>> tracker = HandTracker(config)
    >>> tracker.start()
    >>> frame = cv2.imread("hand.jpg")
    >>> tracker.detect(frame, draw=True)
    >>> results = tracker.get_hands()
    >>> for hand in results:
    ...     print(f"{hand.handedness}: {hand.confidence:.2f}")
    >>> tracker.close()

    With context manager:

    >>> with HandTracker() as tracker:
    ...     frame = cv2.imread("hand.jpg")
    ...     tracker.detect(frame)
    ...     fingers = tracker.raised_fingers()
    ...     print(f"Raised fingers: {sum(fingers)}")

    References
    ----------
    .. [1] MediaPipe Hand Landmarker
       https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
    """

    # Fingertip landmark indices
    _FINGERTIP_IDS: Tuple[int, ...] = (
        HandLandmark.THUMB_TIP,
        HandLandmark.INDEX_FINGER_TIP,
        HandLandmark.MIDDLE_FINGER_TIP,
        HandLandmark.RING_FINGER_TIP,
        HandLandmark.PINKY_TIP,
    )

    # Model download URL
    _MODEL_URL = (
        "https://storage.googleapis.com/mediapipe-models/"
        "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
    )

    # Depth estimation calibration data (pixel distance → cm)
    _DEPTH_CALIB_X = (
        np.array([300, 245, 200, 170, 145, 130, 112, 103, 93, 87, 80, 75, 70, 67, 62, 59, 57]) / 1.5
    )
    _DEPTH_CALIB_Y = np.array([20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])

    def __init__(self, config: Optional[HandTrackerConfig] = None):
        self._config = config or HandTrackerConfig()
        self._detector: Optional[vision.HandLandmarker] = None
        self._detection_result: Optional[vision.HandLandmarkerResult] = None
        self._is_running = False

        # drawing utilities (Tasks API)
        self._hand_connections = HandLandmarksConnections.HAND_CONNECTIONS

        self._depth_coeffs = np.polyfit(self._DEPTH_CALIB_X, self._DEPTH_CALIB_Y, 2)

        self._handedness_color = (88, 205, 54)  # Green
        self._text_margin = 10

    def __enter__(self) -> "HandTracker":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    @property
    def detection_result(self) -> Optional[vision.HandLandmarkerResult]:
        """Latest detection result."""
        return self._detection_result

    @property
    def is_running(self) -> bool:
        """Whether tracker is initialized."""
        return self._is_running

    def start(self) -> None:
        """Initialize the hand landmarker detector.

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
            "num_hands": self._config.num_hands,
            "min_hand_detection_confidence": self._config.min_detection_confidence,
            "min_hand_presence_confidence": self._config.min_presence_confidence,
            "min_tracking_confidence": self._config.min_tracking_confidence,
        }

        if running_mode == vision.RunningMode.LIVE_STREAM:
            options_kwargs["result_callback"] = self._save_result

        options = vision.HandLandmarkerOptions(**options_kwargs)
        self._detector = vision.HandLandmarker.create_from_options(options)
        self._is_running = True

    def close(self) -> None:
        """Release detector resources."""
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        self._detection_result = None
        self._is_running = False

    def detect(self, frame: np.ndarray, draw: bool = False) -> np.ndarray:
        """Detect hands in the image.

        Parameters
        ----------
        frame : np.ndarray
            Input BGR image.
        draw : bool, default=False
            Whether to draw landmarks on the image.

        Returns
        -------
        np.ndarray
            Image with landmarks drawn if draw=True, otherwise original.

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
            import time

            self._detector.detect_async(mp_image, int(time.time_ns() // 1_000_000))
        else:
            self._detection_result = self._detector.detect(mp_image)

        return self.draw_landmarks(frame) if draw else frame

    def draw_landmarks(self, image: np.ndarray) -> np.ndarray:
        """Draw hand landmarks and handedness labels on image.

        Parameters
        ----------
        image : np.ndarray
            Input BGR image to annotate.

        Returns
        -------
        np.ndarray
            Annotated image.
        """
        if self._detection_result is None:
            return image

        height, width = image.shape[:2]

        for idx, hand_landmarks in enumerate(self._detection_result.hand_landmarks):
            handedness = self._detection_result.handedness[idx]

            # Draw landmarks and connections (Tasks API)
            mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                self._hand_connections,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )

            # Draw handedness label
            x_coords = [lm.x for lm in hand_landmarks]
            y_coords = [lm.y for lm in hand_landmarks]
            text_x = int(min(x_coords) * width)
            text_y = int(min(y_coords) * height) - self._text_margin

            cv2.putText(
                image,
                handedness[0].category_name,
                (text_x, text_y),
                cv2.FONT_HERSHEY_DUPLEX,
                1,
                self._handedness_color,
                1,
                cv2.LINE_AA,
            )

        return image

    def get_hands(self) -> List[HandResult]:
        """Get detected hands as structured results.

        Returns
        -------
        list of HandResult
            List of detected hands with landmarks and metadata.
        """
        if self._detection_result is None:
            return []

        results = []
        for idx, _ in enumerate(self._detection_result.hand_landmarks):
            results.append(
                HandResult(
                    landmarks=self._detection_result.hand_landmarks[idx],
                    world_landmarks=self._detection_result.hand_world_landmarks[idx],
                    handedness=self._detection_result.handedness[idx][0].category_name,
                    confidence=self._detection_result.handedness[idx][0].score,
                )
            )
        return results

    def raised_fingers(self, hand_idx: int = 0) -> List[int]:
        """Detect which fingers are raised.

        Uses world landmarks to determine finger positions relative
        to knuckle joints. Thumb detection accounts for handedness.

        Parameters
        ----------
        hand_idx : int, default=0
            Index of the hand to analyze.

        Returns
        -------
        list of int
            List of 5 values (thumb, index, middle, ring, pinky).
            1 = raised, 0 = lowered.

        Notes
        -----
        Returns empty list if no hands detected or invalid index.
        """
        if self._detection_result is None:
            return []

        if hand_idx >= len(self._detection_result.hand_world_landmarks):
            return []

        world_landmarks = self._detection_result.hand_world_landmarks[hand_idx]
        handedness = self._detection_result.handedness[hand_idx][0].category_name

        fingers = []

        # Thumb (check x-axis, direction depends on handedness)
        thumb_tip = world_landmarks[HandLandmark.THUMB_TIP]
        thumb_ip = world_landmarks[HandLandmark.THUMB_IP]
        if handedness == "Right":
            fingers.append(1 if thumb_tip.x > thumb_ip.x else 0)
        else:
            fingers.append(1 if thumb_tip.x < thumb_ip.x else 0)

        # Other fingers (check y-axis: tip above PIP joint)
        finger_tips = [
            HandLandmark.INDEX_FINGER_TIP,
            HandLandmark.MIDDLE_FINGER_TIP,
            HandLandmark.RING_FINGER_TIP,
            HandLandmark.PINKY_TIP,
        ]
        finger_pips = [
            HandLandmark.INDEX_FINGER_PIP,
            HandLandmark.MIDDLE_FINGER_PIP,
            HandLandmark.RING_FINGER_PIP,
            HandLandmark.PINKY_PIP,
        ]

        for tip_id, pip_id in zip(finger_tips, finger_pips):
            tip_y = world_landmarks[tip_id].y
            pip_y = world_landmarks[pip_id].y
            fingers.append(1 if tip_y < pip_y else 0)

        return fingers

    def get_landmarks(self, hand_idx: int = 0, landmark_ids: Optional[List[int]] = None) -> list:
        """Get normalized landmarks for a specific hand.

        Parameters
        ----------
        hand_idx : int, default=0
            Index of the hand.
        landmark_ids : list of int, optional
            Specific landmark indices to return. If None, returns all 21.

        Returns
        -------
        list
            List of landmarks (normalized coordinates).
        """
        if self._detection_result is None:
            return []

        if hand_idx >= len(self._detection_result.hand_landmarks):
            return []

        landmarks = self._detection_result.hand_landmarks[hand_idx]

        if landmark_ids is None:
            return list(landmarks)

        return [landmarks[idx] for idx in landmark_ids if idx < len(landmarks)]

    def get_world_landmarks(self, hand_idx: int = 0) -> list:
        """Get 3D world landmarks for a specific hand.

        Parameters
        ----------
        hand_idx : int, default=0
            Index of the hand.

        Returns
        -------
        list
            List of world landmarks in meters.
        """
        if self._detection_result is None:
            return []

        if hand_idx >= len(self._detection_result.hand_world_landmarks):
            return []

        return list(self._detection_result.hand_world_landmarks[hand_idx])

    def find_distance(
        self,
        landmark1: int,
        landmark2: int,
        image: np.ndarray,
        hand_idx: int = 0,
        draw: bool = False,
    ) -> Tuple[float, np.ndarray, Tuple[int, int, int, int, int, int]]:
        """Calculate pixel distance between two landmarks.

        Parameters
        ----------
        landmark1 : int
            Index of first landmark.
        landmark2 : int
            Index of second landmark.
        image : np.ndarray
            Image for coordinate scaling and optional drawing.
        hand_idx : int, default=0
            Index of the hand.
        draw : bool, default=False
            Whether to draw the distance line on image.

        Returns
        -------
        distance : float
            Euclidean distance in pixels.
        image : np.ndarray
            Image (with drawing if draw=True).
        coords : tuple
            (x1, y1, x2, y2, cx, cy) - endpoints and center point.
        """
        landmarks = self.get_landmarks(hand_idx, [landmark1, landmark2])

        if len(landmarks) < 2:
            return 0.0, image, (0, 0, 0, 0, 0, 0)

        h, w = image.shape[:2]
        x1, y1 = int(landmarks[0].x * w), int(landmarks[0].y * h)
        x2, y2 = int(landmarks[1].x * w), int(landmarks[1].y * h)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        distance = math.hypot(x2 - x1, y2 - y1)

        if draw:
            color = (255, 0, 255)
            cv2.circle(image, (x1, y1), 10, color, cv2.FILLED)
            cv2.circle(image, (x2, y2), 10, color, cv2.FILLED)
            cv2.line(image, (x1, y1), (x2, y2), color, 3)
            cv2.circle(image, (cx, cy), 10, color, cv2.FILLED)

        return distance, image, (x1, y1, x2, y2, cx, cy)

    def estimate_depth(
        self, hand_idx: int = 0, image_width: int = 640, image_height: int = 480
    ) -> Optional[float]:
        """Estimate hand depth using palm width heuristic.

        Uses the distance between index finger MCP and pinky MCP
        landmarks to approximate distance from camera.

        Parameters
        ----------
        hand_idx : int, default=0
            Index of the hand.
        image_width : int, default=640
            Image width for coordinate scaling.
        image_height : int, default=480
            Image height for coordinate scaling.

        Returns
        -------
        float or None
            Estimated depth in centimeters, or None if no detection.

        Notes
        -----
        This is a rough approximation based on typical hand sizes.
        Accuracy depends on individual hand size and calibration data.
        """
        if self._detection_result is None:
            return None

        if hand_idx >= len(self._detection_result.hand_landmarks):
            return None

        landmarks = self._detection_result.hand_landmarks[hand_idx]

        # Measure palm width (MCP of index to pinky)
        idx_mcp = landmarks[HandLandmark.INDEX_FINGER_MCP]
        pinky_mcp = landmarks[HandLandmark.PINKY_MCP]

        x1, y1 = idx_mcp.x * image_width, idx_mcp.y * image_height
        x2, y2 = pinky_mcp.x * image_width, pinky_mcp.y * image_height

        pixel_distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # Apply polynomial model
        a, b, c = self._depth_coeffs
        return float(a * pixel_distance**2 + b * pixel_distance + c)

    def _save_result(
        self,
        result: vision.HandLandmarkerResult,
        output_image: mp.Image,
        timestamp_ms: int,
    ) -> None:
        """Callback for async detection mode."""
        self._detection_result = result if result.hand_landmarks else None

    @classmethod
    def _download_model(cls) -> str:
        """Download the hand landmarker model.

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

        model_path = cache_dir / "hand_landmarker.task"

        if model_path.exists():
            return str(model_path)

        try:
            urllib.request.urlretrieve(cls._MODEL_URL, model_path)
        except Exception as e:
            raise RuntimeError(f"Failed to download hand landmarker model: {e}")

        return str(model_path)


def main():
    """Demo function for hand tracking."""
    cap = cv2.VideoCapture(0)

    config = HandTrackerConfig(num_hands=2, running_mode="IMAGE")

    with HandTracker(config) as tracker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            tracker.detect(frame, draw=True)

            fingers = tracker.raised_fingers()
            if fingers:
                cv2.putText(
                    frame,
                    f"Fingers: {sum(fingers)}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

            cv2.imshow("Hand Tracker", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
