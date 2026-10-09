from threading import Event
from typing import Optional

import cv2
import numpy as np

from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import FileImageConfig


class FileImageCam(AbstractCam):
    """
    Camera driver for static image files.

    Loads an image from disk once and returns the same frame on every
    get_frame() call. ``wait_for_new=True`` yields the frame once per
    load/reload, then waits until timeout.

    Parameters
    ----------
    config : FileImageConfig
        Configuration with image file path.
    """

    def __init__(self, config: FileImageConfig) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._frame: Optional[np.ndarray] = None
        self._new = Event()

    def start(self) -> None:
        """Load image from configured path."""
        self._frame = cv2.imread(self._config.path)
        if self._frame is None:
            raise FileNotFoundError(f"Could not load image: {self._config.path}")
        self._new.set()
        self._is_running = True

    def get_frame(self, wait_for_new: bool = False, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Return the loaded image.

        Parameters
        ----------
        wait_for_new : bool, optional
            If True, return a newly loaded frame or wait until timeout.
        timeout : float, optional
            Max seconds to wait when ``wait_for_new`` is True.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if not loaded or wait timed out.
        """
        if wait_for_new:
            if not self._new.wait(timeout):
                return None
            self._new.clear()
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
        self._new.set()
        return True

    def close(self) -> None:
        """Mark camera as stopped."""
        self._is_running = False
        self._frame = None
        self._new.set()
