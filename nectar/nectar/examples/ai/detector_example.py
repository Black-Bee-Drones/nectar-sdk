#!/usr/bin/env python3
"""
Real-time Object Detection Example.

Demonstrates real-time object detection using the Detector class
with webcam input and ROS2 integration. Supports multiple frameworks
(Ultralytics YOLO, Transformers DETR, RF-DETR).

Examples
--------
Run with local YOLO model:

    ros2 run nectar detector_example --ros-args \
        -p model_source:="yolov8n.pt" \
        -p confidence:=0.5

Run with HuggingFace YOLO model (user/repo:file format):

    ros2 run nectar detector_example --ros-args \
        -p model_source:="blackbeedrones/cbr-25-base:yolov11n.pt"

    ros2 run nectar detector_example --ros-args \
        -p model_source:="blackbeedrones/cbr-25-base:yolov11n.onnx"

Run with Transformers DETR (model ID format):

    ros2 run nectar detector_example --ros-args \
        -p model_source:="facebook/detr-resnet-50" \
        -p framework:="transformers"

Run with RF-DETR:

    ros2 run nectar detector_example --ros-args \
        -p model_source:="rfdetr-base" \
        -p framework:="rfdetr"
"""

import os

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

from nectar.ai.detection import Detector, Framework
from nectar.vision.camera import ImageHandler, OpenCVConfig


class DetectorStreamNode(Node):
    """
    ROS2 node for real-time object detection.
    """

    def __init__(self):
        super().__init__("detector_stream_node")

        # Declare parameters
        self.declare_parameter("model_source", "yolov8n.pt")
        self.declare_parameter("framework", "")
        self.declare_parameter("confidence", 0.25)
        self.declare_parameter("camera_source", "webcam")
        self.declare_parameter("show_result", True)
        self.declare_parameter("annotator_type", "color")
        self.declare_parameter("show_labels", True)
        self.declare_parameter("show_confidence", True)
        self.declare_parameter("show_class", True)
        self.declare_parameter("device", "auto")
        self.declare_parameter("hf_token", "")
        self.declare_parameter("publish_result", False)
        self.declare_parameter("topic", "/inference/compressed")
        self.declare_parameter("jpeg_quality", 80)

        # Get parameters
        model_source = self.get_parameter("model_source").value
        framework_str = self.get_parameter("framework").value
        self.confidence = self.get_parameter("confidence").value
        camera_source = self.get_parameter("camera_source").value
        show_result = self.get_parameter("show_result").value
        self.annotator_type = self.get_parameter("annotator_type").value
        self.show_labels = self.get_parameter("show_labels").value
        self.show_confidence = self.get_parameter("show_confidence").value
        self.show_class = self.get_parameter("show_class").value
        device = self.get_parameter("device").value
        hf_token = self.get_parameter("hf_token").value
        self.publish_result = self.get_parameter("publish_result").value
        topic = self.get_parameter("topic").get_parameter_value().string_value
        self.jpeg_quality = int(self.get_parameter("jpeg_quality").value)

        # Set HF token if provided
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            self.get_logger().info("Using provided HuggingFace token")
        elif os.environ.get("HF_TOKEN"):
            self.get_logger().info("Using HF_TOKEN from environment")

        # Resolve framework
        framework = None
        if framework_str:
            try:
                framework = Framework(framework_str.lower())
                self.get_logger().info(f"Using explicit framework: {framework.value}")
            except ValueError:
                self.get_logger().warning(f"Unknown framework '{framework_str}', using auto-detect")

        self.get_logger().info(f"Loading model: {model_source}")
        self.get_logger().info(f"Device preference: {device}")

        # Initialize detector
        self.detector = Detector(
            model_source=model_source,
            framework=framework,
            device=device,
            confidence_threshold=self.confidence,
        )
        self.detector.load()

        self.get_logger().info(
            f"Model loaded successfully! Framework: {self.detector.framework.value}"
        )

        self.pub = self.create_publisher(CompressedImage, topic, 1) if self.publish_result else None
        if self.publish_result:
            self.get_logger().info(f"Publishing annotated frames on {topic}")

        # Log class names
        if self.detector.class_names:
            num_classes = len(self.detector.class_names)
            self.get_logger().info(f"Model has {num_classes} classes")
            if num_classes <= 10:
                for idx, name in self.detector.class_names.items():
                    self.get_logger().info(f"  Class {idx}: {name}")

        # Setup camera
        camera_config = OpenCVConfig(device_index=0, width=1280, height=720)
        window_name = "Detection Stream" if show_result else None

        self.image_handler = ImageHandler(
            node=self,
            image_source=camera_source,
            config=camera_config,
            show_result=window_name,
            image_processing_callback=self.process_frame,
        )

        self.image_handler.run()

        self.get_logger().info("=" * 60)
        self.get_logger().info("Detection stream started!")
        self.get_logger().info(f"Framework: {self.detector.framework.value}")
        self.get_logger().info(f"Annotator: {self.annotator_type}")
        self.get_logger().info("Press 'q' in the window to quit")
        self.get_logger().info("=" * 60)

        self.frame_count = 0
        self.total_detections = 0

    def process_frame(self, frame):
        """Process each frame with detection and visualization."""
        if frame is None:
            return

        self.frame_count += 1

        # Run detection
        result = self.detector.detect(frame, conf=self.confidence)

        num_detections = len(result)
        self.total_detections += num_detections

        if num_detections > 0:
            self.get_logger().info(
                f"Frame {self.frame_count}: {num_detections} detections | "
                f"Inference: {result.inference_time * 1000:.1f}ms",
                throttle_duration_sec=2.0,
            )

            for det in result.detections[:3]:
                self.get_logger().debug(
                    f"  - {det.class_name}: {det.confidence:.2f} at {det.center}",
                    throttle_duration_sec=5.0,
                )

        # Draw detections
        if num_detections > 0 or self.frame_count == 1:
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

        self._add_stats_overlay(frame, result)

        if self.pub is None:
            return

        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            return

        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "down_camera"
        msg.format = "jpeg"
        msg.data = buf.tobytes()

        self.pub.publish(msg)

    def _add_stats_overlay(self, frame, result):
        """Add statistics overlay to the frame."""
        fps = 1.0 / result.inference_time if result.inference_time > 0 else 0

        overlay_lines = [
            f"Framework: {self.detector.framework.value}",
            f"FPS: {fps:.1f}",
            f"Detections: {len(result)}",
            f"Total: {self.total_detections}",
        ]

        y_offset = 10
        for i, line in enumerate(overlay_lines):
            y_pos = y_offset + (i + 1) * 25

            (text_width, text_height), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)

            cv2.rectangle(
                frame,
                (5, y_pos - text_height - 5),
                (10 + text_width, y_pos + 5),
                (0, 0, 0),
                -1,
            )

            cv2.putText(
                frame,
                line,
                (10, y_pos),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

    def destroy_node(self):
        """Cleanup on shutdown."""
        self.get_logger().info("\nShutting down...")
        self.get_logger().info(f"Processed {self.frame_count} frames")
        self.get_logger().info(f"Total detections: {self.total_detections}")

        if self.frame_count > 0:
            avg_detections = self.total_detections / self.frame_count
            self.get_logger().info(f"Average detections per frame: {avg_detections:.2f}")

        self.image_handler.cleanup()
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = None
    try:
        node = DetectorStreamNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if node:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
