from typing import Optional
import numpy as np
import cv2

from .abstract_cam import AbstractCam


class FileImageCam(AbstractCam):
    def __init__(self, image_path: str, *, name: str = "file_image_cam") -> None:
        super().__init__(name=name)
        self._path = image_path
        self._frame: Optional[np.ndarray] = None

    def start(self) -> None:
        self._frame = cv2.imread(self._path)
        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        return self._frame

    def close(self) -> None:
        self._is_running = False 