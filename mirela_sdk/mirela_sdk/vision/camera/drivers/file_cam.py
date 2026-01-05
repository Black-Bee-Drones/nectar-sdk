from typing import Optional
import numpy as np
import cv2

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.config import FileImageConfig


class FileImageCam(AbstractCam):
    """
    Camera driver for static image files.

    Loads an image from disk and returns it on every get_frame() call.
    Useful for testing and offline processing.

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
        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Return the loaded image.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if file could not be read.
        """
        return self._frame

    def close(self) -> None:
        """Mark camera as stopped."""
        self._is_running = False
