from typing import Optional, Tuple
import numpy as np

from .abstract_cam import DepthCam

try:
    import pyrealsense2 as rs
except Exception as e:  
    rs = None


class RealsenseCam(DepthCam):
    def __init__(
        self,
        *,
        color_res: Tuple[int, int] = (640, 480),
        depth_res: Tuple[int, int] = (640, 480),
        fps: int = 30,
        align_to_color: bool = True,
        name: str = "realsense_cam",
    ) -> None:
        super().__init__(name=name)
        self._color_res = color_res
        self._depth_res = depth_res
        self._fps = fps
        self._align_to_color = align_to_color

        self._pipeline = None
        self._align = None
        self._depth_scale: Optional[float] = None
        self._rgb: Optional[np.ndarray] = None
        self._depth: Optional[np.ndarray] = None

    def start(self) -> None:
        if rs is None:
            raise RuntimeError(
                "pyrealsense2 is not installed. Please install librealsense and pyrealsense2."
            )

        config = rs.config()
        config.enable_stream(
            rs.stream.color,
            self._color_res[0],
            self._color_res[1],
            rs.format.bgr8,
            self._fps,
        )
        config.enable_stream(
            rs.stream.depth,
            self._depth_res[0],
            self._depth_res[1],
            rs.format.z16,
            self._fps,
        )

        self._pipeline = rs.pipeline()
        profile = self._pipeline.start(config)

        depth_sensor = profile.get_device().first_depth_sensor()
        self._depth_scale = float(depth_sensor.get_depth_scale())  # meters per unit

        if self._align_to_color:
            self._align = rs.align(rs.stream.color)
        else:
            self._align = None

        self._is_running = True

    def _wait_for_frames(self):
        if not self._pipeline:
            return None
        frames = self._pipeline.wait_for_frames()
        if self._align is not None:
            frames = self._align.process(frames)
        return frames

    def get_frame(self) -> Optional[np.ndarray]:
        frames = self._wait_for_frames()
        if frames is None:
            return None
        color_frame = frames.get_color_frame()
        if not color_frame:
            return None
        self._rgb = np.asanyarray(color_frame.get_data())
        return self._rgb

    def get_depth_frame(self) -> Optional[np.ndarray]:
        frames = self._wait_for_frames()
        if frames is None:
            return None
        depth_frame = frames.get_depth_frame()
        if not depth_frame:
            return None
        depth_image = np.asanyarray(depth_frame.get_data())  # in raw depth units
        if self._depth_scale is None:
            return None
        self._depth = depth_image.astype(np.float32) * self._depth_scale  # meters
        return self._depth

    def get_distance(self, u: int, v: int) -> Optional[float]:
        # Ensure we have a recent aligned depth frame
        frames = self._wait_for_frames()
        if frames is None:
            return None
        depth_frame = frames.get_depth_frame()
        if not depth_frame:
            return None
        try:
            distance_m = float(depth_frame.get_distance(int(u), int(v)))
        except Exception:
            return None
        return distance_m

    def close(self) -> None:
        if self._pipeline:
            try:
                self._pipeline.stop()
            except Exception:
                pass
            self._pipeline = None
        self._is_running = False
