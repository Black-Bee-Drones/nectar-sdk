"""Localization functional tests: the vision-pose and vision-speed bridges.

The Isaac ROS Visual SLAM producer needs a Jetson and a RealSense, so it is not
exercised here; the consumer bridges that feed the FCU are fully testable with a
synthetic VSLAM pose. The mavros backend is asserted by a ROS republish; the
mavlink backend by capturing a real ``VISION_POSITION_ESTIMATE`` /
``VISION_SPEED_ESTIMATE`` on a loopback FCU.
"""

from __future__ import annotations

import math
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

    ros_node.create_subscription(PoseWithCovarianceStamped, out_topic, _on_out, 10)
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


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(6)) for j in range(6)] for i in range(6)]


def _transpose(a):
    return [[a[j][i] for j in range(6)] for i in range(6)]


def test_pose_covariance_enu_to_ned_matches_mavros():
    """The signed permutation reproduces MAVROS' ``P (D C D) Pᵀ`` congruence."""
    import random

    from nectar.control.localization.frames import pose_covariance_enu_to_ned

    # ftf::transform_static_frame(Covariance6d, ENU_TO_NED): D negates z and yaw,
    # P swaps x<->y and roll<->pitch.
    d = [[0.0] * 6 for _ in range(6)]
    for i, sign in enumerate((1, 1, -1, 1, 1, -1)):
        d[i][i] = sign
    p = [[0.0] * 6 for _ in range(6)]
    for col, row in enumerate((1, 0, 2, 4, 3, 5)):
        p[row][col] = 1.0

    random.seed(0)
    for _ in range(50):
        m = [[random.uniform(-3.0, 3.0) for _ in range(6)] for _ in range(6)]
        cov = _matmul(m, _transpose(m))  # symmetric, positive semi-definite
        expected = _matmul(_matmul(p, _matmul(_matmul(d, cov), d)), _transpose(p))

        got = pose_covariance_enu_to_ned([cov[i][j] for i in range(6) for j in range(6)])
        for i in range(6):
            for j in range(6):
                assert abs(got[i * 6 + j] - expected[i][j]) < 1e-12


def test_covariance_urt_packing():
    """The 6x6 diagonal lands on the elements ArduPilot reads (0, 6, 11, 15, 18, 20)."""
    from nectar.control.localization.frames import covariance_urt_to_mavlink

    diagonal = [11.0, 22.0, 33.0, 44.0, 55.0, 66.0]
    cov = [0.0] * 36
    for i, value in enumerate(diagonal):
        cov[i * 6 + i] = value

    urt = covariance_urt_to_mavlink(cov)
    assert len(urt) == 21
    assert [urt[k] for k in (0, 6, 11, 15, 18, 20)] == diagonal


def test_pose_orientation_matches_mavros():
    """``euler_enu_to_ned`` equals MAVROS' quaternion composition, gimbal lock included.

    MAVROS builds ``NED_ENU_Q * q * AIRCRAFT_BASELINK_Q`` and decomposes it ZYX.
    The comparison is on the rotation the triple encodes, not the raw angles: at
    gimbal lock roll and yaw are not independently observable, and our yaw is
    unwrapped. ArduPilot only ever sees ``Quaternion::from_euler`` of the triple.
    """
    import random

    from tf_transformations import (
        euler_from_quaternion,
        quaternion_from_euler,
        quaternion_matrix,
        quaternion_multiply,
    )

    from nectar.control.localization.frames import euler_enu_to_ned

    # ftf::quaternion_from_rpy is intrinsic ZYX, i.e. tf's 'sxyz' with (r, p, y).
    ned_enu_q = quaternion_from_euler(math.pi, 0.0, math.pi / 2.0)
    aircraft_baselink_q = quaternion_from_euler(math.pi, 0.0, 0.0)

    def mavros_euler(quat):
        m = quaternion_matrix(
            quaternion_multiply(ned_enu_q, quaternion_multiply(quat, aircraft_baselink_q))
        )
        sin_pitch = max(-1.0, min(1.0, -m[2][0]))
        cos_pitch = math.hypot(m[2][1], m[2][2])
        if cos_pitch > 1e-9:
            return (
                math.atan2(m[2][1], m[2][2]),
                math.atan2(sin_pitch, cos_pitch),
                math.atan2(m[1][0], m[0][0]),
            )
        if sin_pitch > 0:
            return (0.0, math.pi / 2.0, math.atan2(m[1][2], m[1][1]))
        return (0.0, -math.pi / 2.0, math.atan2(-m[1][2], m[1][1]))

    def rotation(euler):
        return quaternion_matrix(quaternion_from_euler(*euler))

    random.seed(0)
    samples = [
        (random.uniform(-math.pi, math.pi), pitch, random.uniform(-math.pi, math.pi))
        for pitch in [random.uniform(-1.57, 1.57) for _ in range(500)]
        # exact gimbal lock, where the two disagree on the angles but not the rotation
        + [math.pi / 2.0, -math.pi / 2.0]
    ]

    for roll, pitch, yaw in samples:
        quat = quaternion_from_euler(roll, pitch, yaw)
        ours = rotation(euler_enu_to_ned(*euler_from_quaternion(list(quat))))
        theirs = rotation(mavros_euler(quat))
        assert max(abs(ours[i][j] - theirs[i][j]) for i in range(3) for j in range(3)) < 1e-9


def test_vision_pose_mavlink_forwards_covariance(ros_node, fake_fcu):
    """The pose covariance reaches the FCU, swapped to NED like the MAVROS plugin."""
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
    msg.pose.pose.orientation.w = 1.0
    # Distinct ENU variances so the x/y swap is visible in the result.
    for i, variance in enumerate((0.01, 0.04, 0.09, 0.16, 0.25, 0.36)):
        msg.pose.covariance[i * 6 + i] = variance

    capture = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        capture = fake_fcu.wait_for("VISION_POSITION_ESTIMATE", timeout=0.3)
        if capture is not None:
            break

    assert capture is not None, "no VISION_POSITION_ESTIMATE emitted to the loopback FCU"
    # ArduPilot reads x, y, z, roll, pitch, yaw from these six elements; NED swaps
    # x with y and roll with pitch, and the diagonal is sign-invariant.
    got = [round(capture.covariance[k], 6) for k in (0, 6, 11, 15, 18, 20)]
    assert got == [0.04, 0.01, 0.09, 0.25, 0.16, 0.36], got


def test_vision_pose_mavlink_without_covariance_sends_zeros(ros_node, fake_fcu):
    """A plain PoseStamped source sends a zero covariance, as MAVROS does."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers
    from geometry_msgs.msg import PoseStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.mavlink import VisionPoseBridge

    topic = "/nectar_test/vo_pose"
    conn = helpers.mavlink_connection_to(fake_fcu.port)
    bridge = VisionPoseBridge(node=ros_node, connection=conn, topic=topic)
    bridge.start()

    pub = ros_node.create_publisher(PoseStamped, topic, qos_profile_sensor_data)
    msg = PoseStamped()
    msg.pose.orientation.w = 1.0

    capture = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        capture = fake_fcu.wait_for("VISION_POSITION_ESTIMATE", timeout=0.3)
        if capture is not None:
            break

    assert capture is not None, "no VISION_POSITION_ESTIMATE emitted to the loopback FCU"
    assert list(capture.covariance) == [0.0] * 21


def test_vision_pose_subscriber_updates_without_sending(ros_node, fake_fcu):
    """Subscribe-only companion path updates pose and emits no VISION_POSITION_ESTIMATE."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers
    from geometry_msgs.msg import PoseStamped
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.mavlink import VisionPoseSubscriber

    topic = "/nectar_test/vo_pose_sub_only"
    received: dict = {}
    got = threading.Event()

    def _on_pose(pose) -> None:
        received["x"] = pose.position.x
        received["yaw"] = pose.yaw
        got.set()

    sub = VisionPoseSubscriber(node=ros_node, topic=topic, on_pose=_on_pose)
    sub.start()

    pub = ros_node.create_publisher(PoseStamped, topic, qos_profile_sensor_data)
    msg = PoseStamped()
    msg.pose.position.x = 2.5
    msg.pose.orientation.w = 1.0

    ok = helpers.publish_until(pub, msg, got, timeout=5.0)
    assert ok, "VisionPoseSubscriber did not receive the VSLAM pose"
    assert abs(received.get("x", 0.0) - 2.5) < 1e-3

    # No sender on this link — the loopback FCU must stay quiet.
    capture = fake_fcu.wait_for("VISION_POSITION_ESTIMATE", timeout=0.5)
    assert capture is None, "subscribe-only path must not emit VISION_POSITION_ESTIMATE"


def _yaw_quaternion(yaw: float):
    """Return ``(x, y, z, w)`` for a rotation of ``yaw`` radians about the ENU z-axis."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def _odometry_msg(linear, quat):
    """A ``nav_msgs/Odometry`` with a body-frame twist and the matching attitude."""
    from nav_msgs.msg import Odometry

    msg = Odometry()
    msg.pose.pose.orientation.x, msg.pose.pose.orientation.y = quat[0], quat[1]
    msg.pose.pose.orientation.z, msg.pose.pose.orientation.w = quat[2], quat[3]
    msg.twist.twist.linear.x, msg.twist.twist.linear.y, msg.twist.twist.linear.z = linear
    return msg


def test_body_velocity_to_ned():
    """A body-frame FLU velocity is rotated by the attitude, then swapped to NED."""
    from nectar.control.localization.frames import body_velocity_to_ned

    # Level and facing the VSLAM x-axis: 1 m/s forward is 1 m/s along ENU x (east),
    # which is the NED y-axis.
    vx, vy, vz = body_velocity_to_ned((1.0, 0.0, 0.0), _yaw_quaternion(0.0))
    assert (round(vx, 6), round(vy, 6), round(vz, 6)) == (0.0, 1.0, 0.0)

    # Yawed 90 deg CCW: the same 1 m/s forward is now ENU y (north), i.e. NED x.
    vx, vy, vz = body_velocity_to_ned((1.0, 0.0, 0.0), _yaw_quaternion(math.pi / 2.0))
    assert (round(vx, 6), round(vy, 6), round(vz, 6)) == (1.0, 0.0, 0.0)

    # FLU z is up, NED z is down.
    vx, vy, vz = body_velocity_to_ned((0.0, 0.0, 1.0), _yaw_quaternion(0.0))
    assert (round(vx, 6), round(vy, 6), round(vz, 6)) == (0.0, 0.0, -1.0)


def test_vision_speed_mavros(ros_node):
    """A VSLAM twist is relayed onto the MAVROS vision-speed topic, rotated to ENU."""
    from geometry_msgs.msg import TwistStamped
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.localization.vision_pose_bridge import MavrosVisionSpeedRelay

    in_topic = "/nectar_test/vo_odometry"
    out_topic = "/nectar_test/mavros_vision_speed"

    relay = MavrosVisionSpeedRelay(
        node=ros_node, input_topic=in_topic, output_topic=out_topic, frame_id=""
    )
    relay.start()

    got = threading.Event()
    received: dict = {}

    def _on_out(msg: "TwistStamped") -> None:
        received["linear"] = (msg.twist.linear.x, msg.twist.linear.y, msg.twist.linear.z)
        got.set()

    ros_node.create_subscription(TwistStamped, out_topic, _on_out, 10)
    pub = ros_node.create_publisher(Odometry, in_topic, qos_profile_sensor_data)

    # 1 m/s forward while yawed 90 deg CCW -> 1 m/s along ENU y; the MAVROS plugin
    # does the ENU -> NED step itself, so the relay must stop at ENU.
    msg = _odometry_msg((1.0, 0.0, 0.0), _yaw_quaternion(math.pi / 2.0))

    import helpers

    ok = helpers.publish_until(pub, msg, got, timeout=5.0)

    assert ok, "VSLAM twist not relayed to the mavros vision-speed topic"
    linear = [round(v, 6) for v in received["linear"]]
    assert linear == [0.0, 1.0, 0.0], f"relay did not rotate body -> ENU: {linear}"


def test_vision_speed_mavlink(ros_node, fake_fcu):
    """A VSLAM twist is forwarded to the FCU as a VISION_SPEED_ESTIMATE in NED."""
    pytest.importorskip("pymavlink", reason="pymavlink not installed (make python-sensors)")
    import helpers
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data

    from nectar.control.mavlink import VisionSpeedBridge

    topic = "/nectar_test/vo_odometry"
    conn = helpers.mavlink_connection_to(fake_fcu.port)
    bridge = VisionSpeedBridge(node=ros_node, connection=conn, topic=topic)
    bridge.start()

    pub = ros_node.create_publisher(Odometry, topic, qos_profile_sensor_data)
    msg = _odometry_msg((1.0, 0.0, 0.0), _yaw_quaternion(math.pi / 2.0))

    capture = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        capture = fake_fcu.wait_for("VISION_SPEED_ESTIMATE", timeout=0.3)
        if capture is not None:
            break

    assert capture is not None, "no VISION_SPEED_ESTIMATE emitted to the loopback FCU"
    ned = [round(capture.x, 6), round(capture.y, 6), round(capture.z, 6)]
    assert ned == [1.0, 0.0, 0.0], f"velocity not converted to NED: {ned}"


def test_vision_speed_dds(ros_node):
    """The PX4 bridge attaches the VSLAM velocity to VehicleOdometry, in NED."""
    pytest.importorskip("px4_msgs", reason="px4_msgs not built into the workspace")
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    from px4_msgs.msg import VehicleOdometry
    from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy, qos_profile_sensor_data

    from nectar.control.px4.vision_bridge import Px4VisionOdometryBridge

    pose_topic = "/nectar_test/vo_pose_cov"
    speed_topic = "/nectar_test/vo_odometry"
    out_topic = "/nectar_test/vehicle_visual_odometry"

    bridge = Px4VisionOdometryBridge(
        node=ros_node,
        input_topic=pose_topic,
        output_topic=out_topic,
        speed_topic=speed_topic,
    )
    bridge.start()

    got = threading.Event()
    received: dict = {}

    def _on_out(msg: "VehicleOdometry") -> None:
        # Samples published before the first twist arrives legitimately carry no
        # velocity, so wait for one that does.
        if msg.velocity_frame == VehicleOdometry.VELOCITY_FRAME_UNKNOWN:
            return
        received["velocity"] = [round(float(v), 6) for v in msg.velocity]
        received["frame"] = msg.velocity_frame
        got.set()

    # PX4 publishes /fmu/in/* as BEST_EFFORT; the bridge matches it.
    sub_qos = QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=10
    )
    ros_node.create_subscription(VehicleOdometry, out_topic, _on_out, sub_qos)
    speed_pub = ros_node.create_publisher(Odometry, speed_topic, qos_profile_sensor_data)
    pose_pub = ros_node.create_publisher(
        PoseWithCovarianceStamped, pose_topic, qos_profile_sensor_data
    )

    speed_msg = _odometry_msg((1.0, 0.0, 0.0), _yaw_quaternion(math.pi / 2.0))
    pose_msg = PoseWithCovarianceStamped()
    pose_msg.pose.pose.orientation.w = 1.0

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not got.is_set():
        speed_pub.publish(speed_msg)
        pose_pub.publish(pose_msg)
        got.wait(0.05)

    assert got.is_set(), "no VehicleOdometry carrying a velocity was published"
    assert received["frame"] == VehicleOdometry.VELOCITY_FRAME_NED
    assert received["velocity"] == [1.0, 0.0, 0.0], f"velocity wrong: {received['velocity']}"


def test_vision_speed_dds_stale_velocity_drops_to_nan(ros_node):
    """A velocity older than the timeout is not resent; PX4 sees NaN instead."""
    pytest.importorskip("px4_msgs", reason="px4_msgs not built into the workspace")

    from nectar.control.px4.vision_bridge import Px4VisionOdometryBridge

    bridge = Px4VisionOdometryBridge(
        node=ros_node,
        input_topic="/nectar_test/vo_pose_cov",
        speed_topic="/nectar_test/vo_odometry",
        speed_timeout_s=0.05,
    )
    bridge._on_odometry(_odometry_msg((1.0, 0.0, 0.0), _yaw_quaternion(0.0)))
    assert bridge._fresh_velocity() is not None

    time.sleep(0.1)
    assert bridge._fresh_velocity() is None


def test_pose_variance_diagonal_enu_to_ned_matches_full_cov():
    """DDS variance vectors match the diagonal of the full ENU→NED covariance."""
    from nectar.control.localization.frames import (
        pose_covariance_enu_to_ned,
        pose_variance_diagonal_enu_to_ned,
    )

    cov = [0.0] * 36
    cov[0] = 0.01  # ENU x
    cov[7] = 0.02  # ENU y
    cov[14] = 0.03  # ENU z
    cov[21] = 0.04  # ENU roll
    cov[28] = 0.05  # ENU pitch
    cov[35] = 0.06  # ENU yaw

    pos, ori = pose_variance_diagonal_enu_to_ned(cov)
    ned = pose_covariance_enu_to_ned(cov)
    assert pos == pytest.approx((ned[0], ned[7], ned[14]))
    assert ori == pytest.approx((ned[21], ned[28], ned[35]))
    # ENU (x,y,z) -> NED (y,x,z): variances (0.02, 0.01, 0.03)
    assert pos == pytest.approx((0.02, 0.01, 0.03))
    # ENU (roll,pitch,yaw) -> NED (roll,-pitch,yaw_ned): (0.05, 0.04, 0.06)
    assert ori == pytest.approx((0.05, 0.04, 0.06))


def test_gz_vision_source_body_twist_from_world_delta():
    """Finite-diff world Δp/Δt rotated into body FLU (cuVSLAM PoseCache convention)."""
    from nectar.control.localization.frames import rotate_by_quaternion

    # Move 1 m along ENU +y over 1 s while facing East (identity quat) → body +y.
    world = (0.0, 1.0, 0.0)
    qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
    vx, vy, vz = rotate_by_quaternion(world, (-qx, -qy, -qz, qw))
    assert [round(v, 6) for v in (vx, vy, vz)] == [0.0, 1.0, 0.0]

    # Same world motion while yawed 90 deg CCW (facing North): body +x.
    yaw = math.pi / 2.0
    q = _yaw_quaternion(yaw)
    vx, vy, vz = rotate_by_quaternion(world, (-q[0], -q[1], -q[2], q[3]))
    assert [round(v, 6) for v in (vx, vy, vz)] == [1.0, 0.0, 0.0]
