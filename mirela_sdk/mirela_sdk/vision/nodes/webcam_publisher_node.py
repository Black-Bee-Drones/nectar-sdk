#!/usr/bin/env python3
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from mirela_sdk.vision.camera.config import OpenCVConfig
from mirela_sdk.vision.camera.drivers.opencv_cam import OpenCVCam
from mirela_sdk.vision.camera.handler import ImageHandler


class WebcamPublisherNode(Node):
    """
    Webcam image publisher node using ImageHandler.

    Captures frames from a webcam via ImageHandler and publishes them to ROS topics.

    Parameters (ROS)
    ----------------
    camera_index : int
        Webcam device index (default: 0).
    fps : int
        Target frames per second (default: 30).
    width : int
        Frame width in pixels (default: 640).
    height : int
        Frame height in pixels (default: 480).
    use_compression : bool
        Publish compressed JPEG images (default: True).
    jpeg_quality : int
        JPEG compression quality 0-100 (default: 80).
    log_fps_interval : float
        Interval in seconds to log FPS statistics (default: 5.0, 0 to disable).
    buffer_size : int
        Camera buffer size 1-10 (default: 2). Buffer=1 can cause frame drops
        on some cameras. Buffer=2 provides good latency with stable FPS.
    threaded : bool
        Use background thread for capture (default: True).
        Threaded mode provides more consistent FPS.

    Publishes
    ---------
    image_raw/compressed : CompressedImage
        Compressed JPEG image (if use_compression=True).
    image_raw : Image
        Raw BGR image (if use_compression=False).

    Notes
    -----
    Use v4l2-ctl to check supported modes: `v4l2-ctl -d /dev/video0 --list-formats-ext`
    """

    def __init__(self):
        super().__init__("webcam_publisher")

        self.declare_parameter("camera_index", 0)
        self.declare_parameter("fps", 30)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("use_compression", True)
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("log_fps_interval", 5.0)
        self.declare_parameter("buffer_size", 2)
        self.declare_parameter("threaded", True)

        self.camera_index = self.get_parameter("camera_index").value
        self.fps = self.get_parameter("fps").value
        self.width = self.get_parameter("width").value
        self.height = self.get_parameter("height").value
        self.use_compression = self.get_parameter("use_compression").value
        self.jpeg_quality = self.get_parameter("jpeg_quality").value
        self.log_fps_interval = self.get_parameter("log_fps_interval").value
        self.buffer_size = min(max(self.get_parameter("buffer_size").value, 1), 10)
        self.threaded = self.get_parameter("threaded").value

        self._is_shutdown = False

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )

        if self.use_compression:
            self.publisher = self.create_publisher(
                CompressedImage, "image_raw/compressed", qos_profile
            )
        else:
            self.publisher = self.create_publisher(Image, "image_raw", qos_profile)

        self.bridge = CvBridge()
        self.jpeg_params = (cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality)

        self._frame_count = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0

        config = OpenCVConfig(
            name="webcam",
            device_index=self.camera_index,
            width=self.width,
            height=self.height,
            fps=self.fps,
            fourcc="MJPG",
            buffer_size=self.buffer_size,
            threaded=self.threaded,
        )

        self.camera = OpenCVCam(config)
        self.camera.start()

        actual = self.camera.actual_settings
        self.get_logger().info(
            f"Camera: {actual['width']}x{actual['height']} @ {actual['fps']:.1f}fps, "
            f"fourcc={actual['fourcc']}, buffer={actual['buffer_size']}, "
            f"threaded={actual['threaded']}"
        )

        if actual["fps"] < self.fps:
            self.get_logger().warn(
                f"Camera FPS ({actual['fps']:.1f}) is lower than requested ({self.fps}). "
                "This is a hardware/driver limitation."
            )

        poll_interval = 0.001 if self.threaded else 1.0 / max(actual["fps"], 1)
        # Frame timeout: how long to wait for a new frame in threaded mode
        frame_timeout = 2.0 / max(actual["fps"], 1)  # 2x frame interval
        self.image_handler = ImageHandler(
            node=self,
            image_source="webcam",
            image_processing_callback=self._publish_frame,
            config=config,
            camera=self.camera,
            poll_interval=poll_interval,
            frame_timeout=frame_timeout,
        )

        self.image_handler.run()

        if self.log_fps_interval > 0:
            self.fps_timer = self.create_timer(self.log_fps_interval, self._log_fps_stats)

        self.get_logger().info(
            f"Webcam publisher started - camera: {self.camera_index}, "
            f"target fps: {self.fps}, resolution: {self.width}x{self.height}, "
            f"compression: {self.use_compression}"
        )

    def _publish_frame(self, frame) -> None:
        """
        Process and publish a single frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR image frame from camera.
        """
        if frame is None:
            return

        timestamp = self.get_clock().now().to_msg()

        if self.use_compression:
            _, compressed = cv2.imencode(".jpg", frame, self.jpeg_params)
            msg = CompressedImage()
            msg.header.stamp = timestamp
            msg.header.frame_id = "camera"
            msg.format = "jpeg"
            msg.data = compressed.tobytes()
        else:
            msg = self.bridge.cv2_to_imgmsg(frame, "bgr8")
            msg.header.stamp = timestamp
            msg.header.frame_id = "camera"

        self.publisher.publish(msg)
        self._frame_count += 1

    def _log_fps_stats(self) -> None:
        """Log FPS statistics periodically."""
        elapsed = time.time() - self._fps_start_time
        if elapsed > 0:
            self._current_fps = self._frame_count / elapsed
            self.get_logger().info(
                f"FPS: {self._current_fps:.1f} "
                f"(frames: {self._frame_count}, elapsed: {elapsed:.1f}s)"
            )
        self._frame_count = 0
        self._fps_start_time = time.time()

    def cleanup(self) -> None:
        """Release camera resources."""
        if self._is_shutdown:
            return
        self._is_shutdown = True
        self.image_handler.cleanup()
        self.get_logger().info("Webcam publisher stopped")


def main(args=None) -> None:
    """Entry point for webcam publisher node."""
    rclpy.init(args=args)

    node = WebcamPublisherNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
