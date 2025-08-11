import os
from rclpy.node import Node

import cv2

from typing import Optional

from time import sleep

from .abstract_cam import AbstractCam
from .realsense_cam import RealsenseCam
from .opencv_cam import OpenCVCam
from .c920_cam import C920Cam
from .file_image_cam import FileImageCam
from .ros_cam import ROSCam
from .oakd_cam import OakdCam


class ImageHandler:
    def __init__(
        self,
        node: Node,
        image_source: str,
        image_processing_callback: Optional[callable] = None,
        show_result: str = None,
        cap: Optional[int] = 0,
        oakd_num: Optional[int] = 1,
        c920_config: Optional[int] = 1,
        camera: Optional[AbstractCam] = None,
        poll_interval: float = 0.0001,
    ):
        """
        Class to handle image processing from a ROS topic or webcam.

        :param node (rclpy.node.Node): the ROS node to handle the image processing
        :param image_source (str): the source of the image (ROS topic, webcam, c920 or oakd)
        :param image_processing_callback (callable): the callback function to process the image
        :param cap (int): the webcam index.
            Use this parameter only if the image source is "webcam"
        :param oakd_num (int): index number for oakd cam - 1 for rgb, 2 for left monochrome cam, 3 for
         right monochrome cam
            Use this parameter only if the image source is "oakd"
        :param c920_config (int): index number for c920 configuration. 0 -> 640x480, 1 (default) -> 1280x720, 2-> 1920x1080. All are captured in 30 FPS.
        :param camera (AbstractCam): optional camera instance.
        :param poll_interval (float): timer interval for polling camera.get_frame().
        """
        self.node = node
        self.image_processing_callback = image_processing_callback
        self.image_source = image_source
        self.img = None
        self.show_result = show_result
        self.cap_num = cap
        self.oakd_num = oakd_num
        self.c920_config = c920_config
        self.cleaned = False

        self.camera: Optional[AbstractCam] = camera
        self.poll_interval = poll_interval
        self.cam_timer = None

    def _build_camera_from_source(self) -> AbstractCam:
        src = self.image_source
        if self.camera is not None:
            return self.camera

        if src == "realsense":
            return RealsenseCam(fps=30)
        if src == "webcam":
            return OpenCVCam(device_index=self.cap_num, fps=30, fourcc="MJPG")
        if src == "c920":
            return C920Cam(
                profile=int(self.c920_config), fallback_device_index=self.cap_num
            )
        if src == "oakd":
            cam = OakdCam()
            # Use DepthCam-like start API for uniformity
            cam.start(
                cam_num=int(self.oakd_num), enable_depth=False, usb_full_speed=True
            )
            return cam
        if os.path.isfile(src):
            return FileImageCam(src)
        # Assume ROS topic
        compressed = src.endswith("compressed")
        return ROSCam(self.node, src, compressed=compressed)

    def _camera_callback(self):
        try:
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
            cv2.imshow(self.show_result, self.img)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                self.cleanup()

    def run(self):
        self.node.get_logger().info(f"Running image handler [{self.image_source}]")
        if self.camera is None:
            self.camera = self._build_camera_from_source()
            # If we built an OakdCam in _build_camera_from_source it was already started.
            if not isinstance(self.camera, OakdCam) and not self.camera.is_running:
                self.camera.start()
        else:
            if not self.camera.is_running:
                self.camera.start()
        self.cam_timer = self.node.create_timer(
            self.poll_interval, self._camera_callback
        )

    def cleanup(self):
        if not self.cleaned:
            self.node.get_logger().info("Image Handler Shutting Down")
            self.cleaned = True
            if self.camera is not None:
                try:
                    self.camera.close()
                except Exception as ex:
                    self.node.get_logger().error(f"{ex}")
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
