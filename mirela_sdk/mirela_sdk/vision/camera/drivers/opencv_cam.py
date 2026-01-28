from typing import Optional, Dict, Any
from threading import Thread, Lock, Event
import cv2
import numpy as np

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.config import OpenCVConfig


class OpenCVCam(AbstractCam):
    """
    OpenCV-based camera driver using V4L2 backend.

    Parameters
    ----------
    config : OpenCVConfig
        Camera configuration.
    
    Notes
    -----
    Supports two capture modes:
    - Synchronous (default): get_frame() blocks until frame is captured
    - Threaded: Background thread captures frames continuously

    Use threaded=True when:
    - Timer-based polling causes frame drops
    - You need consistent FPS regardless of processing time
    - Multiple consumers need the latest frame

    Use synchronous (default) when:
    - Simple single-consumer use case
    - Lower memory overhead preferred
    - Processing is fast enough to keep up with camera FPS
    """

    def __init__(self, config: OpenCVConfig) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None
        self._actual_settings: Dict[str, Any] = {}

        self._threaded = config.threaded
        self._frame: Optional[np.ndarray] = None
        self._frame_lock: Optional[Lock] = None
        self._capture_thread: Optional[Thread] = None
        self._stop_thread = False
        self._new_frame_event: Optional[Event] = None
        self._frame_id: int = 0
        self._last_consumed_id: int = 0

    def start(self) -> None:
        """Open and configure the camera."""
        self._cap = cv2.VideoCapture(self._config.device_index, cv2.CAP_V4L2)

        if not self._cap.isOpened():
            raise RuntimeError(
                f"Failed to open camera at index {self._config.device_index}"
            )

        if self._config.fourcc:
            fourcc_code = cv2.VideoWriter_fourcc(*self._config.fourcc)
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc_code)
        if self._config.width is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
        if self._config.height is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
        if self._config.fps is not None:
            self._cap.set(cv2.CAP_PROP_FPS, self._config.fps)
        if self._config.buffer_size is not None:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self._config.buffer_size)
        if self._config.autofocus is not None:
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self._config.autofocus else 0)
        if self._config.focus is not None:
            self._cap.set(cv2.CAP_PROP_FOCUS, self._config.focus)

        # Query actual settings
        self._actual_settings = {
            "width": int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": self._cap.get(cv2.CAP_PROP_FPS),
            "buffer_size": int(self._cap.get(cv2.CAP_PROP_BUFFERSIZE)),
            "fourcc": self._decode_fourcc(int(self._cap.get(cv2.CAP_PROP_FOURCC))),
            "threaded": self._threaded,
        }

        if self._threaded:
            self._frame_lock = Lock()
            self._new_frame_event = Event()
            self._stop_thread = False
            self._capture_thread = Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()

        self._is_running = True

    def _capture_loop(self) -> None:
        """Background thread: continuously capture frames at camera rate."""
        while not self._stop_thread and self._cap is not None:
            ok, frame = self._cap.read()
            if ok and self._frame_lock is not None:
                with self._frame_lock:
                    self._frame = frame
                    self._frame_id += 1
                if self._new_frame_event:
                    self._new_frame_event.set()

    @property
    def actual_settings(self) -> Dict[str, Any]:
        """Return actual camera settings after initialization."""
        return self._actual_settings

    @property
    def is_threaded(self) -> bool:
        """Return True if using threaded capture mode."""
        return self._threaded

    @staticmethod
    def _decode_fourcc(fourcc: int) -> str:
        """Decode fourcc integer to string."""
        return "".join([chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)])

    def get_frame(
        self, wait_for_new: bool = False, timeout: float = 0.1
    ) -> Optional[np.ndarray]:
        """
        Get a frame from the camera.

        Parameters
        ----------
        wait_for_new : bool, optional
            Only used in threaded mode. If True, blocks until a new frame
            arrives. If False, returns the latest buffered frame immediately.
            Ignored in synchronous mode.
        timeout : float, optional
            Max seconds to wait when wait_for_new=True. Default is 0.1s.

        Returns
        -------
        np.ndarray or None
            BGR image frame, or None if capture failed or timeout.
        """
        if not self._cap:
            return None

        if self._threaded:
            if wait_for_new and self._new_frame_event and self._frame_lock:
                with self._frame_lock:
                    if (
                        self._frame_id > self._last_consumed_id
                        and self._frame is not None
                    ):
                        self._last_consumed_id = self._frame_id
                        return self._frame.copy()

                # Wait for next frame
                self._new_frame_event.clear()
                if not self._new_frame_event.wait(timeout):
                    return None

            if self._frame_lock:
                with self._frame_lock:
                    if self._frame is not None:
                        self._last_consumed_id = self._frame_id
                        return self._frame.copy()
            return None
        else:
            ok, frame = self._cap.read()
            return frame if ok else None

    def close(self) -> None:
        """Release camera resources."""
        if self._threaded:
            self._stop_thread = True
            if self._capture_thread is not None:
                self._capture_thread.join(timeout=1.0)
                self._capture_thread = None

        if self._cap:
            self._cap.release()
            self._cap = None

        self._is_running = False
