"""Localization functional tests: the vision-pose bridge, both backends.

The Isaac ROS Visual SLAM producer needs a Jetson and a RealSense, so it is not
exercised here; the consumer bridge that feeds the FCU is fully testable with a
synthetic VSLAM pose. The mavros backend is asserted by a ROS republish; the
mavlink backend by capturing a real ``VISION_POSITION_ESTIMATE`` on a loopback FCU.
"""

from __future__ import annotations

import threading
import time

import pytest

pytestmark = pytest.mark.localization


def test_vision_pose_mavros(ros_node):
    """A VSLAM pose is relayed onto the MAVROS vision-pose topic with its payload intact."""
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.localization.vision_pose_bridge import MavrosVisionRelay

    in_topic = "/nectar_test/vo_pose_cov"
    out_topic = "/nectar_test/mavros_vision_pose"

    relay = MavrosVisionRelay(
        node=ros_node, input_topic=in_topic, output_topic=out_topic, frame_id=""
    )
    relay.start()

    got = threading.Event()
    received: dict = {}

    def _on_out(msg: "PoseWithCovarianceStamped") -> None:
        received["x"] = msg.pose.pose.position.x
        got.set()

    ros_node.create_subscription(
        PoseWithCovarianceStamped, out_topic, _on_out, qos_profile_sensor_data
    )
    pub = ros_node.create_publisher(PoseWithCovarianceStamped, in_topic, qos_profile_sensor_data)

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = "map"
    msg.pose.pose.position.x = 4.2
    msg.pose.pose.orientation.w = 1.0
    import helpers

    ok = helpers.publish_until(pub, msg, got, timeout=5.0)

    assert ok, "VSLAM pose not relayed to the mavros vision-pose topic"
    assert abs(received.get("x", 0.0) - 4.2) < 1e-3, f"relayed payload wrong: x={received.get('x')}"


def test_vision_pose_mavlink(ros_node, fake_fcu):
    """A VSLAM pose is forwarded to the FCU as a VISION_POSITION_ESTIMATE over MAVLink."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.mavlink import VisionPoseBridge

    topic = "/nectar_test/vo_pose_cov"
    conn = helpers.mavlink_connection_to(fake_fcu.port)
    bridge = VisionPoseBridge(node=ros_node, connection=conn, topic=topic)
    bridge.start()

    pub = ros_node.create_publisher(PoseWithCovarianceStamped, topic, qos_profile_sensor_data)
    msg = PoseWithCovarianceStamped()
    msg.pose.pose.position.x = 1.5
    msg.pose.pose.orientation.w = 1.0

    capture = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        capture = fake_fcu.wait_for("VISION_POSITION_ESTIMATE", timeout=0.3)
        if capture is not None:
            break

    assert capture is not None, "no VISION_POSITION_ESTIMATE emitted to the loopback FCU"
