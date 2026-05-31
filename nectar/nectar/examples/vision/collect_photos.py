#!/usr/bin/env python3
"""Capture and save frames from any supported camera.

Examples::

    python collect_photos.py --camera-type webcam --interval 0.5
    python collect_photos.py --camera-type realsense --jpeg-quality 95 --show
    python collect_photos.py --camera-type webcam --publish --publish-scale 0.3
"""

import argparse
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

import nectar
from nectar.vision.camera.config_builder import ConfigBuilder
from nectar.vision.camera.handler import ImageHandler

log = logging.getLogger("collect_photos")


def _camera_config(camera_type: str, width: int, height: int, fps: int):
    source_key = camera_type
    if camera_type == "webcam":
        params = {"device_index": 0, "width": width, "height": height, "fps": fps}
    elif camera_type == "realsense":
        params = {
            "color_width": width,
            "color_height": height,
            "depth_width": width,
            "depth_height": height,
            "fps": fps,
        }
    elif camera_type == "realsense_ros":
        params = {
            "topic": "/camera/color/image_raw/compressed",
            "compressed": True,
            "depth_topic": "/camera/depth/image_rect_raw",
            "depth_compressed": False,
        }
        source_key = "ros_depth"
    elif camera_type == "c920":
        params = {"profile": 1}
    elif camera_type == "imx219":
        params = {"sensor_id": 0, "width": width, "height": height, "flip": 2, "fps": fps}
    elif camera_type == "oakd":
        params = {}
    elif camera_type == "ros":
        params = {"topic": "/camera/color/image_raw/compressed", "compressed": True}
    else:
        return None, camera_type
    return ConfigBuilder.build(source_key, params), source_key


class _Publisher:
    def __init__(self, topic: str, scale: float) -> None:
        self._scale = scale
        self._node = Node(
            f"nectar_collect_photos_pub_{uuid.uuid4().hex[:8]}",
            start_parameter_services=False,
        )
        nectar.add_node(self._node)
        self._pub = self._node.create_publisher(CompressedImage, topic, 1)

    def publish(self, frame: np.ndarray) -> None:
        if self._scale < 1.0:
            frame = cv2.resize(
                frame, None, fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA
            )
        _, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        msg = CompressedImage()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.format = "jpeg"
        msg.data = data.tobytes()
        self._pub.publish(msg)

    def cleanup(self) -> None:
        nectar.remove_node(self._node)
        try:
            self._node.destroy_node()
        except Exception:
            pass


def _setup_output_dir(output_dir: str, run_name: str) -> Path:
    run_name = run_name or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path.home() / output_dir / run_name
    path.mkdir(parents=True, exist_ok=True)
    return path


class Collector:
    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self._output_path = _setup_output_dir(args.output_dir, args.run_name)
        self._count = 0
        self._last_capture = 0.0
        self._publisher: Optional[_Publisher] = (
            _Publisher(args.publish_topic, args.publish_scale) if args.publish else None
        )

        config, source = _camera_config(args.camera_type, args.width, args.height, args.fps)
        log.info(
            "Camera config: %s %dx%d @ %dfps", args.camera_type, args.width, args.height, args.fps
        )

        self.handler = ImageHandler(
            image_source=source,
            config=config,
            show_result="Collect Photos" if args.show else None,
            image_processing_callback=self._on_frame,
            poll_interval=0.01,
        )
        self.handler.run()
        log.info("Saving to %s (interval=%ss)", self._output_path, args.capture_interval)

    def _on_frame(self, frame) -> None:
        if frame is None:
            return
        now = time.time()
        if now - self._last_capture < self._args.capture_interval:
            return
        self._count += 1
        self._last_capture = now

        ext = self._args.image_format
        filepath = self._output_path / f"frame_{self._count:05d}.{ext}"
        params = []
        if ext in ("jpg", "jpeg"):
            params = [cv2.IMWRITE_JPEG_QUALITY, self._args.jpeg_quality]
        elif ext == "png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        cv2.imwrite(str(filepath), frame, params)
        log.info(
            "[%d] Saved %s (%dx%d)", self._count, filepath.name, frame.shape[1], frame.shape[0]
        )

        if self._publisher is not None:
            self._publisher.publish(frame)

        if self._args.max_photos > 0 and self._count >= self._args.max_photos:
            log.info("Reached max_photos (%d). Stopping.", self._args.max_photos)
            raise SystemExit(0)

    def cleanup(self) -> None:
        self.handler.cleanup()
        if self._publisher is not None:
            self._publisher.cleanup()
        log.info("Collection finished -- %d photos saved to %s", self._count, self._output_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Capture and save camera frames")
    p.add_argument("--camera-type", default="webcam")
    p.add_argument("--output-dir", default="collected_photos")
    p.add_argument("--run-name", default="")
    p.add_argument("--capture-interval", type=float, default=1.0)
    p.add_argument("--image-format", default="jpg")
    p.add_argument("--jpeg-quality", type=int, default=90)
    p.add_argument("--show", action="store_true")
    p.add_argument("--max-photos", type=int, default=0)
    p.add_argument("--publish", action="store_true")
    p.add_argument("--publish-topic", default="collect_photos/compressed")
    p.add_argument("--publish-scale", type=float, default=0.5)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    args, _ = p.parse_known_args()
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    nectar.init()
    args = parse_args()
    collector = Collector(args)
    try:
        nectar.spin()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        collector.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
