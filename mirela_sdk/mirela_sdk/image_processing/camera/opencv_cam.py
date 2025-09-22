from typing import Optional
import cv2
import numpy as np

from .abstract_cam import AbstractCam
from .camera_config import OpenCVConfig


class OpenCVCam(AbstractCam):
    def __init__(self, config: OpenCVConfig) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._config.device_index, cv2.CAP_V4L2)
        if self._config.fourcc:
            self._cap.set(
                cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._config.fourcc)
            )
        if self._config.fps is not None:
            self._cap.set(cv2.CAP_PROP_FPS, self._config.fps)
        if self._config.width is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.width)
        if self._config.height is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.height)
        if self._config.autofocus is not None:
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self._config.autofocus else 0)
        if self._config.focus is not None:
            # Some cameras accept manual focus when autofocus disabled
            self._cap.set(cv2.CAP_PROP_FOCUS, self._config.focus)
        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        if not self._cap:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None
        self._is_running = False