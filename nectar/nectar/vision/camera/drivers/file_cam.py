from typing import Optional

import cv2
import numpy as np

from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import FileImageConfig


class FileImageCam(AbstractCam):
    """
    Camera driver for static image files.

    Loads an image from disk once and returns the same frame on every
    get_frame() call.

    Parameters
    ----------
    config : FileImageConfig
        Configuration with image file path.
    """

    def __init__(self, config: FileImageConfig) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._frame: Optional[np.ndarray] = None

    def start(self) -> None:
        """Load image from configured path."""
        self._frame = cv2.imread(self._config.path)
        if self._frame is None:
            raise FileNotFoundError(f"Could not load image: {self._config.path}")
        self._is_running = True

    def get_frame(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Return the loaded image.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if file could not be read.
        """
        return self._frame

    def reload(self) -> bool:
        """
        Reload image from disk.

        Returns
        -------
        bool
            True if reload succeeded, False otherwise.
        """
        frame = cv2.imread(self._config.path)
        if frame is None:
            return False
        self._frame = frame
        return True

    def close(self) -> None:
        """Mark camera as stopped."""
        self._is_running = False
        self._frame = None
