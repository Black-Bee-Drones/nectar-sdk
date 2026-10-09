"""Stream CLI flags and JPEG frame publishing."""

from __future__ import annotations

import argparse
import uuid
from typing import Optional

import cv2
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage

from nectar import runtime as nectar_runtime

SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    durability=DurabilityPolicy.VOLATILE,
)


def add_stream_arguments(
    parser: argparse.ArgumentParser,
    *,
    show_default: bool = True,
    include_publish: bool = True,
    publish_topic: str = "/nectar/image/compressed",
) -> None:
    """Add ``--show`` / ``--no-show`` and optional annotated-image publish flags."""
    group = parser.add_argument_group("stream")
    group.add_argument("--show", dest="show", action="store_true", help="Show OpenCV preview")
    group.add_argument("--no-show", dest="show", action="store_false", help="Disable preview")
    parser.set_defaults(show=show_default)
    if include_publish:
        group.add_argument(
            "--publish",
            action="store_true",
            help="Publish processed frames as sensor_msgs/CompressedImage",
        )
        group.add_argument("--publish-topic", default=publish_topic)
        group.add_argument("--jpeg-quality", type=int, default=80)


def compressed_image_msg(
    frame,
    stamp,
    jpeg_quality: int = 80,
    frame_id: str = "camera",
) -> CompressedImage:
    """Encode a BGR frame as CompressedImage."""
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    msg = CompressedImage()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id
    msg.format = "jpeg"
    msg.data = buf.tobytes()
    return msg


class CompressedFramePublisher:
    """Publish JPEG frames on a ROS 2 topic.

    Pass ``node`` to reuse a node (vision ROS nodes). Omit it from scripts
    that are not already a Node.
    """

    def __init__(
        self,
        topic: str,
        *,
        jpeg_quality: int = 80,
        node: Optional[Node] = None,
        frame_id: str = "camera",
    ) -> None:
        self._jpeg_quality = jpeg_quality
        self._frame_id = frame_id
        self._owns_node = node is None
        if node is None:
            nectar_runtime.ensure_context()
            self._node = Node(
                f"nectar_img_pub_{uuid.uuid4().hex[:8]}",
                start_parameter_services=False,
            )
            nectar_runtime.add_node(self._node)
        else:
            self._node = node
        self._pub = self._node.create_publisher(CompressedImage, topic, SENSOR_QOS)

    def publish(self, frame) -> None:
        if frame is None:
            return
        msg = compressed_image_msg(
            frame,
            self._node.get_clock().now().to_msg(),
            self._jpeg_quality,
            self._frame_id,
        )
        self._pub.publish(msg)

    def cleanup(self) -> None:
        if not self._owns_node:
            return
        nectar_runtime.remove_node(self._node)
        try:
            self._node.destroy_node()
        except Exception:
            pass
