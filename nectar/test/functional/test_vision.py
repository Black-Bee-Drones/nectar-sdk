"""Vision functional tests."""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

pytestmark = pytest.mark.vision


def test_color_filter(tmp_path):
    """An HSV in-range patch is masked by the color detector."""
    import cv2

    from nectar.vision import ColorDetector

    calib = tmp_path / "colors.json"
    calib.write_text(
        json.dumps({"yellow": {"HSV": [[0, 120, 70], [10, 255, 255]]}}),
        encoding="utf-8",
    )
    detector = ColorDetector(mode="preset", color="yellow", file_path=calib)

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


def test_image_handler_callback_return(ros_node, tmp_path):
    """A callback ndarray return replaces the frame stored on the handler."""
    import cv2

    from nectar.vision.camera import ImageHandler

    raw = np.full((24, 32, 3), (10, 20, 30), dtype=np.uint8)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), raw)

    def on_frame(frame):
        out = frame.copy()
        out[:] = (1, 2, 3)
        return out

    handler = ImageHandler(str(path), image_processing_callback=on_frame)
    handler.run()
    deadline = time.monotonic() + 5.0
    img = None
    try:
        while time.monotonic() < deadline:
            img = handler.img
            if img is not None and int(img[0, 0, 0]) == 1:
                break
            time.sleep(0.05)
        assert img is not None, "handler never stored a frame"
        assert int(img[0, 0, 0]) == 1, f"stored frame was not the callback return: {img[0, 0]}"
    finally:
        handler.cleanup()


def test_image_handler_file_does_not_spin(ros_node, tmp_path):
    """A static file source must not busy-loop the processing callback."""
    import cv2

    from nectar.vision.camera import ImageHandler

    path = tmp_path / "still.png"
    cv2.imwrite(str(path), np.zeros((16, 16, 3), dtype=np.uint8))
    seen = []

    def on_frame(_frame):
        seen.append(1)

    handler = ImageHandler(str(path), image_processing_callback=on_frame)
    handler.run()
    try:
        time.sleep(0.1)
        assert len(seen) >= 1, "handler never invoked the callback"
        assert len(seen) <= 5, f"file source busy-looped: {len(seen)} callbacks in 0.1s"
    finally:
        handler.cleanup()


def test_image_handler_ros_topic_not_stale(ros_node):
    """ImageHandler on a ROS topic delivers successive distinct frames."""
    from cv_bridge import CvBridge
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image as RosImage

    from nectar.vision.camera import ImageHandler

    bridge = CvBridge()
    topic = "/nectar_test/handler_cam"
    pub = ros_node.create_publisher(RosImage, topic, qos_profile_sensor_data)
    seen = []

    def on_frame(frame):
        seen.append(int(frame[0, 0, 0]))

    handler = ImageHandler(topic, image_processing_callback=on_frame)
    handler.run()
    try:
        deadline = time.monotonic() + 8.0
        value = 10
        while time.monotonic() < deadline and not {10, 200}.issubset(set(seen)):
            frame = np.full((24, 32, 3), value, dtype=np.uint8)
            pub.publish(bridge.cv2_to_imgmsg(frame, encoding="bgr8"))
            if 10 in seen:
                value = 200
            time.sleep(0.05)
        assert 10 in seen and 200 in seen, f"expected two distinct frames, got {set(seen)}"
    finally:
        handler.cleanup()


def test_two_handlers_register_display(ros_node, tmp_path):
    """Two show_result handlers register with the class-level GUI pump."""
    import cv2

    from nectar.vision.camera.handler import ImageHandler

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    cv2.imwrite(str(a), np.zeros((8, 8, 3), dtype=np.uint8))
    cv2.imwrite(str(b), np.full((8, 8, 3), 255, dtype=np.uint8))

    ImageHandler._displays.clear()
    h1 = ImageHandler(str(a), show_result="A")
    h2 = ImageHandler(str(b), show_result="B")
    h1.run()
    h2.run()
    try:
        assert h1 in ImageHandler._displays
        assert h2 in ImageHandler._displays
        assert len(ImageHandler._displays) == 2
    finally:
        h1.cleanup()
        h2.cleanup()
        assert ImageHandler._displays == []


def test_camera_cli():
    """Omitted flags keep per-driver dataclass defaults; passed flags override."""
    import argparse

    from nectar.vision.camera.cli import add_camera_arguments, parse_camera_args
    from nectar.vision.camera.config import (
        IMX219Config,
        OakDConfig,
        OpenCVConfig,
        RealSenseConfig,
        ROSConfig,
        T265Config,
    )
    from nectar.vision.camera.config_builder import ConfigBuilder
    from nectar.vision.nodes.aruco_node import _parser as aruco_parser

    def _cfg(argv):
        parser = argparse.ArgumentParser()
        add_camera_arguments(parser)
        return parse_camera_args(parser, argv)

    source, cfg = _cfg(["--source", "webcam", "--device-index", "2"])[2:]
    assert source == "webcam"
    assert isinstance(cfg, OpenCVConfig)
    assert cfg.device_index == 2
    assert cfg.width is None

    _, _, source, cfg = _cfg(["--source", "imx219"])
    assert source == "imx219" and isinstance(cfg, IMX219Config) and cfg.width == 1920
    assert _cfg(["--source", "imx219", "--width", "1280"])[3].width == 1280

    oakd = _cfg(["--source", "oakd"])[3]
    assert isinstance(oakd, OakDConfig) and oakd.enable_depth is False
    assert _cfg(["--source", "oakd", "--enable-depth"])[3].enable_depth is True

    rs = _cfg(["--source", "realsense"])[3]
    assert isinstance(rs, RealSenseConfig) and rs.enable_depth is True
    rs = _cfg(["--source", "realsense", "--no-enable-depth"])[3]
    assert rs.enable_depth is False
    rs = _cfg(["--source", "realsense", "--color-width", "1280", "--color-height", "720"])[3]
    assert rs.color_res == (1280, 720) and rs.depth_res == (640, 480)

    t265 = _cfg(["--source", "t265", "--use-ros-topics"])[3]
    assert isinstance(t265, T265Config) and t265.use_ros_topics is True

    source, cfg = _cfg(["--source", "/camera/image_raw/compressed"])[2:]
    assert isinstance(cfg, ROSConfig) and cfg.topic == source and cfg.compressed is True

    _, rest, source, _ = _cfg(["--source", "webcam", "--ros-args", "-p", "foo:=1"])
    assert source == "webcam" and "--ros-args" in rest

    built = ConfigBuilder.build("webcam", {"device_index": 3, "show": True, "marker_dict": 5})
    assert isinstance(built, OpenCVConfig) and built.device_index == 3

    args, rest, source, cfg = parse_camera_args(
        aruco_parser(),
        ["--source", "webcam", "--device-index", "1", "--no-show", "--marker-dict", "4"],
    )
    assert isinstance(cfg, OpenCVConfig) and cfg.device_index == 1
    assert args.show is False and args.marker_dict == 4 and rest == []


def test_camera_factory():
    """Registry, lazy construct, type checks, and register() isolation."""
    import sys

    from nectar.vision.camera.config import CameraConfig, OakDConfig, OpenCVConfig, ROSConfig
    from nectar.vision.camera.drivers.opencv_cam import OpenCVCam
    from nectar.vision.camera.factory import CameraFactory

    keys = CameraFactory.registered_keys()
    assert keys[:2] == ["webcam", "opencv"]
    assert CameraFactory.is_registered("OPENCV")
    assert not CameraFactory.is_registered("not_a_camera")
    assert CameraFactory.config_class("webcam") is OpenCVConfig
    assert CameraFactory.config_class("opencv") is OpenCVConfig
    assert CameraFactory.config_class("ros") is ROSConfig
    assert CameraFactory.config_class("oakd") is OakDConfig
    assert CameraFactory.config_class("missing") is None

    before = set(sys.modules)
    cam = CameraFactory.from_source("webcam")
    added = set(sys.modules) - before
    assert isinstance(cam, OpenCVCam) and cam.is_running is False
    assert not any(name.endswith((".realsense_cam", ".oakd_cam", ".t265_cam")) for name in added)

    with pytest.raises(ValueError, match="OpenCVConfig"):
        CameraFactory.from_source("webcam", config=ROSConfig())
    with pytest.raises(ValueError, match="ROSConfig"):
        CameraFactory.from_source("/image_raw", config=OpenCVConfig())
    with pytest.raises(ValueError, match="Unknown camera source"):
        CameraFactory.from_source("not_a_camera")

    class _DummyCam:
        def __init__(self, config):
            self.config = config

    keys_before = CameraFactory.registered_keys()
    CameraFactory.register("dummy_factory_cam", _DummyCam, config_cls=OpenCVConfig)
    try:
        assert CameraFactory.registered_keys() == [*keys_before, "dummy_factory_cam"]
        assert CameraFactory.config_class("dummy_factory_cam") is OpenCVConfig
        dummy = CameraFactory.from_source("dummy_factory_cam")
        assert isinstance(dummy, _DummyCam)
        assert isinstance(dummy.config, CameraConfig)
        assert dummy.config.name == "dummy_factory_cam"
    finally:
        CameraFactory._builders.pop("dummy_factory_cam", None)
        CameraFactory._config_classes.pop("dummy_factory_cam", None)
