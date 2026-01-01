from typing import Optional
import cv2
import numpy as np

from .abstract_cam import AbstractCam
from .camera_config import IMX219Config


class IMX219Cam(AbstractCam):
    """
    Camera implementation for IMX219 sensor (like Raspberry Pi V2 camera) 
    using the GStreamer pipeline.
    """
    
    def __init__(self, config: IMX219Config) -> None:
        """
        Initialize the IMX219 camera.
        
        Args:
            config: Configuration object for the IMX219 camera.
        """
        super().__init__(name=config.name)
        self._config = config
        self._cap: Optional[cv2.VideoCapture] = None
    
    def _build_gstreamer_pipeline(self) -> str:
        """Build the GStreamer pipeline string for IMX219 camera."""
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
        """Start the camera with GStreamer pipeline."""
        gstreamer_pipeline = self._build_gstreamer_pipeline()
        self._cap = cv2.VideoCapture(gstreamer_pipeline, cv2.CAP_GSTREAMER)
        
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open IMX219 camera (sensor_id={self._config.sensor_id})")
        
        self._is_running = True
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame from the camera."""
        if not self._cap:
            return None
        
        ret, frame = self._cap.read()
        return frame if ret else None
    
    def close(self) -> None:
        """Release camera resources."""
        if self._cap:
            self._cap.release()
            self._cap = None
        
        self._is_running = False
