"""Localization functional checks: the vision-pose bridge, both backends.

The Isaac ROS Visual SLAM producer needs a Jetson and a RealSense, so it is not
exercised here; the consumer bridge that feeds the FCU is fully testable with a
synthetic VSLAM pose. The mavros backend is asserted by a ROS republish; the
mavlink backend by capturing a real ``VISION_POSITION_ESTIMATE`` on a loopback
FCU.
"""

from __future__ import annotations

import threading
import time

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec


def _vision_pose_mavros() -> str:
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.localization.vision_pose_bridge import MavrosVisionRelay

    in_topic = "/nectar_diag/vo_pose_cov"
    out_topic = "/nectar_diag/mavros_vision_pose"

    helpers.ensure_ros()
    node = helpers.make_node("diag_loc_mavros")
    relay = MavrosVisionRelay(node=node, input_topic=in_topic, output_topic=out_topic, frame_id="")
    relay.start()

    got = threading.Event()
    received: dict = {}

    def _on_out(msg: "PoseWithCovarianceStamped") -> None:
        received["x"] = msg.pose.pose.position.x
        got.set()

    sub = node.create_subscription(
        PoseWithCovarianceStamped, out_topic, _on_out, qos_profile_sensor_data
    )
    pub = node.create_publisher(PoseWithCovarianceStamped, in_topic, qos_profile_sensor_data)

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = "map"
    msg.pose.pose.position.x = 4.2
    msg.pose.pose.orientation.w = 1.0
    ok = helpers.publish_until(pub, msg, got, timeout=5.0)

    node.destroy_subscription(sub)
    node.destroy_publisher(pub)
    if not ok:
        raise Fail("VSLAM pose not relayed to the mavros vision-pose topic")
    if abs(received.get("x", 0.0) - 4.2) > 1e-3:
        raise Fail(f"relayed pose payload wrong: x={received.get('x')}")
    return "VSLAM pose -> /mavros/vision_pose relay OK"


def _vision_pose_mavlink() -> str:
    helpers.require_module("pymavlink", "pymavlink not installed (make python-sensors)")
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.mavlink import VisionPoseBridge

    topic = "/nectar_diag/vo_pose_cov"
    port = helpers.free_udp_port()
    fcu = helpers.FakeFcu(port).start()
    capture = None
    try:
        conn = helpers.mavlink_connection_to(port)
        helpers.ensure_ros()
        node = helpers.make_node("diag_loc_mavlink")
        bridge = VisionPoseBridge(node=node, connection=conn, topic=topic)
        bridge.start()

        pub = node.create_publisher(PoseWithCovarianceStamped, topic, qos_profile_sensor_data)
        msg = PoseWithCovarianceStamped()
        msg.pose.pose.position.x = 1.5
        msg.pose.pose.orientation.w = 1.0

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            pub.publish(msg)
            capture = fcu.wait_for("VISION_POSITION_ESTIMATE", timeout=0.3)
            if capture is not None:
                break
    finally:
        fcu.stop()

    if capture is None:
        raise Fail("no VISION_POSITION_ESTIMATE emitted to the loopback FCU")
    return "VSLAM pose -> MAVLink VISION_POSITION_ESTIMATE OK"


MODULE = ModuleSpec(
    key="localization",
    title="Localization (vision-pose bridge)",
    install="make python-control",
    checks=[
        Check("vision-pose relay (mavros backend)", _vision_pose_mavros),
        Check("vision-pose bridge (mavlink backend)", _vision_pose_mavlink),
    ],
)
