from typing import Optional
import cv2
import numpy as np

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.config import IMX219Config


class IMX219Cam(AbstractCam):

    def __init__(self, config: IMX219Config) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None

    def _build_gstreamer_pipeline(self) -> str:
        return (
            f"nvarguscamerasrc sensor-id={self._config.sensor_id} ! "
            f"video/x-raw(memory:NVMM), width=(int){self._config.width}, height=(int){self._config.height}, "
            f"framerate=(fraction){self._config.fps}/1, format=(string)NV12 ! "
            f"nvvidconv flip-method={self._config.flip} ! "
            f"video/x-raw, width=(int){self._config.width}, height=(int){self._config.height}, format=(string)BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=(string)BGR ! "
            f"appsink max-buffer=1 drop=true sync=false"
        )

    def start(self) -> None:
        gstreamer_pipeline = self._build_gstreamer_pipeline()
        self._cap = cv2.VideoCapture(gstreamer_pipeline, cv2.CAP_GSTREAMER)

        if not self._cap.isOpened():
            raise RuntimeError(
                f"Failed to open IMX219 camera (sensor_id={self._config.sensor_id})"
            )

        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        if not self._cap:
            return None

        ret, frame = self._cap.read()
        return frame if ret else None

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

        self._is_running = False
