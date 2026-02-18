import re
import subprocess
from typing import Optional, Tuple

import cv2
import numpy as np

from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import C920Config


class C920Cam(AbstractCam):
    """
    Camera driver for Logitech C920/C920e webcams.

    Parameters
    ----------
    config : C920Config
        Configuration with profile (resolution) and fallback device index.

    Attributes
    ----------
    C920_CTRL_MAP : dict
        Mapping of camera model names to v4l2 control parameters.

    Notes
    -----
    Requires v4l2-utils package for auto-detection. Profile settings:
    - 0: 640x480
    - 1: 1280x720 (default)
    - 2: 1920x1080
    """

    C920_CTRL_MAP = {
        "HD Pro Webcam C920": "focus_automatic_continuous=0",
        "Logi Webcam C920e": "focus_auto=0",
    }

    def __init__(self, config: C920Config) -> None:
        super().__init__(name=config.name)
        self._config = config
        self._device: Optional[str] = None
        self._cap: Optional[cv2.VideoCapture] = None

    def _find_device_and_ctrl(self) -> Tuple[Optional[str], Optional[str]]:
        """Detect C920 device path and control parameter via v4l2-ctl."""
        try:
            result = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True)
            lines = result.stdout.splitlines()
        except Exception:
            return None, None

        device = None
        ctrl_param = None
        for i, line in enumerate(lines):
            for model_name, param in self.C920_CTRL_MAP.items():
                if model_name in line:
                    ctrl_param = param
                    j = i + 1
                    while j < len(lines) and lines[j].startswith("\t"):
                        match = re.search(r"(/dev/video\d+)", lines[j])
                        if match:
                            device = match.group(1)
                            break
                        j += 1
                    break
            if device and ctrl_param:
                break
        return device, ctrl_param

    def _apply_controls(self, device: str, ctrl_param: Optional[str]) -> None:
        """Apply v4l2 control settings (disable autofocus)."""
        if device and ctrl_param:
            try:
                subprocess.run(["v4l2-ctl", "-d", device, "--set-ctrl=" + ctrl_param])
            except Exception:
                pass

    def _profile_resolution(self) -> Tuple[int, int]:
        """Get resolution for configured profile."""
        if self._config.profile == 0:
            return 640, 480
        if self._config.profile == 2:
            return 1920, 1080
        return 1280, 720

    def start(self) -> None:
        """
        Detect device, apply settings, and start capture.

        Auto-detects C920 via v4l2-ctl. Falls back to fallback_device_index
        if detection fails. Configures MJPG format and disables autofocus.
        """
        device, ctrl_param = self._find_device_and_ctrl()
        self._device = device or self._config.fallback_device_index

        self._apply_controls(device, ctrl_param)

        width, height = self._profile_resolution()

        self._cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if self._cap is None or not self._cap.isOpened():
            self._cap = cv2.VideoCapture(self._config.fallback_device_index)

        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._cap.set(cv2.CAP_PROP_FPS, 30)
            try:
                self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                self._cap.set(cv2.CAP_PROP_FOCUS, 0)
            except Exception:
                pass

        self._is_running = True

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Capture frame from webcam.

        Returns
        -------
        np.ndarray or None
            BGR image, or None if capture failed.
        """
        if not self._cap:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        """Release webcam resources."""
        if self._cap:
            self._cap.release()
            self._cap = None
        self._is_running = False
