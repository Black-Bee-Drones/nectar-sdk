#!/usr/bin/env python3
"""Real-time image classification over a camera stream.

Examples::

    python classifier_example.py --model yolo26n-cls.pt
    python classifier_example.py --model google/vit-base-patch16-224 --framework transformers
    python classifier_example.py --source /image_raw/compressed --compressed --publish --no-show
"""

import argparse
import logging
import os
from typing import Optional

import nectar
from nectar.ai.classification import Classifier
from nectar.ai.core import Framework
from nectar.vision.camera import ImageHandler, add_camera_arguments, parse_camera_args
from nectar.vision.stream import CompressedFramePublisher, add_stream_arguments

log = logging.getLogger("classifier_example")


def _resolve_framework(framework_str: str) -> Optional[Framework]:
    if not framework_str:
        return None
    try:
        return Framework(framework_str.lower())
    except ValueError:
        log.warning("Unknown framework '%s', falling back to auto-detect", framework_str)
        return None


class ClassifierStream:
    def __init__(self, args: argparse.Namespace, source: str, config) -> None:
        if args.hf_token:
            os.environ["HF_TOKEN"] = args.hf_token

        self.topk = args.topk
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

        self._pub: Optional[CompressedFramePublisher] = None
        if args.publish:
            self._pub = CompressedFramePublisher(args.publish_topic, jpeg_quality=args.jpeg_quality)
            log.info("Publishing annotated frames on %s", args.publish_topic)

        self.handler = ImageHandler(
            image_source=source,
            config=config,
            show_result="Classification Stream" if args.show else None,
            image_processing_callback=self.process_frame,
        )
        self.handler.run()
        log.info("Classification stream started; press 'q' to quit")

    def process_frame(self, frame):
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
            self._pub.publish(image)
        return image

    def cleanup(self) -> None:
        self.handler.cleanup()
        if self._pub is not None:
            self._pub.cleanup()


def parse_args():
    parser = argparse.ArgumentParser(description="Real-time image classification stream")
    add_camera_arguments(parser)
    add_stream_arguments(parser, show_default=True, publish_topic="/classification/compressed")
    parser.add_argument("--model", default="yolo26n-cls.pt")
    parser.add_argument("--framework", default="", help="ultralytics | transformers")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--hf-token", default="")
    return parse_camera_args(parser)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args, _, source, config = parse_args()
    nectar.init()
    stream = None
    try:
        stream = ClassifierStream(args, source, config)
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
