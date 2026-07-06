#!/usr/bin/env python3
"""Real-time object detection over a camera stream.

Examples::

    python detector_example.py --model yolov8n.pt --confidence 0.5
    python detector_example.py --model facebook/detr-resnet-50 --framework transformers
    python detector_example.py --model rfdetr-medium --framework rfdetr --publish
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
from nectar.ai.detection import Detector, Framework
from nectar.vision.camera import ImageHandler, OpenCVConfig, ROSConfig

log = logging.getLogger("detector_example")


def _camera_config(source: str):
    """Return a config matching the camera source kind.

    For non-OpenCV registered sources (realsense, t265, oakd, c920, imx219, ...)
    we return None so each driver uses its own default config; forwarding an
    OpenCVConfig to those drivers would crash on missing fields.
    """
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


class DetectorStream:
    def __init__(self, args: argparse.Namespace) -> None:
        if args.hf_token:
            os.environ["HF_TOKEN"] = args.hf_token

        self.confidence = args.confidence
        self.annotator_type = args.annotator_type
        self.show_labels = args.show_labels
        self.show_confidence = args.show_confidence
        self.show_class = args.show_class
        self.jpeg_quality = args.jpeg_quality
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

        self._pub_node: Optional[Node] = None
        self._pub = None
        if args.publish:
            self._pub_node = Node(
                f"nectar_detector_pub_{uuid.uuid4().hex[:8]}",
                start_parameter_services=False,
            )
            nectar.add_node(self._pub_node)
            self._pub = self._pub_node.create_publisher(CompressedImage, args.topic, 1)
            log.info("Publishing annotated frames on %s", args.topic)

        self.handler = ImageHandler(
            image_source=args.camera_source,
            config=_camera_config(args.camera_source),
            show_result="Detection Stream" if args.show_result else None,
            image_processing_callback=self.process_frame,
        )
        self.handler.run()
        log.info("Detection stream started; press 'q' to quit")

    def process_frame(self, frame) -> None:
        if frame is None:
            return
        self.frame_count += 1
        result = self.detector.detect(frame, conf=self.confidence)
        self.total_detections += len(result)

        if len(result) > 0:
            log.info(
                "Frame %d: %d detections | Inference: %.1fms",
                self.frame_count,
                len(result),
                result.inference_time * 1000,
            )
            annotated = self.detector.draw_detections(
                image=frame,
                result=result,
                show_labels=self.show_labels,
                show_confidence=self.show_confidence,
                show_class=self.show_class,
                annotator_type=self.annotator_type,
                thickness=2,
                text_scale=0.6,
            )
            frame[:] = annotated

        self._overlay(frame, result)

        if self._pub is not None:
            ok, buf = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if ok:
                msg = CompressedImage()
                msg.header.stamp = self._pub_node.get_clock().now().to_msg()
                msg.header.frame_id = "down_camera"
                msg.format = "jpeg"
                msg.data = buf.tobytes()
                self._pub.publish(msg)

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
        if self._pub_node is not None:
            nectar.remove_node(self._pub_node)
            try:
                self._pub_node.destroy_node()
            except Exception:
                pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Real-time object detection")
    p.add_argument("--model", default="yolov8n.pt")
    p.add_argument("--framework", default="")
    p.add_argument("--confidence", type=float, default=0.25)
    p.add_argument("--camera-source", default="webcam")
    p.add_argument("--show-result", action="store_true", default=True)
    p.add_argument("--no-show", dest="show_result", action="store_false")
    p.add_argument("--annotator-type", default="color")
    p.add_argument("--show-labels", action="store_true", default=True)
    p.add_argument("--show-confidence", action="store_true", default=True)
    p.add_argument("--show-class", action="store_true", default=True)
    p.add_argument("--device", default="auto")
    p.add_argument("--hf-token", default="")
    p.add_argument("--publish", action="store_true")
    p.add_argument("--topic", default="/inference/compressed")
    p.add_argument("--jpeg-quality", type=int, default=80)
    args, _ = p.parse_known_args()
    return args


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    nectar.init()
    args = parse_args()
    stream = None
    try:
        stream = DetectorStream(args)
        nectar.spin()
    except KeyboardInterrupt:
        pass
    finally:
        if stream is not None:
            stream.cleanup()
        nectar.shutdown()


if __name__ == "__main__":
    main()
