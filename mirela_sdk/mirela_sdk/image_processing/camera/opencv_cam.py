from typing import Optional
import cv2
import numpy as np

from .abstract_cam import AbstractCam


class OpenCVCam(AbstractCam):
    def __init__(
        self,
        device_index: int | str = 0,
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[int] = 30,
        fourcc: Optional[str] = "MJPG",
        autofocus: Optional[bool] = None,
        focus: Optional[int] = None,
        name: str = "opencv_cam",
    ) -> None:
        super().__init__(name=name)
        self._device_index = device_index
        self._width = width
        self._height = height
        self._fps = fps
        self._fourcc = fourcc
        self._autofocus = autofocus
        self._focus = focus
        self._cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_V4L2)
        if self._fourcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc))
        if self._fps is not None:
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        if self._width is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        if self._height is not None:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        if self._autofocus is not None:
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1 if self._autofocus else 0)
        if self._focus is not None:
            # Some cameras accept manual focus when autofocus disabled
            self._cap.set(cv2.CAP_PROP_FOCUS, self._focus)
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