import threading
import time
import uuid
from typing import Any, Callable, ClassVar, List, Optional

import cv2
import numpy as np
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
    SDK runtime executor. ``run()`` grabs frames on a worker thread. OpenCV
    display, if enabled, is pumped from :func:`nectar.spin` on the main thread.

    Parameters
    ----------
    image_source : str
        Camera source identifier. File path, ROS topic (starts with '/'),
        or registered key ('webcam', 'realsense', 'c920', 'imx219', 'oakd').
    image_processing_callback : callable, optional
        Per-frame callback ``(np.ndarray) -> Any``. An ``np.ndarray`` return
        value is shown when ``show_result`` is set, and is propagated by
        :meth:`take_photo`.
    show_result : str, optional
        OpenCV window name. ``None`` disables display.
    on_key : callable, optional
        ``(int) -> None`` invoked on the GUI thread for keys other than ``q``.
    on_display : callable, optional
        ``() -> None`` invoked on the GUI thread after ``imshow``.
    config : CameraConfig, optional
        Camera-specific configuration. Auto-detected if not provided.
    camera : AbstractCam, optional
        Pre-built camera instance. Bypasses factory creation.
    poll_interval : float, default=0.01
        Sleep between grabs for synchronous cameras.
    frame_timeout : float, optional
        Timeout for async frame waits. Defaults to 0.1 s.
    executor : Executor, optional
        Executor to register the internal node with. Defaults to the
        shared :mod:`nectar.runtime` executor.
    """

    _displays: ClassVar[List["ImageHandler"]] = []

    def __init__(
        self,
        image_source: str,
        image_processing_callback: Optional[Callable] = None,
        show_result: Optional[str] = None,
        *,
        on_key: Optional[Callable[[int], None]] = None,
        on_display: Optional[Callable[[], None]] = None,
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
        self.on_key = on_key
        self.on_display = on_display
        self.config = config

        self.camera: Optional[AbstractCam] = camera
        self.poll_interval = poll_interval
        self._frame_timeout = frame_timeout if frame_timeout is not None else 0.1
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._display_registered = False

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

    def _store_frame(self, frame: np.ndarray, result: Any = None) -> None:
        display = result if isinstance(result, np.ndarray) else frame
        with self._lock:
            self.img = display

    def _worker_loop(self) -> None:
        async_mode = self._uses_async()
        while not self.cleaned:
            try:
                if self.camera is None:
                    time.sleep(self.poll_interval)
                    continue
                if async_mode:
                    frame = self.camera.get_frame(wait_for_new=True, timeout=self._frame_timeout)
                else:
                    frame = self.camera.get_frame()

                if frame is None:
                    if not async_mode:
                        time.sleep(self.poll_interval)
                    continue

                result = None
                if self.image_processing_callback is not None:
                    result = self.image_processing_callback(frame)
                elif not async_mode:
                    time.sleep(self.poll_interval)
                self._store_frame(frame, result)
            except Exception as e:
                if not self.cleaned:
                    self._node.get_logger().error(f"Image processing error: {e}")

    def _present(self) -> None:
        with self._lock:
            img = self.img
        if img is None:
            return
        try:
            cv2.imshow(self.show_result, img)
            if self.on_display is not None:
                self.on_display()
        except cv2.error as e:
            if "The function is not implemented" in str(e):
                self._node.get_logger().warn(
                    "OpenCV GUI not available. Run with show_result:=false or install opencv-python with GUI support",
                    throttle_duration_sec=10.0,
                )
                self.show_result = None
            else:
                raise

    @classmethod
    def pump_gui(cls) -> Optional[bool]:
        """Present registered windows on the calling thread. One ``waitKey`` per call.

        Returns
        -------
        bool or None
            ``None`` when nothing is registered, ``False`` when ``q`` closed
            the windows, ``True`` otherwise.
        """
        handlers = [h for h in cls._displays if not h.cleaned and h.show_result]
        if not handlers:
            return None
        for handler in handlers:
            handler._present()
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            for handler in handlers:
                handler.cleanup()
            return False
        if key != 255:
            for handler in handlers:
                if handler.on_key is not None:
                    handler.on_key(key)
        return True

    def _register_display(self) -> None:
        if self._display_registered:
            return
        ImageHandler._displays.append(self)
        self._display_registered = True
        nectar_runtime._runtime._gui_pump = ImageHandler.pump_gui

    def _unregister_display(self) -> None:
        if not self._display_registered:
            return
        if self in ImageHandler._displays:
            ImageHandler._displays.remove(self)
        self._display_registered = False
        if not ImageHandler._displays:
            nectar_runtime._runtime._gui_pump = None

    def process(self) -> None:
        """Run the processing callback on the current frame."""
        if self.image_processing_callback is not None:
            result = self.image_processing_callback(self.img)
            if self.img is not None:
                self._store_frame(self.img, result)

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
            self._register_display()

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

        result = None
        if self.image_processing_callback:
            result = self.image_processing_callback(frame)

        self._store_frame(frame, result)
        return result if result is not None else frame

    def cleanup(self) -> None:
        """Release the camera and unregister the internal node."""
        if self.cleaned:
            return
        self.cleaned = True
        self._node.get_logger().info("Image Handler shutting down")
        self.close()
        self._unregister_display()
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=5.0)
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
