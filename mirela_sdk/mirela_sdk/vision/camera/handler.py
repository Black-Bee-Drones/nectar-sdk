from rclpy.node import Node
import cv2
import time
from typing import Optional, Callable, Any

from mirela_sdk.vision.camera.abstract import AbstractCam
from mirela_sdk.vision.camera.factory import CameraFactory
from mirela_sdk.vision.camera.config import CameraConfig


class ImageHandler:
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
        self.cam_timer = None

    def _build_camera_from_source(self) -> AbstractCam:
        if self.camera is not None:
            return self.camera
        return CameraFactory.from_source(
            self.image_source, config=self.config, node=self.node
        )

    def open(self):
        if self.camera is None:
            self.camera = self._build_camera_from_source()
        if not self.camera.is_running:
            self.camera.start()
        self.node.get_logger().info(f"Camera [{self.image_source}] opened.")

    def close(self):
        if self.camera is not None and self.camera.is_running:
            self.camera.close()
            self.node.get_logger().info(f"Camera [{self.image_source}] closed.")

    def _camera_callback(self):
        try:
            if hasattr(self.camera, "_use_ros_topics") and self.camera._use_ros_topics:
                frame = self.camera.get_frame(
                    wait_for_new=True, timeout=self.poll_interval * 0.9
                )
            else:
                frame = self.camera.get_frame() if self.camera else None

            if frame is None:
                return
            self.img = frame
            self.process()
        except Exception as e:
            self.node.get_logger().error(f"Camera polling error: {e}")

    def process(self):
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

    def run(self):
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
        if self.camera is None or not self.camera.is_running:
            raise RuntimeError(
                "Camera must be opened before calling take_photo(). Call open() first."
            )

        start_time = time.time()
        frame = None

        if hasattr(self.camera, "_use_ros_topics") and self.camera._use_ros_topics:
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

    def cleanup(self):
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

    def __del__(self):
        if not self.cleaned:
            self.cleanup()
