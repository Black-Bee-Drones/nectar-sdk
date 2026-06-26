"""Core functional checks: the ROS 2 runtime and cv_bridge interop.

These prove the foundation every other module stands on actually works end to
end: the SDK executor spins, a custom ``nectar_interfaces`` message makes a full
publish->subscribe round-trip, and cv_bridge converts both ways with the pinned
numpy ABI.
"""

from __future__ import annotations

import threading

import numpy as np

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec


def _ros_message_roundtrip() -> str:
    from nectar_interfaces.msg import LineInfo

    helpers.ensure_ros()
    node = helpers.make_node("diag_core")

    received: dict = {}
    got = threading.Event()

    def _on_msg(msg: "LineInfo") -> None:
        received["angle"] = msg.angle
        received["center_x"] = msg.center_x
        got.set()

    sub = node.create_subscription(LineInfo, "/nectar_diag/line", _on_msg, 10)
    pub = node.create_publisher(LineInfo, "/nectar_diag/line", 10)

    out = LineInfo(center_x=12.5, center_y=7.0, angle=0.75, width=3.0, height=4.0)
    ok = helpers.publish_until(pub, out, got, timeout=5.0)

    node.destroy_subscription(sub)
    node.destroy_publisher(pub)

    if not ok:
        raise Fail("no message received within 5s (rclpy pub/sub round-trip failed)")
    if abs(received.get("angle", -1) - 0.75) > 1e-6:
        raise Fail(f"payload mismatch: angle={received.get('angle')}")
    return "nectar_interfaces/LineInfo pub->sub OK"


def _cv_bridge_roundtrip() -> str:
    from cv_bridge import CvBridge

    bridge = CvBridge()
    src = (np.random.rand(48, 64, 3) * 255).astype(np.uint8)
    msg = bridge.cv2_to_imgmsg(src, encoding="bgr8")
    back = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
    if not np.array_equal(src, back):
        raise Fail("cv_bridge round-trip altered the image")
    return f"cv_bridge bgr8 round-trip OK ({src.shape[1]}x{src.shape[0]})"


MODULE = ModuleSpec(
    key="core",
    title="Core runtime",
    install="core install",
    checks=[
        Check("rclpy + nectar_interfaces round-trip", _ros_message_roundtrip),
        Check("cv_bridge image round-trip", _cv_bridge_roundtrip),
    ],
)
