"""Vision functional checks.

Algorithms are exercised on synthetic inputs (a rendered ArUco marker, a
solid-color patch, a drawn line) so they need no camera. The ROS-topic camera
path is exercised end to end by publishing an image and reading it back through
``CameraFactory``. USB/RealSense/OAK-D drivers need a physical device, so they
self-skip when none is attached.
"""

from __future__ import annotations

import numpy as np

from nectar.diagnostics import helpers
from nectar.diagnostics.runner import Check, Fail, ModuleSpec, Skip


def _aruco_synthetic() -> str:
    import cv2

    from nectar.vision import Aruco

    dict_size = 5
    marker_id = 23
    aruco_dict = cv2.aruco.getPredefinedDictionary(
        getattr(cv2.aruco, f"DICT_{dict_size}X{dict_size}_1000")
    )
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 300)
    padded = cv2.copyMakeBorder(marker, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=255)
    img = cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)

    try:
        detector = Aruco(marker_dict=dict_size, tag_size=0.20)
    except FileNotFoundError as exc:
        raise Skip(f"camera calibration files unavailable: {exc}")

    detected_id, translation, _yaw = detector.pose_estimate(img)
    if detected_id is None:
        raise Fail("marker rendered but not detected")
    if int(detected_id) != marker_id:
        raise Fail(f"wrong id: expected {marker_id}, got {detected_id}")
    return (
        f"detected id={marker_id}, pose returned ({'ok' if translation is not None else 'no-pose'})"
    )


def _color_filter() -> str:
    import cv2

    from nectar.vision import ColorDetector

    detector = ColorDetector(mode="preset", color="yellow")
    detector.color_values = [[0, 120, 70], [10, 255, 255]]  # a red HSV band

    hsv = np.full((120, 160, 3), (5, 200, 200), dtype=np.uint8)  # H=5 inside band
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    detector.filterColor(bgr)

    if detector.mask is None:
        raise Fail("filterColor produced no mask")
    hit = int((detector.mask > 0).sum())
    if hit < 0.5 * detector.mask.size:
        raise Fail(f"mask covered only {hit}/{detector.mask.size} px of a matching patch")
    return f"HSV in-range mask {hit}/{detector.mask.size} px"


def _line_detection() -> str:
    import cv2

    from nectar.vision import HoughLinesP, LineDetector

    mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.line(mask, (100, 60), (540, 420), 255, 6)

    detector = LineDetector(color=None, estimation_method=HoughLinesP)
    detector.external_mask = mask
    img = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    out = detector.detect_line(img, draw=False)
    center_x, center_y, angle = out[2], out[3], out[4]
    if any(
        v is None or (isinstance(v, float) and np.isnan(v)) for v in (center_x, center_y, angle)
    ):
        raise Fail(f"no line estimated (cx={center_x}, cy={center_y}, angle={angle})")
    return f"line estimated: center=({center_x:.0f},{center_y:.0f}), angle={angle:.1f} deg"


def _distance_estimator() -> str:
    from nectar.vision import DistanceEstimator

    est = DistanceEstimator(model_type="polynomial")
    near = est.estimate(60.0)
    far = est.estimate(200.0)
    for label, val in (("60px", near), ("200px", far)):
        if not np.isfinite(val):
            raise Fail(f"non-finite estimate at {label}: {val}")
    if abs(near - far) < 1e-6:
        raise Fail("model is constant across inputs")
    return f"polynomial model: 60px->{near:.1f}, 200px->{far:.1f}"


def _ros_topic_camera() -> str:
    from cv_bridge import CvBridge
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image as RosImage

    from nectar.vision import CameraFactory

    helpers.ensure_ros()
    pub_node = helpers.make_node("diag_cam_pub")
    bridge = CvBridge()
    frame = (np.random.rand(48, 64, 3) * 255).astype(np.uint8)
    msg = bridge.cv2_to_imgmsg(frame, encoding="bgr8")
    pub = pub_node.create_publisher(RosImage, "/nectar_diag/cam", qos_profile_sensor_data)

    cam = CameraFactory.from_source("/nectar_diag/cam")
    cam.start()

    import time

    got = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        got = cam.get_frame(wait_for_new=True, timeout=0.25)
        if got is not None:
            break

    cam.close()
    pub_node.destroy_publisher(pub)

    if got is None:
        raise Fail("no frame received through CameraFactory ROS topic")
    if got.shape != frame.shape:
        raise Fail(f"frame shape {got.shape} != published {frame.shape}")
    return f"ROS-topic camera delivered a {got.shape[1]}x{got.shape[0]} frame"


def _oakd_device() -> str:
    try:
        import depthai
    except ImportError:
        raise Skip("depthai not installed (make python-full / oakd extra)")
    try:
        devices = depthai.Device.getAllAvailableDevices()
    except Exception as exc:  # noqa: BLE001
        raise Skip(f"depthai present, device query failed: {exc}")
    if not devices:
        raise Skip("depthai installed, no OAK-D device attached")
    return f"OAK-D device(s) enumerated: {len(devices)}"


def _realsense_device() -> str:
    try:
        import pyrealsense2 as rs
    except ImportError:
        raise Skip("pyrealsense2 not installed (realsense extra)")
    try:
        ctx = rs.context()
        n = len(ctx.query_devices())
    except Exception as exc:  # noqa: BLE001
        raise Skip(f"pyrealsense2 present, device query failed: {exc}")
    if n == 0:
        raise Skip("pyrealsense2 installed, no RealSense device attached")
    return f"RealSense device(s) enumerated: {n}"


MODULE = ModuleSpec(
    key="vision",
    title="Vision",
    install="make python-vision",
    checks=[
        Check("ArUco synthetic marker", _aruco_synthetic),
        Check("color HSV filter", _color_filter),
        Check("line detection (Hough)", _line_detection),
        Check("distance estimator", _distance_estimator),
        Check("ROS-topic camera (CameraFactory)", _ros_topic_camera),
        Check("OAK-D device", _oakd_device),
        Check("RealSense device", _realsense_device),
    ],
)
