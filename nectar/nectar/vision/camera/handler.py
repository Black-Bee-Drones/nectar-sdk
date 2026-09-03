import threading
import time
import uuid
from typing import Any, Callable, Optional

import cv2
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import Executor
from rclpy.node import Node

from nectar import runtime as nectar_runtime
from nectar.vision.camera.abstract import AbstractCam
from nectar.vision.camera.config import CameraConfig
from nectar.vision.camera.factory import CameraFactory


class ImageHandler:
    """
    High-level camera interface backed by an internal ROS 2 node.

    Manages camera lifecycle, frame capture, and optional image processing.
    A dedicated node is created at construction time and registered with the
    SDK runtime executor.

    Parameters
    ----------
    image_source : str
        Camera source identifier. File path, ROS topic (starts with '/'),
        or registered key ('webcam', 'realsense', 'c920', 'imx219', 'oakd').
    image_processing_callback : callable, optional
        Per-frame callback ``(np.ndarray) -> Any``. The return value is
        propagated by :meth:`take_photo`.
    show_result : str, optional
        OpenCV window name. ``None`` disables display.
    config : CameraConfig, optional
        Camera-specific configuration. Auto-detected if not provided.
    camera : AbstractCam, optional
        Pre-built camera instance. Bypasses factory creation.
    poll_interval : float, default=0.01
        Sleep between grabs for synchronous cameras, and display-timer
        period when ``show_result`` is set.
    frame_timeout : float, optional
        Timeout for async frame waits. Defaults to 0.1 s.
    executor : Executor, optional
        Executor to register the internal node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    """

    def __init__(
        self,
        image_source: str,
        image_processing_callback: Optional[Callable] = None,
        show_result: Optional[str] = None,
        *,
        config: Optional[CameraConfig] = None,
        camera: Optional[AbstractCam] = None,
        poll_interval: float = 0.01,
        frame_timeout: Optional[float] = None,
        executor: Optional[Executor] = None,
    ):
        self.cleaned = False
        nectar_runtime.ensure_context()
        self._node = Node(
            f"nectar_image_handler_{uuid.uuid4().hex[:8]}",
            start_parameter_services=False,
        )
        if executor is not None:
            executor.add_node(self._node)
            self._executor: Optional[Executor] = executor
        else:
            nectar_runtime.add_node(self._node)
            self._executor = None

        self.image_processing_callback = image_processing_callback
        self.image_source = image_source
        self.img = None
        self.show_result = show_result
        self.config = config

        self.camera: Optional[AbstractCam] = camera
        self.poll_interval = poll_interval
        self._frame_timeout = frame_timeout if frame_timeout is not None else 0.1
        self.cam_timer = None
        self._timer_group = ReentrantCallbackGroup()
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None

    @property
    def node(self) -> Node:
        """Internal ROS 2 node owned by this handler."""
        return self._node

    def _build_camera_from_source(self) -> AbstractCam:
        if self.camera is not None:
            return self.camera
        return CameraFactory.from_source(self.image_source, config=self.config, node=self._node)

    def _uses_async(self) -> bool:
        """True when get_frame(wait_for_new=True) waits on a producer that is not this caller."""
        cam = self.camera
        if cam is None:
            return False
        if getattr(cam, "is_threaded", False) or getattr(cam, "_use_ros_topics", False):
            return True
        return cam.__class__.__name__ in ("ROSCam", "ROSDepthCam")

    def open(self) -> None:
        """Build the camera (if needed) and start capture."""
        if self.camera is None:
            self.camera = self._build_camera_from_source()
        if not self.camera.is_running:
            self.camera.start()
        self._node.get_logger().info(f"Camera [{self.image_source}] opened.")

    def close(self) -> None:
        """Stop and release the underlying camera."""
        if self.camera is not None and self.camera.is_running:
            self.camera.close()
            self._node.get_logger().info(f"Camera [{self.image_source}] closed.")

    def _worker_loop(self) -> None:
        while not self.cleaned:
            try:
                if self.camera is None:
                    time.sleep(self.poll_interval)
                    continue
                if self._uses_async():
                    frame = self.camera.get_frame(wait_for_new=True, timeout=self._frame_timeout)
                else:
                    frame = self.camera.get_frame()
                    if frame is None:
                        time.sleep(self.poll_interval)
                        continue
                if frame is None:
                    continue
                with self._lock:
                    self.img = frame
                if self.image_processing_callback is not None:
                    self.image_processing_callback(frame)
                elif not self._uses_async():
                    time.sleep(self.poll_interval)
            except Exception as e:
                if not self.cleaned:
                    self._node.get_logger().error(f"Image processing error: {e}")

    def _show(self) -> None:
        if self.show_result is None:
            return
        with self._lock:
            img = self.img
        if img is None:
            return
        try:
            cv2.imshow(self.show_result, img)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                self.cleanup()
        except cv2.error as e:
            if "The function is not implemented" in str(e):
                self._node.get_logger().warn(
                    "OpenCV GUI not available. Run with show_result:=false or install opencv-python with GUI support",
                    throttle_duration_sec=10.0,
                )
                self.show_result = None
            else:
                raise

    def process(self) -> None:
        """Run the processing callback and optional OpenCV display on the current frame."""
        if self.image_processing_callback is not None:
            self.image_processing_callback(self.img)
        self._show()

    def run(self) -> None:
        """Open the camera and start the capture loop on a worker thread."""
        self._node.get_logger().info(f"Running image handler [{self.image_source}]")
        if self.camera is None:
            self.camera = self._build_camera_from_source()
        if not self.camera.is_running:
            self.camera.start()
        if self._worker is None:
            self._worker = threading.Thread(
                target=self._worker_loop, name="nectar-image-handler", daemon=True
            )
            self._worker.start()
        if self.show_result is not None:
            self.cam_timer = self._node.create_timer(
                self.poll_interval, self._show, callback_group=self._timer_group
            )

    def take_photo(self, timeout_sec: float = 1.0, wait_for_new: bool = True) -> Optional[Any]:
        """
        Capture a single frame and optionally run the processing callback.

        Parameters
        ----------
        timeout_sec : float, default=1.0
            Maximum time to wait for a frame.
        wait_for_new : bool, default=True
            For async cameras, wait for a fresh frame instead of the buffered one.

        Returns
        -------
        Any or None
            Callback result when set, otherwise the raw frame. ``None`` on timeout.

        Raises
        ------
        RuntimeError
            If the camera has not been opened.
        """
        if self.camera is None or not self.camera.is_running:
            raise RuntimeError("Camera must be opened before calling take_photo().")

        if self._uses_async():
            frame = self.camera.get_frame(wait_for_new=wait_for_new, timeout=timeout_sec)
        else:
            frame = None
            start_time = time.time()
            while time.time() - start_time < timeout_sec:
                frame = self.camera.get_frame()
                if frame is not None:
                    break
                time.sleep(0.05)

        if frame is None:
            self._node.get_logger().error("Failed to capture frame within timeout.")
            return None

        self.img = frame
        if self.image_processing_callback:
            return self.image_processing_callback(self.img)
        return self.img

    def cleanup(self) -> None:
        """Release the camera, destroy the timer, and unregister the internal node."""
        if self.cleaned:
            return
        self.cleaned = True
        self._node.get_logger().info("Image Handler shutting down")
        self.close()
        if self.cam_timer is not None:
            self._node.destroy_timer(self.cam_timer)
            self.cam_timer = None
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2.0)
        self._worker = None
        if self.show_result is not None:
            try:
                cv2.destroyWindow(self.show_result)
            except Exception:
                cv2.destroyAllWindows()
        if self._executor is None:
            nectar_runtime.remove_node(self._node)
        else:
            try:
                self._executor.remove_node(self._node)
            except Exception:
                pass
        try:
            self._node.destroy_node()
        except Exception:
            pass

    def __del__(self) -> None:
        if not self.cleaned:
            try:
                self.cleanup()
            except Exception:
                pass
