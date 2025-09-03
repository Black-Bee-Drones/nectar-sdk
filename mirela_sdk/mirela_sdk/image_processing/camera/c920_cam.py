from typing import Optional
import subprocess
import re
import cv2
import numpy as np

from .abstract_cam import AbstractCam


class C920Cam(AbstractCam):
    C920_CTRL_MAP = {
        "HD Pro Webcam C920": "focus_automatic_continuous=0",
        "Logi Webcam C920e": "focus_auto=0",
    }

    def __init__(
        self,
        *,
        profile: int = 1,
        fallback_device_index: int | str = 0,
        name: str = "c920_cam",
    ) -> None:
        super().__init__(name=name)
        self._profile = profile  # 0: 640x480, 1: 1280x720, 2: 1920x1080
        self._fallback_device_index = fallback_device_index
        self._device: Optional[str] = None
        self._cap: Optional[cv2.VideoCapture] = None

    def _find_device_and_ctrl(self) -> tuple[Optional[str], Optional[str]]:
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--list-devices"], capture_output=True, text=True
            )
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
        if device and ctrl_param:
            try:
                subprocess.run(["v4l2-ctl", "-d", device, "--set-ctrl=" + ctrl_param])
            except Exception:
                pass

    def _profile_resolution(self) -> tuple[int, int]:
        if self._profile == 0:
            return 640, 480
        if self._profile == 2:
            return 1920, 1080
        return 1280, 720

    def start(self) -> None:
        device, ctrl_param = self._find_device_and_ctrl()
        self._device = device or self._fallback_device_index

        self._apply_controls(device, ctrl_param)

        width, height = self._profile_resolution()

        self._cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if self._cap is None or not self._cap.isOpened():
            # Fallback to plain VideoCapture
            self._cap = cv2.VideoCapture(self._fallback_device_index)

        if self._cap is not None:
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._cap.set(cv2.CAP_PROP_FPS, 30)
            # Try to disable autofocus and set focus to 0 (some models only)
            try:
                self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                self._cap.set(cv2.CAP_PROP_FOCUS, 0)
            except Exception:
                pass

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
