"""Core functional tests: the ROS 2 runtime and cv_bridge interop.

These prove the foundation every other module stands on works end to end: the
SDK executor spins, a custom ``nectar_interfaces`` message makes a full
publish->subscribe round-trip, and cv_bridge converts both ways with the pinned
numpy ABI.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

pytestmark = pytest.mark.core


def test_ros_message_roundtrip(ros_node):
    """A nectar_interfaces/LineInfo message survives a pub->sub round-trip intact."""
    from nectar_interfaces.msg import LineInfo

    received: dict = {}
    got = threading.Event()

    def _on_msg(msg: "LineInfo") -> None:
        received["angle"] = msg.angle
        received["center_x"] = msg.center_x
        got.set()

    ros_node.create_subscription(LineInfo, "/nectar_test/line", _on_msg, 10)
    pub = ros_node.create_publisher(LineInfo, "/nectar_test/line", 10)

    out = LineInfo(center_x=12.5, center_y=7.0, angle=0.75, width=3.0, height=4.0)
    import helpers

    ok = helpers.publish_until(pub, out, got, timeout=5.0)

    assert ok, "no message received within 5s (rclpy pub/sub round-trip failed)"
    assert abs(received.get("angle", -1) - 0.75) < 1e-6, f"payload mismatch: {received}"


def test_cv_bridge_roundtrip():
    """cv_bridge converts a uint8 BGR image to a ROS Image and back unchanged."""
    from cv_bridge import CvBridge

    bridge = CvBridge()
    src = (np.random.rand(48, 64, 3) * 255).astype(np.uint8)
    msg = bridge.cv2_to_imgmsg(src, encoding="bgr8")
    back = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
    assert np.array_equal(src, back), "cv_bridge round-trip altered the image"
