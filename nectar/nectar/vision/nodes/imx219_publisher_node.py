import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from nectar.vision.camera.config import IMX219Config
from nectar.vision.camera.drivers.imx219_cam import IMX219Cam
from nectar.vision.camera.handler import ImageHandler


class IMX219PublisherNode(Node):
    """
    IMX219 CSI camera image publisher node using ImageHandler.

    Captures frames from an IMX219 CSI camera via GStreamer/nvarguscamerasrc
    and publishes them to ROS topics.

    Parameters (ROS)
    ----------------
    sensor_id : int
        CSI sensor ID (default: 0).
    fps : int
        Target frames per second (default: 30).
    width : int
        Frame width in pixels (default: 1920).
    height : int
        Frame height in pixels (default: 1080).
    flip : int
        nvvidconv flip-method (default: 0).
        0=none, 1=ccw-90, 2=rotate-180, 3=cw-90, 4=horiz-flip,
        5=upper-right-diag, 6=vert-flip, 7=upper-left-diag.
    use_compression : bool
        Publish compressed JPEG images (default: True).
    jpeg_quality : int
        JPEG compression quality 0-100 (default: 80).
    log_fps_interval : float
        Interval in seconds to log FPS statistics (default: 5.0, 0 to disable).
    brightness : float
        Brightness offset applied via videobalance (default: 0.0, neutral).
        Valid range: -1.0 (darkest) to 1.0 (brightest).
        Set to 0.0 to disable the element entirely.

    Publishes
    ---------
    image_raw/compressed : CompressedImage
        Compressed JPEG image (if use_compression=True).
    image_raw : Image
        Raw BGR image (if use_compression=False).

    Notes
    -----
    Requires GStreamer with nvarguscamerasrc and NVIDIA multimedia libraries.
    Use ``v4l2-ctl --list-devices`` to list connected CSI cameras.
    """

    def __init__(self):
        super().__init__("imx219_publisher")

        self.declare_parameter("sensor_id", 0)
        self.declare_parameter("fps", 30)
        self.declare_parameter("width", 1920)
        self.declare_parameter("height", 1080)
        self.declare_parameter("flip", 0)
        self.declare_parameter("use_compression", True)
        self.declare_parameter("jpeg_quality", 80)
        self.declare_parameter("log_fps_interval", 5.0)
        # Brightness: 0.0 is neutral (disables videobalance element)
        self.declare_parameter("brightness", 0.0)

        sensor_id = self.get_parameter("sensor_id").value
        fps = self.get_parameter("fps").value
        width = self.get_parameter("width").value
        height = self.get_parameter("height").value
        flip = self.get_parameter("flip").value
        self.use_compression = self.get_parameter("use_compression").value
        self.jpeg_quality = self.get_parameter("jpeg_quality").value
        self.log_fps_interval = self.get_parameter("log_fps_interval").value

        raw_brightness = self.get_parameter("brightness").value
        brightness = raw_brightness if raw_brightness != 0.0 else None

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

        config = IMX219Config(
            name="imx219_cam",
            sensor_id=sensor_id,
            width=width,
            height=height,
            fps=fps,
            flip=flip,
            brightness=brightness,
        )

        self.camera = IMX219Cam(config)
        self.camera.start()

        self.get_logger().info(
            f"IMX219 camera started: sensor_id={sensor_id}, "
            f"{width}x{height} @ {fps}fps, flip={flip}, "
            f"brightness={'off' if brightness is None else brightness}"
        )

        poll_interval = 1.0 / max(fps, 1)
        frame_timeout = 2.0 / max(fps, 1)
        self.image_handler = ImageHandler(
            node=self,
            image_source="imx219",
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
            f"IMX219 publisher started - compression: {self.use_compression}"
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
        self.get_logger().info("IMX219 publisher stopped")


def main(args=None) -> None:
    """Entry point for IMX219 publisher node."""
    rclpy.init(args=args)

    node = IMX219PublisherNode()

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
