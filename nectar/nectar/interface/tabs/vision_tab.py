from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    pass
import json
import os
import time

import cv2
import numpy as np
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from rclpy.node import Node

from nectar.interface.theme import COLORS
from nectar.interface.widgets import (
    CameraConfigPanel,
    CollapsibleSection,
    DetectionConfigPanel,
    DualVideoDisplay,
    LabeledSlider,
)


class ColorCalibrationManager:
    """
    Manager for color calibration presets and sampling.

    Handles loading, saving, and computing color thresholds from
    sampled pixels. Supports both HSV and LAB color spaces.

    Parameters
    ----------
    calibration_path : str, optional
        Path to calibration JSON file.

    Attributes
    ----------
    lower : np.ndarray
        Lower color threshold [val1, val2, val3].
    upper : np.ndarray
        Upper color threshold [val1, val2, val3].
    color_space : str
        Current color space ("HSV" or "LAB").
    """

    DEFAULT_RANGES = {
        "HSV": {"lower": [0, 0, 0], "upper": [179, 255, 255]},
        "LAB": {"lower": [0, 0, 0], "upper": [255, 255, 255]},
    }

    MARGINS = {
        "HSV": [5, 15, 15],
        "LAB": [10, 10, 10],
    }

    def __init__(self, calibration_path: Optional[str] = None) -> None:
        if calibration_path is None:
            base_path = os.path.dirname(os.path.realpath(__file__))
            self._calibration_path = os.path.join(
                base_path,
                "..",
                "..",
                "vision",
                "algorithms",
                "color",
                "color_calibration.json",
            )
        else:
            self._calibration_path = calibration_path

        self._color_space = "HSV"
        self._sampled_pixels: List[np.ndarray] = []
        self._lower = np.array(self.DEFAULT_RANGES["HSV"]["lower"], dtype=np.uint8)
        self._upper = np.array(self.DEFAULT_RANGES["HSV"]["upper"], dtype=np.uint8)
        self._flood_tolerance = 15

    @property
    def lower(self) -> np.ndarray:
        return self._lower

    @lower.setter
    def lower(self, value: List[int]) -> None:
        self._lower = np.array(value, dtype=np.uint8)

    @property
    def upper(self) -> np.ndarray:
        return self._upper

    @upper.setter
    def upper(self, value: List[int]) -> None:
        self._upper = np.array(value, dtype=np.uint8)

    @property
    def color_space(self) -> str:
        return self._color_space

    @color_space.setter
    def color_space(self, value: str) -> None:
        if value in ("HSV", "LAB"):
            self._color_space = value
            self._sampled_pixels.clear()
            self._lower = np.array(self.DEFAULT_RANGES[value]["lower"], dtype=np.uint8)
            self._upper = np.array(self.DEFAULT_RANGES[value]["upper"], dtype=np.uint8)

    @property
    def flood_tolerance(self) -> int:
        return self._flood_tolerance

    @flood_tolerance.setter
    def flood_tolerance(self, value: int) -> None:
        self._flood_tolerance = max(1, min(50, value))

    @property
    def sample_count(self) -> int:
        return len(self._sampled_pixels)

    def reset(self) -> None:
        self._sampled_pixels.clear()
        self._lower = np.array(self.DEFAULT_RANGES[self._color_space]["lower"], dtype=np.uint8)
        self._upper = np.array(self.DEFAULT_RANGES[self._color_space]["upper"], dtype=np.uint8)

    def undo_sample(self) -> bool:
        if self._sampled_pixels:
            self._sampled_pixels.pop()
            if self._sampled_pixels:
                self._compute_bounds()
            else:
                self.reset()
            return True
        return False

    def sample_at_point(self, frame: np.ndarray, x: int, y: int) -> Tuple[bool, np.ndarray]:
        h, w = frame.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return False, np.array([])

        if self._color_space == "HSV":
            converted = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        else:
            converted = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

        mask = np.zeros((h + 2, w + 2), np.uint8)
        tol = self._flood_tolerance

        cv2.floodFill(
            converted.copy(),
            mask,
            (x, y),
            255,
            (tol, tol, tol),
            (tol, tol, tol),
            cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE,
        )

        region_mask = mask[1:-1, 1:-1]
        pixels = converted[region_mask == 1]

        if len(pixels) < 10:
            return False, np.array([])

        self._sampled_pixels.append(pixels)
        self._compute_bounds()
        return True, pixels

    def _compute_bounds(self) -> None:
        if not self._sampled_pixels:
            return

        all_pixels = np.vstack(self._sampled_pixels)
        margins = self.MARGINS[self._color_space]
        maxes = self.DEFAULT_RANGES[self._color_space]["upper"]

        lower, upper = [], []
        for ch in range(3):
            ch_data = all_pixels[:, ch]
            lo = max(0, int(np.percentile(ch_data, 2)) - margins[ch])
            hi = min(maxes[ch], int(np.percentile(ch_data, 98)) + margins[ch])
            lower.append(lo)
            upper.append(hi)

        self._lower = np.array(lower, dtype=np.uint8)
        self._upper = np.array(upper, dtype=np.uint8)

    def apply_filter(self, frame: np.ndarray, return_mask: bool = False) -> np.ndarray:
        if self._color_space == "HSV":
            converted = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        else:
            converted = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

        mask = cv2.inRange(converted, self._lower, self._upper)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        if return_mask:
            return mask

        return cv2.bitwise_and(frame, frame, mask=mask)

    def get_available_presets(self) -> Dict[str, List[str]]:
        if not os.path.exists(self._calibration_path):
            return {}

        try:
            with open(self._calibration_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {name: list(spaces.keys()) for name, spaces in data.items()}
        except (json.JSONDecodeError, IOError):
            return {}

    def load_preset(self, name: str, color_space: Optional[str] = None) -> bool:
        if color_space is None:
            color_space = self._color_space

        if not os.path.exists(self._calibration_path):
            return False

        try:
            with open(self._calibration_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if name not in data or color_space not in data[name]:
                return False

            values = data[name][color_space]
            self._lower = np.array(values[0], dtype=np.uint8)
            self._upper = np.array(values[1], dtype=np.uint8)
            self._color_space = color_space
            self._sampled_pixels.clear()
            return True

        except (json.JSONDecodeError, IOError):
            return False

    def save_preset(self, name: str) -> bool:
        data = {}
        if os.path.exists(self._calibration_path):
            try:
                with open(self._calibration_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        if name not in data:
            data[name] = {}

        data[name][self._color_space] = [
            self._lower.tolist(),
            self._upper.tolist(),
        ]

        try:
            os.makedirs(os.path.dirname(self._calibration_path), exist_ok=True)
            with open(self._calibration_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except IOError:
            return False


class CameraInitWorker(QObject):
    """
    Background worker for camera initialization.

    Handles camera creation and startup in a separate thread to prevent
    UI blocking during potentially slow hardware initialization.

    Parameters
    ----------
    config : dict
        Camera configuration from CameraConfigPanel.get_config().
    enable_depth : bool
        Whether to enable depth capture for depth-capable cameras.
    node : Node, optional
        ROS2 node for ROS-based cameras.
    """

    finished = Signal(bool, str)
    camera_ready = Signal(object)

    def __init__(self, config: Dict[str, Any], enable_depth: bool = False, node=None) -> None:
        super().__init__()
        self._config = config
        self._enable_depth = enable_depth
        self._node = node
        self._camera = None

    @property
    def camera(self):
        return self._camera

    def run(self) -> None:
        try:
            camera_type = self._config.get("type", "webcam")
            self._camera = self._create_camera(camera_type)
            self._camera.start()
            self.camera_ready.emit(self._camera)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _create_camera(self, camera_type: str):
        """Create camera instance based on type and configuration."""
        if camera_type == "webcam":
            from nectar.vision.camera import OpenCVCam, OpenCVConfig

            config = OpenCVConfig(
                device_index=self._config.get("device_index", 0),
                width=self._config.get("width"),
                height=self._config.get("height"),
                fps=self._config.get("fps", 30),
                autofocus=self._config.get("autofocus", True),
                threaded=self._config.get("threaded", True),
            )
            return OpenCVCam(config)

        elif camera_type == "realsense":
            use_ros = self._config.get("use_ros_topics", False)

            if use_ros:
                from nectar.vision.camera import QoSReliability, ROSDepthCam, ROSDepthConfig

                color_topic = self._config.get("color_topic", "/camera/color/image_raw")
                color_compressed = self._config.get("color_compressed", True)
                if color_compressed and not color_topic.endswith("/compressed"):
                    color_topic = color_topic + "/compressed"

                depth_topic = self._config.get("depth_topic", "/camera/depth/image_rect_raw")
                depth_compressed = self._config.get("depth_compressed", False)
                if depth_compressed and not depth_topic.endswith("/compressedDepth"):
                    depth_topic = depth_topic + "/compressedDepth"

                config = ROSDepthConfig(
                    topic=color_topic,
                    compressed=color_compressed,
                    depth_topic=depth_topic,
                    depth_compressed=depth_compressed,
                    enable_depth=self._enable_depth,
                    reliability=QoSReliability.BEST_EFFORT,
                )
                if self._node is None:
                    raise ValueError("ROS depth camera requires a ROS node")
                return ROSDepthCam(self._node, config)
            else:
                from nectar.vision.camera import RealsenseCam, RealSenseConfig

                width = self._config.get("width", 640)
                height = self._config.get("height", 480)

                config = RealSenseConfig(
                    color_res=(width, height),
                    depth_res=(width, height),
                    fps=self._config.get("fps", 30),
                    align_to_color=self._config.get("align_to_color", True),
                    enable_depth=self._enable_depth,
                )
                return RealsenseCam(config)

        elif camera_type == "oakd":
            from nectar.vision.camera import OakdCam, OakDConfig

            config = OakDConfig(
                cam_num=self._config.get("cam_num", 1),
                enable_depth=self._enable_depth,
            )
            return OakdCam(config)

        elif camera_type == "ros":
            from nectar.vision.camera import QoSDurability, QoSReliability, ROSCam, ROSConfig

            reliability_str = self._config.get("reliability", "Best Effort")
            if reliability_str == "Reliable":
                reliability = QoSReliability.RELIABLE
            else:
                reliability = QoSReliability.BEST_EFFORT

            durability_str = self._config.get("durability", "Volatile")
            if durability_str == "Transient Local":
                durability = QoSDurability.TRANSIENT_LOCAL
            else:
                durability = QoSDurability.VOLATILE

            config = ROSConfig(
                topic=self._config.get("topic", "/camera/image_raw"),
                compressed=self._config.get("compressed", False),
                reliability=reliability,
                durability=durability,
                history_depth=self._config.get("history_depth", 1),
                encoding=self._config.get("encoding", "bgr8"),
            )
            if self._node is None:
                raise ValueError("ROS camera requires a ROS node")
            return ROSCam(self._node, config)

        elif camera_type == "ros_depth":
            from nectar.vision.camera import QoSReliability, ROSDepthCam, ROSDepthConfig

            reliability_str = self._config.get("reliability", "Best Effort")
            if reliability_str == "Reliable":
                reliability = QoSReliability.RELIABLE
            else:
                reliability = QoSReliability.BEST_EFFORT

            color_topic = self._config.get("topic", "/front_camera/image")
            color_compressed = self._config.get("compressed", False)
            if color_compressed and not color_topic.endswith("/compressed"):
                color_topic = color_topic + "/compressed"

            depth_topic = self._config.get("depth_topic", "/front_camera/depth_image")
            depth_compressed = self._config.get("depth_compressed", False)
            if depth_compressed and not depth_topic.endswith("/compressedDepth"):
                depth_topic = depth_topic + "/compressedDepth"

            config = ROSDepthConfig(
                topic=color_topic,
                compressed=color_compressed,
                depth_topic=depth_topic,
                depth_compressed=depth_compressed,
                enable_depth=True,
                reliability=reliability,
            )
            if self._node is None:
                raise ValueError("ROS depth camera requires a ROS node")
            return ROSDepthCam(self._node, config)

        elif camera_type == "file":
            from nectar.vision.camera import FileImageCam, FileImageConfig

            config = FileImageConfig(path=self._config.get("path", ""))
            return FileImageCam(config)

        elif camera_type == "c920":
            from nectar.vision.camera import C920Cam, C920Config

            config = C920Config(
                profile=self._config.get("profile", 1),
                fallback_device_index=self._config.get("fallback_device_index", 0),
            )
            return C920Cam(config)

        elif camera_type == "imx219":
            from nectar.vision.camera import IMX219Cam, IMX219Config

            config = IMX219Config(
                sensor_id=self._config.get("sensor_id", 0),
                width=self._config.get("width", 1920),
                height=self._config.get("height", 1080),
                fps=self._config.get("fps", 30),
                flip=self._config.get("flip", 0),
            )
            return IMX219Cam(config)

        else:
            from nectar.vision.camera import CameraFactory

            return CameraFactory.from_source(camera_type)


class VisionTab(QWidget):
    """
    Vision processing tab with camera controls and filters.

    Provides comprehensive color calibration, line detection,
    and various OpenCV/AI processing tools.

    Parameters
    ----------
    node : Node, optional
        ROS2 node for ROS camera sources.
    parent : QWidget, optional
        Parent widget.
    """

    ESTIMATION_METHODS = [
        "HoughLinesP",
        "RotatedRect",
        "FitEllipse",
        "RansacLine",
        "AdaptiveHoughLinesP",
    ]

    def __init__(self, node: Optional[Node] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._node = node
        self._camera = None
        self._cv_utils = None
        self._line_detector = None
        self._prev_gray = None
        self._current_frame: Optional[np.ndarray] = None

        self._camera_thread: Optional[QThread] = None
        self._camera_worker: Optional[CameraInitWorker] = None

        self._active_filters: List[Callable] = []
        self._filter_params: Dict[str, Any] = {}

        self._fps_counter = 0
        self._fps = 0.0
        self._fps_start = time.time()

        self._color_manager = ColorCalibrationManager()

        # AI Detection state
        self._ai_detector = None
        self._detection_enabled = False
        self._last_detection_result = None

        # Depth estimation state
        self._depth_enabled = False
        self._show_depth_map = False
        self._measure_distance = False
        self._selected_point: Optional[Tuple[int, int]] = None
        self._current_distance: Optional[float] = None
        self._current_depth_frame: Optional[np.ndarray] = None
        self._depth_colormap = cv2.COLORMAP_PLASMA
        self._depth_min_m = 0.1
        self._depth_max_m = 5.0

        self._setup_ui()
        self._setup_timers()
        self._init_cv_utils()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_control_panel()
        right_panel = self._create_video_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([380, 720])

        layout.addWidget(splitter)

    def _create_control_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(440)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(6)

        layout.addWidget(self._create_camera_selector())
        layout.addWidget(self._create_depth_estimation_section())
        layout.addWidget(self._create_color_calibration_section())
        layout.addWidget(self._create_line_detection_section())
        layout.addWidget(self._create_edge_detection_section())
        layout.addWidget(self._create_blur_section())
        layout.addWidget(self._create_transform_section())
        layout.addWidget(self._create_morphology_section())
        layout.addWidget(self._create_effects_section())
        layout.addWidget(self._create_detection_section())
        layout.addWidget(self._create_aruco_section())
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _create_video_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Live Preview")
        header.setStyleSheet(
            f"""
            font-size: 13px;
            font-weight: 600;
            color: {COLORS.accent};
            padding: 4px 0;
        """
        )
        header.setAlignment(Qt.AlignCenter)

        # Use DualVideoDisplay for RGB + Depth side-by-side
        self._video_display = DualVideoDisplay()
        self._video_display.set_placeholder("Select a camera source to start")
        self._video_display.rgb_clicked.connect(self._on_video_clicked)
        self._video_display.depth_clicked.connect(self._on_depth_clicked)

        self._info_label = QLabel("FPS: -- | Resolution: --")
        self._info_label.setProperty("secondary", True)
        self._info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(header)
        layout.addWidget(self._video_display, 1)
        layout.addWidget(self._info_label)

        return container

    def _create_camera_selector(self) -> QGroupBox:
        group = QGroupBox("Camera Source")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Dynamic camera configuration panel
        self._camera_config = CameraConfigPanel()
        layout.addWidget(self._camera_config)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self._start_btn = QPushButton("Start")
        self._start_btn.setProperty("accent", True)
        self._start_btn.clicked.connect(self._start_camera)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._stop_camera)
        self._stop_btn.setEnabled(False)

        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)
        layout.addLayout(btn_layout)

        return group

    def _create_depth_estimation_section(self) -> CollapsibleSection:
        """Create depth estimation controls for RealSense/OAK-D cameras."""
        section = CollapsibleSection("Depth Estimation")

        # Enable depth checkbox
        self._depth_enable_cb = QCheckBox("Enable Depth Mode")
        self._depth_enable_cb.setToolTip(
            "Enable depth capture (RealSense/OAK-D only). Requires camera restart."
        )
        self._depth_enable_cb.stateChanged.connect(self._on_depth_enabled_changed)

        # Info label about depth
        depth_info = QLabel("Supports: RealSense, OAK-D")
        depth_info.setProperty("muted", True)

        # Show depth map checkbox
        self._show_depth_map_cb = QCheckBox("Show Depth Map (side-by-side)")
        self._show_depth_map_cb.setToolTip(
            "Display colorized depth alongside RGB in side-by-side view"
        )
        self._show_depth_map_cb.setEnabled(False)
        self._show_depth_map_cb.stateChanged.connect(self._on_show_depth_changed)

        # Measure distance checkbox
        self._measure_distance_cb = QCheckBox("Click to Measure Distance")
        self._measure_distance_cb.setToolTip("Click on image to measure distance at point")
        self._measure_distance_cb.setEnabled(False)
        self._measure_distance_cb.stateChanged.connect(self._on_measure_distance_changed)

        # Distance display
        self._distance_label = QLabel("Distance: -- m")
        self._distance_label.setStyleSheet(
            f"color: {COLORS.accent}; font-weight: 600; font-size: 13px; padding: 4px;"
        )
        self._distance_label.setAlignment(Qt.AlignCenter)

        # Point coordinates display
        self._point_label = QLabel("Point: (-, -)")
        self._point_label.setProperty("muted", True)
        self._point_label.setAlignment(Qt.AlignCenter)

        # Colormap selector
        colormap_layout = QHBoxLayout()
        colormap_layout.setSpacing(6)
        cmap_lbl = QLabel("Colormap:")
        cmap_lbl.setProperty("secondary", True)
        self._colormap_combo = QComboBox()
        self._colormap_combo.addItems(
            ["PLASMA", "JET", "VIRIDIS", "INFERNO", "MAGMA", "TURBO", "HOT", "BONE"]
        )
        self._colormap_combo.currentTextChanged.connect(self._on_colormap_changed)
        colormap_layout.addWidget(cmap_lbl)
        colormap_layout.addWidget(self._colormap_combo, 1)

        # Depth range sliders
        range_label = QLabel("Depth Range (m)")
        range_label.setProperty("secondary", True)

        range_layout = QHBoxLayout()
        range_layout.setSpacing(4)
        self._depth_min_slider = LabeledSlider("Min", 0.0, 2.0, 0.1, 1)
        self._depth_max_slider = LabeledSlider("Max", 1.0, 15.0, 5.0, 1)
        self._depth_min_slider.valueChanged.connect(lambda v: setattr(self, "_depth_min_m", v))
        self._depth_max_slider.valueChanged.connect(lambda v: setattr(self, "_depth_max_m", v))
        range_layout.addWidget(self._depth_min_slider)
        range_layout.addWidget(self._depth_max_slider)

        # Reset point button
        self._reset_point_btn = QPushButton("Reset Point")
        self._reset_point_btn.clicked.connect(self._on_reset_depth_point)
        self._reset_point_btn.setEnabled(False)

        # Add all widgets to section
        section.add_widget(self._depth_enable_cb)
        section.add_widget(depth_info)
        section.add_widget(self._show_depth_map_cb)
        section.add_widget(self._measure_distance_cb)
        section.add_widget(self._distance_label)
        section.add_widget(self._point_label)
        section.add_layout(colormap_layout)
        section.add_widget(range_label)
        section.add_layout(range_layout)
        section.add_widget(self._reset_point_btn)

        return section

    def _create_color_calibration_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Color Calibration")

        self._color_filter_cb = QCheckBox("Enable Color Filter")
        self._color_filter_cb.stateChanged.connect(
            lambda: self._toggle_filter("color_filter", self._color_filter_cb.isChecked())
        )

        cs_layout = QHBoxLayout()
        cs_layout.setSpacing(6)
        cs_lbl = QLabel("Space:")
        cs_lbl.setProperty("secondary", True)
        self._color_space_combo = QComboBox()
        self._color_space_combo.addItems(["HSV", "LAB"])
        self._color_space_combo.currentTextChanged.connect(self._on_color_space_changed)
        cs_layout.addWidget(cs_lbl)
        cs_layout.addWidget(self._color_space_combo, 1)

        self._click_sample_cb = QCheckBox("Click to Sample")
        self._click_sample_cb.setToolTip("Click on video to sample color region")
        self._click_sample_cb.stateChanged.connect(self._on_click_sample_changed)

        tol_layout = QHBoxLayout()
        tol_layout.setSpacing(6)
        tol_lbl = QLabel("Tol:")
        tol_lbl.setProperty("secondary", True)
        self._tolerance_spin = QSpinBox()
        self._tolerance_spin.setRange(1, 50)
        self._tolerance_spin.setValue(15)
        self._tolerance_spin.valueChanged.connect(
            lambda v: setattr(self._color_manager, "flood_tolerance", v)
        )
        tol_layout.addWidget(tol_lbl)
        tol_layout.addWidget(self._tolerance_spin, 1)

        self._sample_label = QLabel("Samples: 0")
        self._sample_label.setProperty("muted", True)

        sample_btn_layout = QHBoxLayout()
        sample_btn_layout.setSpacing(4)
        self._undo_sample_btn = QPushButton("Undo")
        self._undo_sample_btn.clicked.connect(self._on_undo_sample)
        self._reset_sample_btn = QPushButton("Reset")
        self._reset_sample_btn.clicked.connect(self._on_reset_samples)
        sample_btn_layout.addWidget(self._undo_sample_btn)
        sample_btn_layout.addWidget(self._reset_sample_btn)

        self._ch1_label = QLabel("Hue")
        self._ch1_label.setProperty("secondary", True)
        self._lower_ch1 = LabeledSlider("Min", 0, 179, 0, 0)
        self._upper_ch1 = LabeledSlider("Max", 0, 179, 179, 0)
        self._lower_ch1.valueChanged.connect(self._on_slider_changed)
        self._upper_ch1.valueChanged.connect(self._on_slider_changed)

        self._ch2_label = QLabel("Sat")
        self._ch2_label.setProperty("secondary", True)
        self._lower_ch2 = LabeledSlider("Min", 0, 255, 0, 0)
        self._upper_ch2 = LabeledSlider("Max", 0, 255, 255, 0)
        self._lower_ch2.valueChanged.connect(self._on_slider_changed)
        self._upper_ch2.valueChanged.connect(self._on_slider_changed)

        self._ch3_label = QLabel("Val")
        self._ch3_label.setProperty("secondary", True)
        self._lower_ch3 = LabeledSlider("Min", 0, 255, 0, 0)
        self._upper_ch3 = LabeledSlider("Max", 0, 255, 255, 0)
        self._lower_ch3.valueChanged.connect(self._on_slider_changed)
        self._upper_ch3.valueChanged.connect(self._on_slider_changed)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(4)
        self._preset_combo = QComboBox()
        self._preset_combo.setEditable(False)
        self._refresh_presets()
        preset_layout.addWidget(self._preset_combo, 1)

        preset_btn_layout = QHBoxLayout()
        preset_btn_layout.setSpacing(4)
        self._load_preset_btn = QPushButton("Load")
        self._load_preset_btn.clicked.connect(self._on_load_preset)
        self._save_preset_btn = QPushButton("Save")
        self._save_preset_btn.clicked.connect(self._on_save_preset)
        self._refresh_preset_btn = QPushButton("↻")
        self._refresh_preset_btn.setFixedWidth(28)
        self._refresh_preset_btn.clicked.connect(self._refresh_presets)
        preset_btn_layout.addWidget(self._load_preset_btn)
        preset_btn_layout.addWidget(self._save_preset_btn)
        preset_btn_layout.addWidget(self._refresh_preset_btn)

        self._show_mask_cb = QCheckBox("Show Mask Only")
        self._show_mask_cb.setToolTip("Display binary mask instead of filtered image")

        section.add_widget(self._color_filter_cb)
        section.add_layout(cs_layout)
        section.add_widget(self._click_sample_cb)
        section.add_layout(tol_layout)
        section.add_widget(self._sample_label)
        section.add_layout(sample_btn_layout)

        ch1_layout = QHBoxLayout()
        ch1_layout.setSpacing(4)
        ch1_layout.addWidget(self._ch1_label)
        ch1_layout.addWidget(self._lower_ch1)
        ch1_layout.addWidget(self._upper_ch1)
        section.add_layout(ch1_layout)

        ch2_layout = QHBoxLayout()
        ch2_layout.setSpacing(4)
        ch2_layout.addWidget(self._ch2_label)
        ch2_layout.addWidget(self._lower_ch2)
        ch2_layout.addWidget(self._upper_ch2)
        section.add_layout(ch2_layout)

        ch3_layout = QHBoxLayout()
        ch3_layout.setSpacing(4)
        ch3_layout.addWidget(self._ch3_label)
        ch3_layout.addWidget(self._lower_ch3)
        ch3_layout.addWidget(self._upper_ch3)
        section.add_layout(ch3_layout)

        section.add_layout(preset_layout)
        section.add_layout(preset_btn_layout)
        section.add_widget(self._show_mask_cb)

        return section

    def _create_line_detection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Line Detection")

        self._line_detect_cb = QCheckBox("Enable Line Detection")
        self._line_detect_cb.stateChanged.connect(
            lambda: self._toggle_filter("line_detection", self._line_detect_cb.isChecked())
        )

        method_layout = QHBoxLayout()
        method_layout.setSpacing(6)
        method_lbl = QLabel("Method:")
        method_lbl.setProperty("secondary", True)
        self._line_method_combo = QComboBox()
        self._line_method_combo.addItems(self.ESTIMATION_METHODS)
        self._line_method_combo.currentTextChanged.connect(self._on_line_method_changed)
        method_layout.addWidget(method_lbl)
        method_layout.addWidget(self._line_method_combo, 1)

        self._show_roi_cb = QCheckBox("Show ROI")
        self._show_roi_cb.setChecked(True)

        roi_layout = QHBoxLayout()
        roi_layout.setSpacing(4)
        self._roi_width = LabeledSlider("W", 100, 640, 400, 0)
        self._roi_height = LabeledSlider("H", 100, 480, 280, 0)
        roi_layout.addWidget(self._roi_width)
        roi_layout.addWidget(self._roi_height)

        section.add_widget(self._line_detect_cb)
        section.add_layout(method_layout)
        section.add_widget(self._show_roi_cb)
        section.add_layout(roi_layout)

        return section

    def _create_edge_detection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Edge Detection")

        self._canny_cb = QCheckBox("Canny Edge")
        self._canny_cb.stateChanged.connect(
            lambda: self._toggle_filter("canny", self._canny_cb.isChecked())
        )

        canny_layout = QHBoxLayout()
        canny_layout.setSpacing(4)
        self._lower_canny = LabeledSlider("Lo", 0, 255, 100, 0)
        self._upper_canny = LabeledSlider("Hi", 0, 255, 200, 0)
        canny_layout.addWidget(self._lower_canny)
        canny_layout.addWidget(self._upper_canny)

        self._contour_cb = QCheckBox("Contour Detection")
        self._contour_cb.stateChanged.connect(
            lambda: self._toggle_filter("contour", self._contour_cb.isChecked())
        )

        section.add_widget(self._canny_cb)
        section.add_layout(canny_layout)
        section.add_widget(self._contour_cb)
        return section

    def _create_blur_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Blur & Sharpen")

        self._blur_cb = QCheckBox("Gaussian Blur")
        self._blur_cb.stateChanged.connect(
            lambda: self._toggle_filter("blur", self._blur_cb.isChecked())
        )

        self._blur_kernel = LabeledSlider("Kernel", 1, 31, 5, 0)

        self._sharpen_cb = QCheckBox("Sharpen")
        self._sharpen_cb.stateChanged.connect(
            lambda: self._toggle_filter("sharpen", self._sharpen_cb.isChecked())
        )

        section.add_widget(self._blur_cb)
        section.add_widget(self._blur_kernel)
        section.add_widget(self._sharpen_cb)

        return section

    def _create_transform_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Transformations")

        self._rotation_cb = QCheckBox("Rotation")
        self._rotation_cb.stateChanged.connect(
            lambda: self._toggle_filter("rotation", self._rotation_cb.isChecked())
        )

        self._rotation_angle = LabeledSlider("Angle", 0, 360, 0, 0)

        self._resize_cb = QCheckBox("Resize")
        self._resize_cb.stateChanged.connect(
            lambda: self._toggle_filter("resize", self._resize_cb.isChecked())
        )

        resize_layout = QHBoxLayout()
        resize_layout.setSpacing(4)
        self._resize_width = LabeledSlider("W", 100, 1920, 640, 0)
        self._resize_height = LabeledSlider("H", 100, 1080, 480, 0)
        resize_layout.addWidget(self._resize_width)
        resize_layout.addWidget(self._resize_height)

        section.add_widget(self._rotation_cb)
        section.add_widget(self._rotation_angle)
        section.add_widget(self._resize_cb)
        section.add_layout(resize_layout)

        return section

    def _create_morphology_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Morphological Ops")

        self._morphology_cb = QCheckBox("Morphology")
        self._morphology_cb.stateChanged.connect(
            lambda: self._toggle_filter("morphology", self._morphology_cb.isChecked())
        )

        op_layout = QHBoxLayout()
        op_layout.setSpacing(6)
        op_lbl = QLabel("Op:")
        op_lbl.setProperty("secondary", True)
        self._morph_op_combo = QComboBox()
        self._morph_op_combo.addItems(["erode", "dilate", "open", "close"])
        op_layout.addWidget(op_lbl)
        op_layout.addWidget(self._morph_op_combo, 1)

        self._morph_kernel = LabeledSlider("Kernel", 1, 31, 5, 0)

        self._adaptive_thresh_cb = QCheckBox("Adaptive Threshold")
        self._adaptive_thresh_cb.stateChanged.connect(
            lambda: self._toggle_filter("adaptive_thresh", self._adaptive_thresh_cb.isChecked())
        )

        self._hist_eq_cb = QCheckBox("Histogram Equalization")
        self._hist_eq_cb.stateChanged.connect(
            lambda: self._toggle_filter("hist_eq", self._hist_eq_cb.isChecked())
        )

        section.add_widget(self._morphology_cb)
        section.add_layout(op_layout)
        section.add_widget(self._morph_kernel)
        section.add_widget(self._adaptive_thresh_cb)
        section.add_widget(self._hist_eq_cb)

        return section

    def _create_effects_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Visual Effects")

        effects = [
            ("pencil_sketch", "Pencil Sketch"),
            ("stylization", "Stylization"),
            ("cartoonify", "Cartoonify"),
            ("color_quantization", "Color Quantization"),
            ("hough_lines", "Hough Lines"),
            ("hough_circles", "Hough Circles"),
            ("optical_flow", "Optical Flow"),
        ]

        self._effect_checkboxes = {}
        for key, label in effects:
            cb = QCheckBox(label)
            cb.toggled.connect(lambda checked, k=key: self._toggle_filter(k, checked))
            self._effect_checkboxes[key] = cb
            section.add_widget(cb)

        return section

    def _create_detection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("AI Detection")

        # Object detection toggle
        self._object_detect_cb = QCheckBox("Enable Object Detection")
        self._object_detect_cb.setToolTip("Run AI object detection on camera frames")
        self._object_detect_cb.stateChanged.connect(self._on_object_detection_toggled)

        # Detection configuration panel
        self._detection_panel = DetectionConfigPanel()
        self._detection_panel.detectorReady.connect(self._on_detector_ready)
        self._detection_panel.detectorUnloaded.connect(self._on_detector_unloaded)
        self._detection_panel.statusChanged.connect(lambda msg: self._info_label.setText(msg))

        # Hand and face tracking (existing)
        self._hand_cb = QCheckBox("Hand Tracking")
        self._hand_cb.stateChanged.connect(
            lambda: self._toggle_filter("hand", self._hand_cb.isChecked())
        )

        self._face_cb = QCheckBox("Face Mesh")
        self._face_cb.stateChanged.connect(
            lambda: self._toggle_filter("face", self._face_cb.isChecked())
        )

        section.add_widget(self._object_detect_cb)
        section.add_widget(self._detection_panel)
        section.add_widget(self._hand_cb)
        section.add_widget(self._face_cb)

        return section

    @Slot()
    def _on_object_detection_toggled(self) -> None:
        """Handle object detection enable/disable toggle."""
        enabled = self._object_detect_cb.isChecked()
        self._detection_enabled = enabled and self._ai_detector is not None

        if enabled and self._ai_detector is None:
            self._info_label.setText("Load a detection model first")
            self._object_detect_cb.setChecked(False)

    @Slot(object)
    def _on_detector_ready(self, detector) -> None:
        """Handle detector loaded event."""
        self._ai_detector = detector
        self._object_detect_cb.setEnabled(True)
        self._object_detect_cb.setChecked(True)
        self._detection_enabled = True

    @Slot()
    def _on_detector_unloaded(self) -> None:
        """Handle detector unloaded event."""
        self._ai_detector = None
        self._detection_enabled = False
        self._object_detect_cb.setChecked(False)
        self._last_detection_result = None

    def _create_aruco_section(self) -> CollapsibleSection:
        section = CollapsibleSection("ArUco Markers")

        self._aruco_cb = QCheckBox("ArUco Detection")
        self._aruco_cb.stateChanged.connect(
            lambda: self._toggle_filter("aruco", self._aruco_cb.isChecked())
        )

        dict_layout = QHBoxLayout()
        dict_layout.setSpacing(6)
        dict_lbl = QLabel("Dict:")
        dict_lbl.setProperty("secondary", True)
        self._aruco_dict_combo = QComboBox()
        self._aruco_dict_combo.addItems(
            [
                "DICT_4X4_50",
                "DICT_4X4_100",
                "DICT_5X5_50",
                "DICT_5X5_100",
                "DICT_6X6_50",
                "DICT_6X6_100",
                "DICT_6X6_250",
                "DICT_7X7_50",
                "DICT_ARUCO_ORIGINAL",
            ]
        )
        self._aruco_dict_combo.setCurrentIndex(6)
        dict_layout.addWidget(dict_lbl)
        dict_layout.addWidget(self._aruco_dict_combo, 1)

        section.add_widget(self._aruco_cb)
        section.add_layout(dict_layout)

        return section

    def _setup_timers(self) -> None:
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._process_frame)
        self._frame_timer.setInterval(16)

    def _init_cv_utils(self) -> None:
        self._cv_utils = OpenCVUtils()

    def _refresh_presets(self) -> None:
        self._preset_combo.clear()
        presets = self._color_manager.get_available_presets()
        for name, spaces in presets.items():
            space_str = ", ".join(spaces)
            self._preset_combo.addItem(f"{name} [{space_str}]", name)

    def _update_sliders_from_manager(self) -> None:
        lower = self._color_manager.lower
        upper = self._color_manager.upper

        self._lower_ch1.setValue(float(lower[0]))
        self._upper_ch1.setValue(float(upper[0]))
        self._lower_ch2.setValue(float(lower[1]))
        self._upper_ch2.setValue(float(upper[1]))
        self._lower_ch3.setValue(float(lower[2]))
        self._upper_ch3.setValue(float(upper[2]))

        self._sample_label.setText(f"Samples: {self._color_manager.sample_count}")

    def _update_manager_from_sliders(self) -> None:
        self._color_manager.lower = [
            int(self._lower_ch1.value()),
            int(self._lower_ch2.value()),
            int(self._lower_ch3.value()),
        ]
        self._color_manager.upper = [
            int(self._upper_ch1.value()),
            int(self._upper_ch2.value()),
            int(self._upper_ch3.value()),
        ]

    @Slot(str)
    def _on_color_space_changed(self, color_space: str) -> None:
        self._color_manager.color_space = color_space

        if color_space == "HSV":
            self._ch1_label.setText("Hue")
            self._ch2_label.setText("Sat")
            self._ch3_label.setText("Val")
            self._lower_ch1.setValue(0)
            self._upper_ch1.setValue(179)
        else:
            self._ch1_label.setText("L")
            self._ch2_label.setText("A")
            self._ch3_label.setText("B")
            self._lower_ch1.setValue(0)
            self._upper_ch1.setValue(255)

        self._update_sliders_from_manager()

    @Slot()
    def _on_click_sample_changed(self) -> None:
        enabled = self._click_sample_cb.isChecked() or self._measure_distance
        self._video_display.enable_rgb_click(enabled)

    @Slot(int, int)
    def _on_video_clicked(self, x: int, y: int) -> None:
        if self._current_frame is None:
            return

        # Handle color sampling
        if self._click_sample_cb.isChecked():
            success, _ = self._color_manager.sample_at_point(self._current_frame, x, y)
            if success:
                self._update_sliders_from_manager()

        # Handle depth measurement
        if self._measure_distance and self._is_depth_camera():
            self._selected_point = (x, y)
            self._point_label.setText(f"Point: ({x}, {y})")

            distance = self._get_distance_at_point(x, y)
            if distance is not None and distance > 0:
                self._current_distance = distance
                self._distance_label.setText(f"Distance: {distance:.3f} m")
            else:
                self._current_distance = None
                self._distance_label.setText("Distance: N/A")

    @Slot()
    def _on_slider_changed(self) -> None:
        self._update_manager_from_sliders()

    @Slot()
    def _on_undo_sample(self) -> None:
        if self._color_manager.undo_sample():
            self._update_sliders_from_manager()

    @Slot()
    def _on_reset_samples(self) -> None:
        self._color_manager.reset()
        self._update_sliders_from_manager()

    @Slot()
    def _on_load_preset(self) -> None:
        idx = self._preset_combo.currentIndex()
        if idx < 0:
            return

        name = self._preset_combo.currentData()
        color_space = self._color_space_combo.currentText()

        if self._color_manager.load_preset(name, color_space):
            self._update_sliders_from_manager()
            self._info_label.setText(f"Loaded preset: {name}")
        else:
            QMessageBox.warning(
                self,
                "Load Failed",
                f"Could not load preset '{name}' for {color_space}",
            )

    @Slot()
    def _on_save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
        if not ok or not name.strip():
            return

        name = name.strip()
        if self._color_manager.save_preset(name):
            self._refresh_presets()
            self._info_label.setText(f"Saved preset: {name}")
        else:
            QMessageBox.warning(self, "Save Failed", "Could not save preset")

    @Slot()
    def _on_depth_enabled_changed(self) -> None:
        """Handle depth enable checkbox toggle."""
        self._depth_enabled = self._depth_enable_cb.isChecked()
        if self._camera is not None:
            QMessageBox.information(
                self,
                "Restart Required",
                "Please stop and restart the camera to apply depth mode changes.",
            )

    @Slot()
    def _on_show_depth_changed(self) -> None:
        """Handle show depth map checkbox toggle."""
        self._show_depth_map = self._show_depth_map_cb.isChecked()
        self._video_display.set_dual_mode(self._show_depth_map)

    @Slot(int, int)
    def _on_depth_clicked(self, x: int, y: int) -> None:
        """Handle click on depth display for distance measurement."""
        if not self._measure_distance or not self._is_depth_camera():
            return

        self._selected_point = (x, y)
        self._point_label.setText(f"Point: ({x}, {y})")

        distance = self._get_distance_at_point(x, y)
        if distance is not None and distance > 0:
            self._current_distance = distance
            self._distance_label.setText(f"Distance: {distance:.3f} m")
        else:
            self._current_distance = None
            self._distance_label.setText("Distance: N/A")

    @Slot()
    def _on_measure_distance_changed(self) -> None:
        """Handle measure distance checkbox toggle."""
        self._measure_distance = self._measure_distance_cb.isChecked()
        click_enabled = self._measure_distance or self._click_sample_cb.isChecked()
        self._video_display.enable_rgb_click(click_enabled)
        self._video_display.enable_depth_click(self._measure_distance)
        self._reset_point_btn.setEnabled(self._measure_distance)
        if not self._measure_distance:
            self._selected_point = None
            self._current_distance = None
            self._distance_label.setText("Distance: -- m")
            self._point_label.setText("Point: (-, -)")

    @Slot(str)
    def _on_colormap_changed(self, colormap_name: str) -> None:
        """Handle colormap selection change."""
        colormaps = {
            "PLASMA": cv2.COLORMAP_PLASMA,
            "JET": cv2.COLORMAP_JET,
            "VIRIDIS": cv2.COLORMAP_VIRIDIS,
            "INFERNO": cv2.COLORMAP_INFERNO,
            "MAGMA": cv2.COLORMAP_MAGMA,
            "TURBO": cv2.COLORMAP_TURBO,
            "HOT": cv2.COLORMAP_HOT,
            "BONE": cv2.COLORMAP_BONE,
        }
        self._depth_colormap = colormaps.get(colormap_name, cv2.COLORMAP_PLASMA)

    @Slot()
    def _on_reset_depth_point(self) -> None:
        """Reset the selected depth measurement point."""
        self._selected_point = None
        self._current_distance = None
        self._distance_label.setText("Distance: -- m")
        self._point_label.setText("Point: (-, -)")

    def _is_depth_camera(self) -> bool:
        """Check if current camera supports depth."""
        if self._camera is None:
            return False
        from nectar.vision.camera.abstract import DepthCam

        return isinstance(self._camera, DepthCam)

    def _get_depth_frame(self) -> Optional[np.ndarray]:
        """Get depth frame from camera if available."""
        if not self._is_depth_camera():
            return None
        try:
            return self._camera.get_depth_frame()
        except (AttributeError, RuntimeError):
            return None

    def _get_distance_at_point(self, u: int, v: int) -> Optional[float]:
        """Get distance at pixel coordinates."""
        if not self._is_depth_camera():
            return None
        try:
            from nectar.vision.camera import ROSDepthCam

            if isinstance(self._camera, ROSDepthCam) and self._current_frame is not None:
                return self._camera.get_distance(u, v, color_shape=self._current_frame.shape)
            return self._camera.get_distance(u, v)
        except (AttributeError, RuntimeError, IndexError):
            return None

    def _colorize_depth(self, depth_frame: np.ndarray) -> np.ndarray:
        """Convert depth frame to colorized visualization."""
        if depth_frame is None:
            return None

        depth_clip = depth_frame.copy()
        depth_clip[depth_clip <= 0] = float("nan")

        # Normalize to range
        depth_norm = (depth_clip - self._depth_min_m) / (self._depth_max_m - self._depth_min_m)
        depth_norm = np.clip(depth_norm, 0, 1)
        depth_vis = (depth_norm * 255).astype(np.float32)
        depth_vis = np.nan_to_num(depth_vis, nan=0.0).astype(np.uint8)

        # Apply colormap
        return cv2.applyColorMap(depth_vis, self._depth_colormap)

    @Slot(str)
    def _on_line_method_changed(self, method_name: str) -> None:
        try:
            from nectar.vision.algorithms.line import (
                AdaptiveHoughLinesP,
                FitEllipse,
                HoughLinesP,
                LineDetector,
                RansacLine,
                RotatedRect,
            )

            methods = {
                "HoughLinesP": HoughLinesP,
                "RotatedRect": RotatedRect,
                "FitEllipse": FitEllipse,
                "RansacLine": RansacLine,
                "AdaptiveHoughLinesP": AdaptiveHoughLinesP,
            }
            if method_name in methods:
                self._line_detector = LineDetector(
                    color=None,
                    estimation_method=methods[method_name],
                )
        except (ImportError, ModuleNotFoundError):
            self._line_detector = None

    @Slot()
    def _start_camera(self) -> None:
        config = self._camera_config.get_config()

        self._start_btn.setEnabled(False)
        self._camera_config.setEnabled(False)
        self._video_display.set_placeholder("Connecting...")

        self._camera_thread = QThread()
        self._camera_worker = CameraInitWorker(
            config, enable_depth=self._depth_enabled, node=self._node
        )
        self._camera_worker.moveToThread(self._camera_thread)

        self._camera_thread.started.connect(self._camera_worker.run)
        self._camera_worker.finished.connect(self._on_camera_init_finished)
        self._camera_worker.camera_ready.connect(self._on_camera_ready)
        self._camera_worker.finished.connect(self._camera_thread.quit)

        self._camera_thread.start()

    @Slot(object)
    def _on_camera_ready(self, camera) -> None:
        self._camera = camera

    @Slot(bool, str)
    def _on_camera_init_finished(self, success: bool, error: str) -> None:
        if success and self._camera:
            self._frame_timer.start()
            self._stop_btn.setEnabled(True)
            self._video_display.set_placeholder("Starting...")

            # Enable depth controls if camera supports depth
            is_depth = self._is_depth_camera() and self._depth_enabled
            self._show_depth_map_cb.setEnabled(is_depth)
            self._measure_distance_cb.setEnabled(is_depth)

            camera_type = self._camera_config.camera_type
            if is_depth:
                self._info_label.setText(f"{camera_type.upper()} depth camera connected")
            else:
                self._info_label.setText(f"{camera_type.upper()} camera connected")
        else:
            self._video_display.set_placeholder(f"Error: {error}" if error else "Connection failed")
            self._start_btn.setEnabled(True)
            self._camera_config.setEnabled(True)
            self._camera = None
            self._show_depth_map_cb.setEnabled(False)
            self._measure_distance_cb.setEnabled(False)

    @Slot()
    def _stop_camera(self) -> None:
        self._frame_timer.stop()

        if self._camera_thread and self._camera_thread.isRunning():
            self._camera_thread.quit()
            self._camera_thread.wait(1000)

        if self._camera:
            try:
                self._camera.close()
            except (AttributeError, RuntimeError):
                pass
            self._camera = None

        self._current_frame = None
        self._video_display.clear_display()
        self._video_display.set_placeholder("Select a camera source to start")
        self._video_display.set_dual_mode(False)
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._camera_config.setEnabled(True)
        self._prev_gray = None

        # Reset depth state
        self._current_depth_frame = None
        self._selected_point = None
        self._current_distance = None
        self._show_depth_map = False
        self._show_depth_map_cb.setEnabled(False)
        self._show_depth_map_cb.setChecked(False)
        self._measure_distance_cb.setEnabled(False)
        self._measure_distance_cb.setChecked(False)
        self._reset_point_btn.setEnabled(False)
        self._distance_label.setText("Distance: -- m")
        self._point_label.setText("Point: (-, -)")

    def _toggle_filter(self, filter_name: str, enabled: bool) -> None:
        if enabled:
            if filter_name not in self._filter_params:
                self._filter_params[filter_name] = True
        else:
            if filter_name in self._filter_params:
                del self._filter_params[filter_name]

    @Slot()
    def _process_frame(self) -> None:
        if not self._camera:
            return

        try:
            frame = self._camera.get_frame()
            if frame is None:
                return

            self._current_frame = frame.copy()
            rgb_frame = frame.copy()
            depth_vis = None

            # Handle depth processing
            if self._depth_enabled and self._is_depth_camera():
                depth_frame = self._get_depth_frame()
                self._current_depth_frame = depth_frame

                # Create colorized depth visualization
                if depth_frame is not None:
                    depth_vis = self._colorize_depth(depth_frame)

                # Update distance at selected point
                if self._measure_distance and self._selected_point is not None:
                    u, v = self._selected_point
                    distance = self._get_distance_at_point(u, v)
                    if distance is not None and distance > 0:
                        self._current_distance = distance
                        self._distance_label.setText(f"Distance: {distance:.3f} m")

            # Apply filters to RGB frame
            rgb_frame = self._apply_filters(rgb_frame)

            # Draw depth measurement point on both frames
            if self._measure_distance and self._selected_point is not None:
                u, v = self._selected_point
                h, w = rgb_frame.shape[:2]
                if 0 <= u < w and 0 <= v < h:
                    # Draw on RGB
                    cv2.circle(rgb_frame, (u, v), 8, (0, 255, 255), 2)
                    cv2.circle(rgb_frame, (u, v), 3, (0, 255, 255), -1)

                    if self._current_distance is not None:
                        text = f"{self._current_distance:.2f}m"
                        text_x = max(10, min(u + 15, w - 80))
                        text_y = max(25, min(v - 10, h - 10))
                        cv2.putText(
                            rgb_frame,
                            text,
                            (text_x, text_y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 255),
                            2,
                        )

                    # Draw on depth visualization if available
                    if depth_vis is not None:
                        dh, dw = depth_vis.shape[:2]
                        from nectar.vision.camera import ROSDepthCam

                        if isinstance(self._camera, ROSDepthCam):
                            scaled_u = int(u * dw / w) if w > 0 else u
                            scaled_v = int(v * dh / h) if h > 0 else v
                        else:
                            scaled_u, scaled_v = u, v

                        if 0 <= scaled_u < dw and 0 <= scaled_v < dh:
                            cv2.circle(depth_vis, (scaled_u, scaled_v), 8, (255, 255, 255), 2)
                            cv2.circle(depth_vis, (scaled_u, scaled_v), 3, (255, 255, 255), -1)

            # Update FPS counter
            self._fps_counter += 1
            if self._fps_counter >= 30:
                elapsed = time.time() - self._fps_start
                self._fps = 30 / elapsed if elapsed > 0 else 0
                self._fps_start = time.time()
                self._fps_counter = 0

            h, w = rgb_frame.shape[:2]
            depth_str = " | Depth: ON" if self._depth_enabled and self._is_depth_camera() else ""
            self._info_label.setText(f"FPS: {self._fps:.1f} | Resolution: {w}x{h}{depth_str}")

            # Display RGB frame (always)
            self._video_display.display_rgb(rgb_frame)

            # Display depth visualization if enabled and available
            if self._show_depth_map and depth_vis is not None:
                self._video_display.display_depth(depth_vis)

        except Exception as e:
            self._info_label.setText(f"Error: {e}")

    def _draw_roi(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        roi_w = int(self._roi_width.value())
        roi_h = int(self._roi_height.value())

        center_x, center_y = w // 2, h // 2
        x1 = center_x - roi_w // 2
        y1 = center_y - roi_h // 2
        x2 = center_x + roi_w // 2
        y2 = center_y + roi_h // 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.line(frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 0), 1)
        cv2.line(frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 0), 1)

        return frame

    def _apply_filters(self, frame: np.ndarray) -> np.ndarray:
        color_mask = None

        if "color_filter" in self._filter_params:
            show_mask = self._show_mask_cb.isChecked()
            if show_mask:
                mask = self._color_manager.apply_filter(frame, return_mask=True)
                frame = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            else:
                color_mask = self._color_manager.apply_filter(frame, return_mask=True)
                frame = self._color_manager.apply_filter(frame)

        if "line_detection" in self._filter_params:
            if self._show_roi_cb.isChecked():
                frame = self._draw_roi(frame)

            if self._line_detector is None:
                self._on_line_method_changed(self._line_method_combo.currentText())

            if self._line_detector:
                try:
                    roi_w = int(self._roi_width.value())
                    roi_h = int(self._roi_height.value())

                    if color_mask is not None:
                        self._line_detector.external_mask = color_mask
                    else:
                        self._line_detector.external_mask = None

                    frame, _, _, _, _, _, _ = self._line_detector.detect_line(
                        frame, region=(roi_w, roi_h), draw=True
                    )
                except (ValueError, RuntimeError, cv2.error):
                    pass

        if "canny" in self._filter_params:
            frame = self._cv_utils.apply_edge_detection(
                frame,
                int(self._lower_canny.value()),
                int(self._upper_canny.value()),
            )

        if "contour" in self._filter_params:
            frame = self._cv_utils.apply_contour_detection(frame)

        if "blur" in self._filter_params:
            kernel = int(self._blur_kernel.value())
            frame = self._cv_utils.blur_image(frame, kernel)

        if "sharpen" in self._filter_params:
            frame = self._cv_utils.sharpen(frame)

        if "rotation" in self._filter_params:
            frame = self._cv_utils.rotate_image(frame, int(self._rotation_angle.value()))

        if "resize" in self._filter_params:
            frame = self._cv_utils.resize_image(
                frame,
                int(self._resize_width.value()),
                int(self._resize_height.value()),
            )

        if "morphology" in self._filter_params:
            op = self._morph_op_combo.currentText()
            kernel = int(self._morph_kernel.value())
            frame = self._cv_utils.morphology(frame, op, kernel)

        if "adaptive_thresh" in self._filter_params:
            frame = self._cv_utils.adaptive_threshold(frame)

        if "hist_eq" in self._filter_params:
            frame = self._cv_utils.equalize_histogram(frame)

        if "pencil_sketch" in self._filter_params:
            frame = self._cv_utils.pencil_sketch(frame)

        if "stylization" in self._filter_params:
            frame = self._cv_utils.stylization(frame)

        if "cartoonify" in self._filter_params:
            frame = self._cv_utils.cartoonify(frame)

        if "color_quantization" in self._filter_params:
            frame = self._cv_utils.color_quantization(frame)

        if "hough_lines" in self._filter_params:
            frame = self._cv_utils.hough_lines(frame)

        if "hough_circles" in self._filter_params:
            frame = self._cv_utils.hough_circles(frame)

        if "optical_flow" in self._filter_params:
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if self._prev_gray is not None:
                frame = self._cv_utils.optical_flow(self._prev_gray, curr_gray, frame)
            self._prev_gray = curr_gray

        # AI Object Detection
        if self._detection_enabled and self._ai_detector is not None:
            frame = self._apply_object_detection(frame)

        if "hand" in self._filter_params:
            frame = self._cv_utils.detect_hands(frame)

        if "face" in self._filter_params:
            frame = self._cv_utils.detect_faces(frame)

        if "aruco" in self._filter_params:
            dict_type = self._aruco_dict_combo.currentText()
            frame = self._cv_utils.detect_aruco_markers(frame, dict_type)

        return frame

    def _apply_object_detection(self, frame: np.ndarray) -> np.ndarray:
        """
        Run AI object detection on frame and draw results.

        Parameters
        ----------
        frame : np.ndarray
            Input frame (BGR).

        Returns
        -------
        np.ndarray
            Frame with detection annotations.
        """
        if self._ai_detector is None or not self._ai_detector.is_loaded:
            return frame

        try:
            # Run detection
            conf = self._detection_panel.conf_threshold
            iou = self._detection_panel.iou_threshold
            result = self._ai_detector.detect(frame, conf=conf, iou=iou)
            self._last_detection_result = result

            # Draw detections on frame
            if len(result) > 0:
                frame = self._ai_detector.draw_detections(
                    frame,
                    result,
                    show_labels=self._detection_panel.show_labels,
                    show_confidence=self._detection_panel.show_confidence,
                    show_class=self._detection_panel.show_labels,
                )

            # Update stats in panel
            class_counts = {}
            for det in result:
                name = det.class_name or f"class_{det.class_id}"
                class_counts[name] = class_counts.get(name, 0) + 1

            inference_ms = result.inference_time * 1000
            self._detection_panel.update_stats(len(result), inference_ms, class_counts)

        except Exception as e:
            # Log error but don't crash the frame loop
            self._info_label.setText(f"Detection error: {str(e)[:30]}")

        return frame

    def set_node(self, node: Node) -> None:
        self._node = node

    def cleanup(self) -> None:
        self._frame_timer.stop()

        if self._camera_thread and self._camera_thread.isRunning():
            self._camera_thread.quit()
            self._camera_thread.wait(1000)

        if self._camera:
            try:
                self._camera.close()
            except (AttributeError, RuntimeError):
                pass

        # Cleanup detection panel
        if hasattr(self, "_detection_panel"):
            self._detection_panel.cleanup()
        self._ai_detector = None

        if self._cv_utils:
            if hasattr(self._cv_utils, "_hand_tracker") and self._cv_utils._hand_tracker:
                try:
                    self._cv_utils._hand_tracker.close()
                except (AttributeError, RuntimeError):
                    pass
            if hasattr(self._cv_utils, "_face_tracker") and self._cv_utils._face_tracker:
                try:
                    self._cv_utils._face_tracker.close()
                except (AttributeError, RuntimeError):
                    pass


class OpenCVUtils:
    """OpenCV utility functions for image processing."""

    def __init__(self) -> None:
        self._hand_tracker = None
        self._face_tracker = None
        self._aruco_dicts = {
            "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
            "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
            "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
            "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
            "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
            "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
            "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
            "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
            "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
        }

    def apply_color_filter(
        self,
        frame: np.ndarray,
        lower: Tuple[int, int, int],
        upper: Tuple[int, int, int],
    ) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        return cv2.bitwise_and(frame, frame, mask=mask)

    def apply_edge_detection(self, frame: np.ndarray, lower: int, upper: int) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        edges = cv2.Canny(gray, lower, upper)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    def apply_contour_detection(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        result = frame.copy() if len(frame.shape) == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(result, contours, -1, (0, 255, 0), 2)
        return result

    def blur_image(self, frame: np.ndarray, kernel_size: int) -> np.ndarray:
        kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)

    def sharpen(self, frame: np.ndarray) -> np.ndarray:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        return cv2.filter2D(frame, -1, kernel)

    def rotate_image(self, frame: np.ndarray, angle: int) -> np.ndarray:
        h, w = frame.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(frame, matrix, (w, h))

    def resize_image(self, frame: np.ndarray, width: int, height: int) -> np.ndarray:
        return cv2.resize(frame, (width, height))

    def morphology(self, frame: np.ndarray, operation: str, kernel_size: int) -> np.ndarray:
        kernel = np.ones((kernel_size, kernel_size), np.uint8)
        ops = {
            "erode": cv2.MORPH_ERODE,
            "dilate": cv2.MORPH_DILATE,
            "open": cv2.MORPH_OPEN,
            "close": cv2.MORPH_CLOSE,
        }
        op = ops.get(operation, cv2.MORPH_ERODE)
        return cv2.morphologyEx(frame, op, kernel)

    def adaptive_threshold(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    def equalize_histogram(self, frame: np.ndarray) -> np.ndarray:
        if len(frame.shape) == 3:
            yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            yuv[:, :, 0] = cv2.equalizeHist(yuv[:, :, 0])
            return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)
        return cv2.equalizeHist(frame)

    def pencil_sketch(self, frame: np.ndarray) -> np.ndarray:
        gray, color = cv2.pencilSketch(frame, sigma_s=60, sigma_r=0.07, shade_factor=0.05)
        return color

    def stylization(self, frame: np.ndarray) -> np.ndarray:
        return cv2.stylization(frame, sigma_s=60, sigma_r=0.45)

    def cartoonify(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 9
        )
        color = cv2.bilateralFilter(frame, 9, 300, 300)
        return cv2.bitwise_and(color, color, mask=edges)

    def color_quantization(self, frame: np.ndarray, k: int = 8) -> np.ndarray:
        data = frame.reshape((-1, 3)).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.001)
        _, labels, centers = cv2.kmeans(data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        centers = np.uint8(centers)
        result = centers[labels.flatten()]
        return result.reshape(frame.shape)

    def hough_lines(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
        result = frame.copy() if len(frame.shape) == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return result

    def hough_circles(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        gray = cv2.medianBlur(gray, 5)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            1,
            20,
            param1=50,
            param2=30,
            minRadius=0,
            maxRadius=0,
        )
        result = frame.copy() if len(frame.shape) == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                cv2.circle(result, (i[0], i[1]), i[2], (0, 255, 0), 2)
                cv2.circle(result, (i[0], i[1]), 2, (0, 0, 255), 3)
        return result

    def optical_flow(
        self, prev_gray: np.ndarray, curr_gray: np.ndarray, frame: np.ndarray
    ) -> np.ndarray:
        flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv = np.zeros_like(frame)
        hsv[..., 0] = ang * 180 / np.pi / 2
        hsv[..., 1] = 255
        hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def detect_hands(self, frame: np.ndarray) -> np.ndarray:
        if self._hand_tracker is None:
            try:
                from nectar.vision import HandTracker, HandTrackerConfig

                config = HandTrackerConfig(num_hands=2, running_mode="IMAGE")
                self._hand_tracker = HandTracker(config)
                self._hand_tracker.start()
            except (ImportError, RuntimeError):
                return frame

        try:
            return self._hand_tracker.detect(frame, draw=True)
        except RuntimeError:
            return frame

    def detect_faces(self, frame: np.ndarray) -> np.ndarray:
        if self._face_tracker is None:
            try:
                from nectar.vision import FaceMeshTracker, FaceMeshTrackerConfig

                config = FaceMeshTrackerConfig(num_faces=1, running_mode="IMAGE")
                self._face_tracker = FaceMeshTracker(config)
                self._face_tracker.start()
            except (ImportError, RuntimeError):
                return frame

        try:
            return self._face_tracker.detect(frame, draw=True)
        except RuntimeError:
            return frame

    def detect_aruco_markers(self, frame: np.ndarray, dict_type: str) -> np.ndarray:
        dict_id = self._aruco_dicts.get(dict_type, cv2.aruco.DICT_6X6_250)
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        corners, ids, _ = detector.detectMarkers(gray)

        result = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(result, corners, ids)
        return result
