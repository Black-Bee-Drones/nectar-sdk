#!/usr/bin/env python3
"""Real-time image classification over a camera stream.

Examples::

    python classifier_example.py --model yolo26n-cls.pt
    python classifier_example.py --model google/vit-base-patch16-224 --framework transformers
    python classifier_example.py --camera-source /image_raw/compressed --publish --no-show
"""

import argparse
import logging
import os
import uuid
from typing import Optional, Tuple

import cv2
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage

import nectar
from nectar.ai.classification import Classifier
from nectar.ai.core import Framework
from nectar.vision.camera import ImageHandler, ROSConfig
from nectar.vision.camera.config import CameraConfig
from nectar.vision.camera.config_builder import ConfigBuilder

log = logging.getLogger("classifier_example")

_PUBLISH_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    durability=DurabilityPolicy.VOLATILE,
)


def _compressed_topic(topic: str, compressed: bool) -> bool:
    return compressed or topic.rstrip("/").endswith("/compressed")


def _camera_config(args: argparse.Namespace) -> Tuple[Optional[CameraConfig], str]:
    source = args.camera_source
    if source.startswith("/"):
        return ROSConfig(
            topic=source, compressed=_compressed_topic(source, args.compressed)
        ), source
    if os.path.isfile(source):
        return None, source
    key = "ros_depth" if source.lower() == "realsense_ros" else source.lower()
    if not ConfigBuilder.is_registered(key):
        return None, source
    params = {
        "device_index": args.device_index,
        "width": args.width,
        "height": args.height,
        "topic": args.topic,
        "compressed": _compressed_topic(args.topic, args.compressed),
        "color_width": args.width,
        "color_height": args.height,
        "depth_width": args.width,
        "depth_height": args.height,
    }
    return ConfigBuilder.build(key, params), key


def _resolve_framework(framework_str: str) -> Optional[Framework]:
    if not framework_str:
        return None
    try:
        return Framework(framework_str.lower())
    except ValueError:
        log.warning("Unknown framework '%s', falling back to auto-detect", framework_str)
        return None


class ClassifierStream:
    def __init__(self, args: argparse.Namespace) -> None:
        if args.hf_token:
            os.environ["HF_TOKEN"] = args.hf_token

        self.topk = args.topk
        self.jpeg_quality = args.jpeg_quality
        self.frame_count = 0

        framework = _resolve_framework(args.framework)
        log.info("Loading model: %s (device=%s)", args.model, args.device)
        self.classifier = Classifier(
            model_source=args.model,
            framework=framework,
            device=args.device,
            topk=self.topk,
        )
        self.classifier.load()
        log.info("Model loaded -- framework: %s", self.classifier.framework.value)

        self._pub_node: Optional[Node] = None
        self._pub = None
        if args.publish:
            self._pub_node = Node(
                f"nectar_classifier_pub_{uuid.uuid4().hex[:8]}",
                start_parameter_services=False,
            )
            nectar.add_node(self._pub_node)
            self._pub = self._pub_node.create_publisher(
                CompressedImage, args.publish_topic, _PUBLISH_QOS
            )
            log.info("Publishing annotated frames on %s", args.publish_topic)

        config, source = _camera_config(args)
        self.handler = ImageHandler(
            image_source=source,
            config=config,
            show_result="Classification Stream" if args.show_result else None,
            image_processing_callback=self.process_frame,
        )
        self.handler.run()
        log.info("Classification stream started; press 'q' to quit")

    def process_frame(self, frame) -> None:
        if frame is None:
            return
        image = frame.copy()
        self.frame_count += 1
        result = self.classifier.classify(image, topk=self.topk)

        log.info(
            "Frame %d: %s (%.3f) | Inference: %.1fms",
            self.frame_count,
            result.top1_name,
            result.top1_confidence or 0.0,
            result.inference_time * 1000,
        )
        image = self.classifier.draw_classification(image, result, topk=self.topk)

        if self._pub is not None:
            ok, buf = cv2.imencode(
                ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if ok:
                msg = CompressedImage()
                msg.header.stamp = self._pub_node.get_clock().now().to_msg()
                msg.format = "jpeg"
                msg.data = buf.tobytes()
                self._pub.publish(msg)

    def cleanup(self) -> None:
        self.handler.cleanup()
        if self._pub_node is not None:
            nectar.remove_node(self._pub_node)
            try:
                self._pub_node.destroy_node()
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time image classification stream")
    parser.add_argument("--model", default="yolo26n-cls.pt")
    parser.add_argument("--framework", default="", help="ultralytics | transformers")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--camera-source", default="webcam")
    parser.add_argument("--topic", default="/image_raw")
    parser.add_argument("--compressed", action="store_true")
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--no-show", dest="show_result", action="store_false")
    parser.set_defaults(show_result=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--publish-topic", default="/classification/compressed")
    parser.add_argument("--jpeg-quality", type=int, default=80)
    args, _ = parser.parse_known_args()
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args = parse_args()
    nectar.init()
    stream = None
    try:
        stream = ClassifierStream(args)
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
