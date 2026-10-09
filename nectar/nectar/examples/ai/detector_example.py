#!/usr/bin/env python3
"""Real-time object detection over a camera stream.

Examples::

    python detector_example.py --model yolov8n.pt --confidence 0.5
    python detector_example.py --model facebook/detr-resnet-50 --framework transformers
    python detector_example.py --model rfdetr-medium --framework rfdetr --publish
    python detector_example.py --source /image_raw/compressed --compressed --publish --no-show
"""

import argparse
import logging
import os
from typing import Optional

import cv2

import nectar
from nectar.ai.core import Framework
from nectar.ai.detection import Detector
from nectar.vision.camera import ImageHandler, add_camera_arguments, parse_camera_args
from nectar.vision.stream import CompressedFramePublisher, add_stream_arguments

log = logging.getLogger("detector_example")


def _resolve_framework(framework_str: str) -> Optional[Framework]:
    if not framework_str:
        return None
    try:
        return Framework(framework_str.lower())
    except ValueError:
        log.warning("Unknown framework '%s', falling back to auto-detect", framework_str)
        return None


class DetectorStream:
    def __init__(self, args: argparse.Namespace, source: str, config) -> None:
        if args.hf_token:
            os.environ["HF_TOKEN"] = args.hf_token

        self.confidence = args.confidence
        self.annotator_type = args.annotator_type
        self.show_labels = args.show_labels
        self.show_confidence = args.show_confidence
        self.show_class = args.show_class
        self.frame_count = 0
        self.total_detections = 0

        framework = _resolve_framework(args.framework)
        log.info("Loading model: %s (device=%s)", args.model, args.device)
        self.detector = Detector(
            model_source=args.model,
            framework=framework,
            device=args.device,
            confidence_threshold=self.confidence,
        )
        self.detector.load()
        log.info("Model loaded -- framework: %s", self.detector.framework.value)

        self._pub: Optional[CompressedFramePublisher] = None
        if args.publish:
            self._pub = CompressedFramePublisher(args.publish_topic, jpeg_quality=args.jpeg_quality)
            log.info("Publishing annotated frames on %s", args.publish_topic)

        self.handler = ImageHandler(
            image_source=source,
            config=config,
            show_result="Detection Stream" if args.show else None,
            image_processing_callback=self.process_frame,
        )
        self.handler.run()
        log.info("Detection stream started; press 'q' to quit")

    def process_frame(self, frame):
        if frame is None:
            return
        image = frame.copy()
        self.frame_count += 1
        result = self.detector.detect(image, conf=self.confidence)
        self.total_detections += len(result)

        if len(result) > 0:
            log.info(
                "Frame %d: %d detections | Inference: %.1fms",
                self.frame_count,
                len(result),
                result.inference_time * 1000,
            )
            image = self.detector.draw_detections(
                image=image,
                result=result,
                show_labels=self.show_labels,
                show_confidence=self.show_confidence,
                show_class=self.show_class,
                annotator_type=self.annotator_type,
                thickness=2,
                text_scale=0.6,
            )

        self._overlay(image, result)

        if self._pub is not None:
            self._pub.publish(image)
        return image

    def _overlay(self, frame, result) -> None:
        fps = 1.0 / result.inference_time if result.inference_time > 0 else 0
        lines = [
            f"Framework: {self.detector.framework.value}",
            f"FPS: {fps:.1f}",
            f"Detections: {len(result)}",
            f"Total: {self.total_detections}",
        ]
        y = 10
        for i, line in enumerate(lines):
            yp = y + (i + 1) * 25
            (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(frame, (5, yp - th - 5), (10 + tw, yp + 5), (0, 0, 0), -1)
            cv2.putText(
                frame,
                line,
                (10, yp),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

    def cleanup(self) -> None:
        log.info(
            "Processed %d frames, total detections=%d",
            self.frame_count,
            self.total_detections,
        )
        self.handler.cleanup()
        if self._pub is not None:
            self._pub.cleanup()


def parse_args():
    p = argparse.ArgumentParser(description="Real-time object detection")
    add_camera_arguments(p)
    add_stream_arguments(p, show_default=True, publish_topic="/inference/compressed")
    p.add_argument("--model", default="yolov8n.pt")
    p.add_argument("--framework", default="")
    p.add_argument("--confidence", type=float, default=0.25)
    p.add_argument("--annotator-type", default="color")
    p.add_argument("--show-labels", action="store_true", default=True)
    p.add_argument("--show-confidence", action="store_true", default=True)
    p.add_argument("--show-class", action="store_true", default=True)
    p.add_argument("--device", default="auto")
    p.add_argument("--hf-token", default="")
    return parse_camera_args(p)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    args, _, source, config = parse_args()
    nectar.init()
    stream = None
    try:
        stream = DetectorStream(args, source, config)
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
