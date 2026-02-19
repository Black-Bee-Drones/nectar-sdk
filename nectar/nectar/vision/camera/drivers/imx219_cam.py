from typing import Optional
from time import sleep

import cv2
import numpy as np

from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import IMX219Config


class IMX219Cam(AbstractCam):
    """
    Camera driver for IMX219 CSI cameras.

    Parameters
    ----------
    config : IMX219Config
        Configuration with sensor ID, resolution, FPS, flip, and brightness settings.

    Notes
    -----
    Uses GStreamer pipeline with nvarguscamerasrc for hardware-accelerated capture.

    Requires GStreamer and NVIDIA multimedia libraries. The pipeline uses
    NVMM memory for zero-copy GPU processing.

    Brightness is applied via the ``videobalance`` GStreamer element and can be
    adjusted at runtime via :meth:`set_brightness`; the method restarts the
    capture pipeline to apply the new settings.
    """

    def __init__(self, config: IMX219Config) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None
        self._brightness: Optional[float] = config.brightness # Mutable runtime override

    def _build_gstreamer_pipeline(self) -> str:
        """Build GStreamer pipeline string for nvarguscamerasrc."""
        
        brightness_element = ""
        if self._brightness is not None:
            brightness_element = f"videobalance brightness={self._brightness:.4f} ! "

        return (
            f"nvarguscamerasrc sensor-id={self._config.sensor_id} ! "
            f"video/x-raw(memory:NVMM), width=(int){self._config.width}, height=(int){self._config.height}, "
            f"framerate=(fraction){self._config.fps}/1, format=(string)NV12 ! "
            f"nvvidconv flip-method={self._config.flip} ! "
            f"video/x-raw, width=(int){self._config.width}, height=(int){self._config.height}, format=(string)BGRx ! "
            f"videoconvert ! "
            f"{brightness_element}"
            f"video/x-raw, format=(string)BGR ! "
            f"appsink max-buffer=1 drop=true sync=false"
        )

    def start(self) -> None:
        """
        Initialize GStreamer pipeline and start capture.

        Raises
        ------
        RuntimeError
            If camera cannot be opened (CSI not connected or configured).
        """
        gstreamer_pipeline = self._build_gstreamer_pipeline()
        self._cap = cv2.VideoCapture(gstreamer_pipeline, cv2.CAP_GSTREAMER)

        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open IMX219 camera (sensor_id={self._config.sensor_id})")

        self._is_running = True

    def set_brightness(self, brightness: Optional[float]) -> None:
        """
        Set brightness adjustment, then restart the pipeline.

        Parameters
        ----------
        brightness : float or None
            Brightness offset in the range ``[-1.0, 1.0]``.
            ``0.0`` is neutral; negative values darken, positive values brighten.
            Pass ``None`` to remove the ``videobalance`` element entirely.

        Raises
        ------
        ValueError
            If ``brightness`` is outside ``[-1.0, 1.0]``.
        RuntimeError
            If the pipeline cannot be reopened after applying new settings.
        """
        if brightness is not None and not (-1.0 <= brightness <= 1.0):
            raise ValueError(f"brightness must be in [-1.0, 1.0], got {brightness}")
        self._brightness = brightness
        if self._is_running:
            self._restart_pipeline()

    def _restart_pipeline(self) -> None:
        """Release and reopen the GStreamer pipeline with current settings."""
        if self._is_running:
            self.close()
            sleep(0.2) # Short delay to ensure resources are released before restarting
        self.start()

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Capture frame from GStreamer pipeline.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if capture failed.
        """
        if not self._cap:
            return None

        ret, frame = self._cap.read()
        return frame if ret else None

    def close(self) -> None:
        """Release GStreamer pipeline resources."""
        if self._cap:
            self._cap.release()
            self._cap = None

        self._is_running = False
