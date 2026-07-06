"""Vision functional tests.

Algorithms are exercised on synthetic inputs (a rendered ArUco marker, a
solid-color patch, a drawn line) so they need no camera. The ROS-topic camera
path is exercised end to end by publishing an image and reading it back through
``CameraFactory``. Physical USB/RealSense/OAK-D drivers live in ``test/hardware``.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

pytestmark = pytest.mark.vision


def test_aruco_synthetic():
    """A rendered ArUco marker is detected with the correct id and a pose is returned."""
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
        pytest.skip(f"camera calibration files unavailable: {exc}")

    detected_id, _translation, _yaw = detector.pose_estimate(img)
    assert detected_id is not None, "marker rendered but not detected"
    assert int(detected_id) == marker_id, f"wrong id: expected {marker_id}, got {detected_id}"


def test_color_filter():
    """An HSV in-range patch is masked by the color detector."""
    import cv2

    from nectar.vision import ColorDetector

    detector = ColorDetector(mode="preset", color="yellow")
    detector.color_values = [[0, 120, 70], [10, 255, 255]]  # a red HSV band

    hsv = np.full((120, 160, 3), (5, 200, 200), dtype=np.uint8)  # H=5 inside band
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    detector.filterColor(bgr)

    assert detector.mask is not None, "filterColor produced no mask"
    hit = int((detector.mask > 0).sum())
    assert hit >= 0.5 * detector.mask.size, f"mask covered only {hit}/{detector.mask.size} px"


def test_line_detection():
    """A drawn line is recovered with a finite center and angle."""
    import cv2

    from nectar.vision import HoughLinesP, LineDetector

    mask = np.zeros((480, 640), dtype=np.uint8)
    cv2.line(mask, (100, 60), (540, 420), 255, 6)

    detector = LineDetector(color=None, estimation_method=HoughLinesP)
    detector.external_mask = mask
    img = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

    out = detector.detect_line(img, draw=False)
    center_x, center_y, angle = out[2], out[3], out[4]
    finite = [
        v is not None and not (isinstance(v, float) and np.isnan(v))
        for v in (center_x, center_y, angle)
    ]
    assert all(finite), f"no line estimated (cx={center_x}, cy={center_y}, angle={angle})"


def test_distance_estimator():
    """The polynomial distance model returns distinct finite estimates across inputs."""
    from nectar.vision import DistanceEstimator

    est = DistanceEstimator(model_type="polynomial")
    near = est.estimate(60.0)
    far = est.estimate(200.0)
    assert np.isfinite(near) and np.isfinite(far), f"non-finite estimate: {near}, {far}"
    assert abs(near - far) >= 1e-6, "model is constant across inputs"


def test_ros_topic_camera(ros_node):
    """CameraFactory delivers a frame published on a ROS image topic."""
    from cv_bridge import CvBridge
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image as RosImage

    from nectar.vision import CameraFactory

    bridge = CvBridge()
    frame = (np.random.rand(48, 64, 3) * 255).astype(np.uint8)
    msg = bridge.cv2_to_imgmsg(frame, encoding="bgr8")
    pub = ros_node.create_publisher(RosImage, "/nectar_test/cam", qos_profile_sensor_data)

    cam = CameraFactory.from_source("/nectar_test/cam")
    cam.start()

    got = None
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        pub.publish(msg)
        got = cam.get_frame(wait_for_new=True, timeout=0.25)
        if got is not None:
            break
    cam.close()

    assert got is not None, "no frame received through CameraFactory ROS topic"
    assert got.shape == frame.shape, f"frame shape {got.shape} != published {frame.shape}"
