#!/usr/bin/env python3
"""Real-time image classification over a camera stream.

Examples::

    python classifier_example.py --model yolo26n-cls.pt
    python classifier_example.py --model google/vit-base-patch16-224 --framework transformers
"""

import argparse
import logging
import os
import uuid
from typing import Optional

import cv2
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

import nectar
from nectar.ai.classification import Classifier
from nectar.ai.core import Framework
from nectar.vision.camera import ImageHandler, OpenCVConfig, ROSConfig

log = logging.getLogger("classifier_example")


def _camera_config(source: str):
    if source.startswith("/"):
        return ROSConfig(topic=source)
    if os.path.isfile(source):
        return None
    if source.lower() in ("webcam", "opencv"):
        return OpenCVConfig(device_index=0, width=1280, height=720)
    return None


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
            self._pub = self._pub_node.create_publisher(CompressedImage, args.topic, 1)
            log.info("Publishing annotated frames on %s", args.topic)

        self.handler = ImageHandler(
            image_source=args.camera_source,
            config=_camera_config(args.camera_source),
            show_result="Classification Stream" if args.show_result else None,
            image_processing_callback=self.process_frame,
        )
        self.handler.run()
        log.info("Classification stream started; press 'q' to quit")

    def process_frame(self, frame) -> None:
        if frame is None:
            return
        self.frame_count += 1
        result = self.classifier.classify(frame, topk=self.topk)

        log.info(
            "Frame %d: %s (%.3f) | Inference: %.1fms",
            self.frame_count,
            result.top1_name,
            result.top1_confidence or 0.0,
            result.inference_time * 1000,
        )
        annotated = self.classifier.draw_classification(frame, result, topk=self.topk)
        frame[:] = annotated

        if self._pub is not None:
            ok, buf = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if ok:
                msg = CompressedImage()
                msg.format = "jpeg"
                msg.data = buf.tobytes()
                self._pub.publish(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Real-time image classification stream")
    parser.add_argument("--model", default="yolo26n-cls.pt")
    parser.add_argument("--framework", default="", help="ultralytics | transformers")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--camera-source", default="webcam")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--no-show", dest="show_result", action="store_false")
    parser.set_defaults(show_result=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--topic", default="/classification/compressed")
    parser.add_argument("--jpeg-quality", type=int, default=80)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    nectar.init()
    try:
        ClassifierStream(args)
        nectar.spin()
    finally:
        nectar.shutdown()


if __name__ == "__main__":
    main()
