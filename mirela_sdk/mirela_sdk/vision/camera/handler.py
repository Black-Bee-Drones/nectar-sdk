from rclpy.node import Node
import cv2
import time
from typing import Optional, Callable, Any

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.factory import CameraFactory
from mirela_sdk.vision.camera.config import CameraConfig


class ImageHandler:
    """
    High-level camera interface for ROS2 nodes.

    Manages camera lifecycle, frame polling, and optional image processing
    via timer-based callbacks. Supports both continuous streaming and
    single-shot capture modes.

    Parameters
    ----------
    node : Node
        ROS2 node for timer creation and logging.
    image_source : str
        Camera source identifier. Can be:
        - File path for static images
        - ROS topic starting with '/'
        - Camera type: 'webcam', 'realsense', 'c920', 'imx219', 'oakd'
    image_processing_callback : callable, optional
        Function called with each frame (np.ndarray). Return value
        is used as result in take_photo().
    show_result : str, optional
        Window name for cv2.imshow() display. None disables display.
    config : CameraConfig, optional
        Camera-specific configuration. Auto-detected if not provided.
    camera : AbstractCam, optional
        Pre-configured camera instance. Bypasses factory creation.
    poll_interval : float, optional
        Timer period in seconds for frame polling. Default is 0.01s.
    frame_timeout : float, optional
        Timeout for waiting on new frames in async mode. Default is 0.1s.

    Attributes
    ----------
    img : np.ndarray or None
        Most recently captured frame.
    camera : AbstractCam or None
        Active camera instance.
    """

    def __init__(
        self,
        node: Node,
        image_source: str,
        image_processing_callback: Optional[Callable] = None,
        show_result: Optional[str] = None,
        *,
        config: Optional[CameraConfig] = None,
        camera: Optional[AbstractCam] = None,
        poll_interval: float = 0.01,
        frame_timeout: Optional[float] = None,
    ):
        self.node = node
        self.image_processing_callback = image_processing_callback
        self.image_source = image_source
        self.img = None
        self.show_result = show_result
        self.config = config
        self.cleaned = False

        self.camera: Optional[AbstractCam] = camera
        self.poll_interval = poll_interval
        self._frame_timeout = frame_timeout if frame_timeout is not None else 0.1
        self.cam_timer = None

    def _build_camera_from_source(self) -> AbstractCam:
        """Build camera instance from source string using factory."""
        if self.camera is not None:
            return self.camera
        return CameraFactory.from_source(
            self.image_source, config=self.config, node=self.node
        )

    def open(self) -> None:
        """
        Open and initialize the camera.

        Creates camera instance if not provided and starts capture.
        Use this for manual control; run() handles this automatically.
        """
        if self.camera is None:
            self.camera = self._build_camera_from_source()
        if not self.camera.is_running:
            self.camera.start()
        self.node.get_logger().info(f"Camera [{self.image_source}] opened.")

    def close(self) -> None:
        """
        Stop and release camera resources.
        """
        if self.camera is not None and self.camera.is_running:
            self.camera.close()
            self.node.get_logger().info(f"Camera [{self.image_source}] closed.")

    def _camera_callback(self) -> None:
        """Timer callback for frame polling and processing."""
        try:
            if self.camera is None:
                return

            # Async capture (threaded OpenCV or ROS topics)
            uses_async = getattr(self.camera, "_use_ros_topics", False) or getattr(
                self.camera, "is_threaded", False
            )

            if uses_async:
                frame = self.camera.get_frame(
                    wait_for_new=True, timeout=self._frame_timeout
                )
            else:
                frame = self.camera.get_frame()

            if frame is None:
                return
            self.img = frame
            self.process()
        except Exception as e:
            self.node.get_logger().error(f"Camera polling error: {e}")

    def process(self) -> None:
        """
        Process current frame through callback and optional display.

        Invokes image_processing_callback if set, then displays frame
        in OpenCV window if show_result is configured.
        """
        if self.image_processing_callback is not None:
            self.image_processing_callback(self.img)
        if self.show_result is not None and self.img is not None:
            try:
                cv2.imshow(self.show_result, self.img)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.cleanup()
            except cv2.error as e:
                if "The function is not implemented" in str(e):
                    self.node.get_logger().warn(
                        "OpenCV GUI not available. Run with show_result:=false or install opencv-python with GUI support",
                        throttle_duration_sec=10.0,
                    )
                    self.show_result = None
                else:
                    raise

    def run(self) -> None:
        """
        Start continuous frame capture with timer-based polling.

        Opens camera and creates ROS timer for periodic frame acquisition.
        """
        self.node.get_logger().info(f"Running image handler [{self.image_source}]")
        if self.camera is None:
            self.camera = self._build_camera_from_source()
        if not self.camera.is_running:
            self.camera.start()
        self.cam_timer = self.node.create_timer(
            self.poll_interval, self._camera_callback
        )

    def take_photo(
        self, timeout_sec: float = 1.0, wait_for_new: bool = True
    ) -> Optional[Any]:
        """
        Capture a single frame and optionally process it.

        Parameters
        ----------
        timeout_sec : float, optional
            Maximum time to wait for frame capture. Default is 1.0s.
        wait_for_new : bool, optional
            If True, waits for a fresh frame. If False, returns buffered
            frame immediately (async cameras only). Default is True.

        Returns
        -------
        Any or None
            Callback result if image_processing_callback is set,
            otherwise the raw frame (np.ndarray). None on timeout.

        Raises
        ------
        RuntimeError
            If camera is not opened. Call open() first.
        """
        if self.camera is None or not self.camera.is_running:
            raise RuntimeError(
                "Camera must be opened before calling take_photo(). Call open() first."
            )

        start_time = time.time()
        frame = None

        uses_async = getattr(self.camera, "_use_ros_topics", False) or getattr(
            self.camera, "is_threaded", False
        )

        if uses_async:
            frame = self.camera.get_frame(
                wait_for_new=wait_for_new, timeout=timeout_sec
            )
        else:
            while time.time() - start_time < timeout_sec:
                frame = self.camera.get_frame()
                if frame is not None:
                    break
                time.sleep(0.05)

        if frame is None:
            self.node.get_logger().error("Failed to capture frame within timeout.")
            return None

        self.img = frame
        if self.image_processing_callback:
            return self.image_processing_callback(self.img)
        return self.img

    def cleanup(self) -> None:
        """
        Release all resources and stop capture.

        Closes camera, destroys timer, and closes OpenCV windows.
        """
        if not self.cleaned:
            self.node.get_logger().info("Image Handler Shutting Down")
            self.cleaned = True
            self.close()
            if self.cam_timer is not None:
                self.node.destroy_timer(self.cam_timer)
            if self.show_result is not None:
                try:
                    cv2.destroyWindow(self.show_result)
                except Exception:
                    cv2.destroyAllWindows()
        else:
            print("Image Handler already cleaned up")

    def __del__(self) -> None:
        if not self.cleaned:
            self.cleanup()
