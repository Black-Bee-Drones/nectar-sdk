from typing import Optional
import numpy as np
import cv2

from .abstract_cam import AbstractCam
from .camera_config import FileImageConfig


class FileImageCam(AbstractCam):
    def __init__(self, config: FileImageConfig) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._frame: Optional[np.ndarray] = None

    def start(self) -> None:
        self._frame = cv2.imread(self._config.path)
        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        return self._frame

    def close(self) -> None:
        self._is_running = False
