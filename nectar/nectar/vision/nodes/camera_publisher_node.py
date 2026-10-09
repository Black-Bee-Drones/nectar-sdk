#!/usr/bin/env python3
import argparse
import time
from typing import Any, Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image

from nectar.vision.camera import (
    CameraFactory,
    ImageHandler,
    add_camera_arguments,
    parse_camera_args,
)
from nectar.vision.camera.config import CameraConfig
from nectar.vision.stream import add_stream_arguments


class CameraPublisherNode(Node):
    """
    Generic camera image publisher node.

    Captures frames from any supported camera driver via CameraFactory and
    publishes them to ROS image topics.
    """

    def __init__(
        self,
        source: str = "webcam",
        camera_config: Optional[CameraConfig] = None,
        *,
        show: bool = False,
        use_compression: bool = True,
        jpeg_quality: int = 80,
        log_fps_interval: float = 5.0,
        poll_interval: float = -1.0,
        frame_timeout: float = -1.0,
    ) -> None:
        super().__init__("camera_publisher")

        self.camera_source = source
        self.use_compression = use_compression
        self.jpeg_quality = jpeg_quality
        self.log_fps_interval = log_fps_interval
        self._poll_interval_override = poll_interval
        self._frame_timeout_override = frame_timeout
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

        camera = CameraFactory.from_source(self.camera_source, config=camera_config, node=self)
        poll = self._resolve_poll_interval(camera)
        timeout = self._resolve_frame_timeout(camera)

        self.image_handler = ImageHandler(
            image_source=self.camera_source,
            image_processing_callback=self._publish_frame,
            config=camera_config,
            camera=camera,
            poll_interval=poll,
            frame_timeout=timeout,
            show_result="Camera Publisher" if show else None,
        )

        self.image_handler.run()
        self._log_camera_info(camera)

        if self.log_fps_interval > 0:
            self.fps_timer = self.create_timer(self.log_fps_interval, self._log_fps_stats)

        self.get_logger().info(
            f"Camera publisher started — source: {self.camera_source}, "
            f"compression: {self.use_compression}"
        )

    def _resolve_poll_interval(self, camera: Any) -> float:
        if self._poll_interval_override > 0:
            return self._poll_interval_override
        is_threaded = getattr(camera, "is_threaded", False)
        if is_threaded:
            return 0.001
        fps = self._get_effective_fps(camera)
        return 1.0 / max(fps, 1)

    def _resolve_frame_timeout(self, camera: Any) -> float:
        if self._frame_timeout_override > 0:
            return self._frame_timeout_override
        fps = self._get_effective_fps(camera)
        return 2.0 / max(fps, 1)

    @staticmethod
    def _get_effective_fps(camera: Any) -> float:
        actual = getattr(camera, "actual_settings", None)
        if actual and "fps" in actual:
            return float(actual["fps"])
        cfg = getattr(camera, "_config", None)
        if cfg:
            fps = getattr(cfg, "fps", None)
            if fps is not None:
                return float(fps)
        return 30.0

    def _log_camera_info(self, camera: Any) -> None:
        actual = getattr(camera, "actual_settings", None)
        if actual:
            parts = [f"{k}={v}" for k, v in actual.items()]
            self.get_logger().info(f"Camera actual settings: {', '.join(parts)}")
        else:
            self.get_logger().info(f"Camera '{self.camera_source}' started successfully.")

    def _publish_frame(self, frame):
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
        return frame

    def _log_fps_stats(self) -> None:
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
        if self._is_shutdown:
            return
        self._is_shutdown = True
        self.image_handler.cleanup()
        self.get_logger().info("Camera publisher stopped")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish camera frames as a ROS 2 image topic")
    add_camera_arguments(parser)
    add_stream_arguments(parser, show_default=False, include_publish=False)
    parser.add_argument(
        "--no-compression",
        dest="use_compression",
        action="store_false",
        help="Publish sensor_msgs/Image instead of CompressedImage",
    )
    parser.set_defaults(use_compression=True)
    parser.add_argument("--jpeg-quality", type=int, default=80)
    parser.add_argument("--log-fps-interval", type=float, default=5.0)
    parser.add_argument("--poll-interval", type=float, default=-1.0)
    parser.add_argument("--frame-timeout", type=float, default=-1.0)
    return parser


def main(args=None) -> None:
    """Entry point for camera publisher node."""
    import nectar

    ns, ros_argv, source, camera_config = parse_camera_args(_parser(), args)
    rclpy.init(args=ros_argv)
    nectar.init()
    node = CameraPublisherNode(
        source,
        camera_config,
        show=ns.show,
        use_compression=ns.use_compression,
        jpeg_quality=ns.jpeg_quality,
        log_fps_interval=ns.log_fps_interval,
        poll_interval=ns.poll_interval,
        frame_timeout=ns.frame_timeout,
    )
    nectar.add_node(node)
    try:
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
