from typing import Optional, List, Callable, Dict, Any, Tuple
import os
import json
import time
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QCheckBox,
    QSplitter,
    QScrollArea,
    QLineEdit,
    QSpinBox,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject

from rclpy.node import Node

from mirela_sdk.interface.theme import COLORS
from mirela_sdk.interface.widgets import (
    CollapsibleSection,
    LabeledSlider,
    VideoDisplay,
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
        self._lower = np.array(
            self.DEFAULT_RANGES[self._color_space]["lower"], dtype=np.uint8
        )
        self._upper = np.array(
            self.DEFAULT_RANGES[self._color_space]["upper"], dtype=np.uint8
        )

    def undo_sample(self) -> bool:
        if self._sampled_pixels:
            self._sampled_pixels.pop()
            if self._sampled_pixels:
                self._compute_bounds()
            else:
                self.reset()
            return True
        return False

    def sample_at_point(
        self, frame: np.ndarray, x: int, y: int
    ) -> Tuple[bool, np.ndarray]:
        """
        Sample color region at clicked point using flood fill.

        Parameters
        ----------
        frame : np.ndarray
            BGR image frame.
        x : int
            X coordinate in frame.
        y : int
            Y coordinate in frame.

        Returns
        -------
        tuple
            (success, sampled_pixels) where success indicates if sampling worked.
        """
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
        """
        Apply color filter to frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR input frame.
        return_mask : bool
            If True, return binary mask instead of filtered image.

        Returns
        -------
        np.ndarray
            Filtered image or binary mask.
        """
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
        """
        Get available color presets from calibration file.

        Returns
        -------
        dict
            Dictionary mapping color names to available color spaces.
        """
        if not os.path.exists(self._calibration_path):
            return {}

        try:
            with open(self._calibration_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {name: list(spaces.keys()) for name, spaces in data.items()}
        except (json.JSONDecodeError, IOError):
            return {}

    def load_preset(self, name: str, color_space: Optional[str] = None) -> bool:
        """
        Load color preset from calibration file.

        Parameters
        ----------
        name : str
            Preset name.
        color_space : str, optional
            Color space to load (defaults to current).

        Returns
        -------
        bool
            True if loaded successfully.
        """
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
        """
        Save current color values as preset.

        Parameters
        ----------
        name : str
            Preset name.

        Returns
        -------
        bool
            True if saved successfully.
        """
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
    """Background worker for camera initialization."""

    finished = Signal(bool, str)
    camera_ready = Signal(object)

    def __init__(self, source: str, config: dict) -> None:
        super().__init__()
        self._source = source
        self._config = config
        self._camera = None

    @property
    def camera(self):
        return self._camera

    def run(self) -> None:
        try:
            from mirela_sdk.vision import CameraFactory, OpenCVConfig

            if self._source == "webcam":
                config = OpenCVConfig(
                    device_index=self._config.get("device", 0),
                    width=self._config.get("width", 640),
                    height=self._config.get("height", 480),
                )
                self._camera = CameraFactory.from_source("webcam", config=config)
            elif self._source == "ros":
                from mirela_sdk.vision import ROSConfig

                config = ROSConfig(topic=self._config.get("topic", "/camera/image_raw"))
                self._camera = CameraFactory.from_source(
                    "ros", config=config, node=self._config.get("node")
                )
            elif self._source == "file":
                from mirela_sdk.vision import FileImageConfig

                config = FileImageConfig(path=self._config.get("path", ""))
                self._camera = CameraFactory.from_source("file", config=config)
            else:
                self._camera = CameraFactory.from_source(self._source)

            self._camera.start()
            self.camera_ready.emit(self._camera)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


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

    def __init__(
        self, node: Optional[Node] = None, parent: Optional[QWidget] = None
    ) -> None:
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

        self._setup_ui()
        self._setup_timers()
        self._init_cv_utils()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_control_panel()
        right_panel = self._create_video_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([420, 800])

        layout.addWidget(splitter)

    def _create_control_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(400)
        scroll.setMaximumWidth(480)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_camera_selector())
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
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Live Preview")
        header.setStyleSheet(
            f"""
            font-size: 16px;
            font-weight: bold;
            color: {COLORS.accent};
            padding: 8px;
        """
        )
        header.setAlignment(Qt.AlignCenter)

        self._video_display = VideoDisplay()
        self._video_display.set_placeholder("Select a camera source to start")
        self._video_display.clicked.connect(self._on_video_clicked)

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

        source_layout = QHBoxLayout()
        self._source_combo = QComboBox()
        self._source_combo.addItems(
            [
                "webcam",
                "realsense",
                "oakd",
                "ros",
                "file",
            ]
        )
        self._source_combo.setEditable(True)

        source_layout.addWidget(QLabel("Source:"))
        source_layout.addWidget(self._source_combo, 1)

        config_layout = QGridLayout()
        config_layout.addWidget(QLabel("Device/Topic:"), 0, 0)
        self._device_input = QLineEdit("0")
        config_layout.addWidget(self._device_input, 0, 1)

        config_layout.addWidget(QLabel("Width:"), 1, 0)
        self._width_spin = QSpinBox()
        self._width_spin.setRange(320, 1920)
        self._width_spin.setValue(640)
        config_layout.addWidget(self._width_spin, 1, 1)

        config_layout.addWidget(QLabel("Height:"), 2, 0)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(240, 1080)
        self._height_spin.setValue(480)
        config_layout.addWidget(self._height_spin, 2, 1)

        btn_layout = QHBoxLayout()
        self._start_btn = QPushButton("Start")
        self._start_btn.setProperty("accent", True)
        self._start_btn.clicked.connect(self._start_camera)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._stop_camera)
        self._stop_btn.setEnabled(False)

        btn_layout.addWidget(self._start_btn)
        btn_layout.addWidget(self._stop_btn)

        layout.addLayout(source_layout)
        layout.addLayout(config_layout)
        layout.addLayout(btn_layout)

        return group

    def _create_color_calibration_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Color Calibration")

        self._color_filter_cb = QCheckBox("Enable Color Filter")
        self._color_filter_cb.stateChanged.connect(
            lambda: self._toggle_filter(
                "color_filter", self._color_filter_cb.isChecked()
            )
        )

        cs_layout = QHBoxLayout()
        cs_layout.addWidget(QLabel("Color Space:"))
        self._color_space_combo = QComboBox()
        self._color_space_combo.addItems(["HSV", "LAB"])
        self._color_space_combo.currentTextChanged.connect(self._on_color_space_changed)
        cs_layout.addWidget(self._color_space_combo, 1)

        self._click_sample_cb = QCheckBox("Click to Sample")
        self._click_sample_cb.setToolTip("Click on video to sample color region")
        self._click_sample_cb.stateChanged.connect(self._on_click_sample_changed)

        tolerance_layout = QHBoxLayout()
        tolerance_layout.addWidget(QLabel("Tolerance:"))
        self._tolerance_spin = QSpinBox()
        self._tolerance_spin.setRange(1, 50)
        self._tolerance_spin.setValue(15)
        self._tolerance_spin.valueChanged.connect(
            lambda v: setattr(self._color_manager, "flood_tolerance", v)
        )
        tolerance_layout.addWidget(self._tolerance_spin, 1)

        self._sample_label = QLabel("Samples: 0")
        self._sample_label.setProperty("secondary", True)

        sample_btn_layout = QHBoxLayout()
        self._undo_sample_btn = QPushButton("Undo")
        self._undo_sample_btn.clicked.connect(self._on_undo_sample)
        self._reset_sample_btn = QPushButton("Reset")
        self._reset_sample_btn.clicked.connect(self._on_reset_samples)
        sample_btn_layout.addWidget(self._undo_sample_btn)
        sample_btn_layout.addWidget(self._reset_sample_btn)

        self._ch1_label = QLabel("Hue")
        self._lower_ch1 = LabeledSlider("Min", 0, 179, 0, 0)
        self._upper_ch1 = LabeledSlider("Max", 0, 179, 179, 0)
        self._lower_ch1.valueChanged.connect(self._on_slider_changed)
        self._upper_ch1.valueChanged.connect(self._on_slider_changed)

        self._ch2_label = QLabel("Saturation")
        self._lower_ch2 = LabeledSlider("Min", 0, 255, 0, 0)
        self._upper_ch2 = LabeledSlider("Max", 0, 255, 255, 0)
        self._lower_ch2.valueChanged.connect(self._on_slider_changed)
        self._upper_ch2.valueChanged.connect(self._on_slider_changed)

        self._ch3_label = QLabel("Value")
        self._lower_ch3 = LabeledSlider("Min", 0, 255, 0, 0)
        self._upper_ch3 = LabeledSlider("Max", 0, 255, 255, 0)
        self._lower_ch3.valueChanged.connect(self._on_slider_changed)
        self._upper_ch3.valueChanged.connect(self._on_slider_changed)

        preset_label = QLabel("Presets")
        preset_label.setProperty("secondary", True)

        preset_layout = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.setEditable(False)
        self._preset_combo.setMinimumWidth(120)
        self._refresh_presets()
        preset_layout.addWidget(self._preset_combo, 1)

        preset_btn_layout = QHBoxLayout()
        self._load_preset_btn = QPushButton("Load")
        self._load_preset_btn.clicked.connect(self._on_load_preset)
        self._save_preset_btn = QPushButton("Save")
        self._save_preset_btn.clicked.connect(self._on_save_preset)
        self._refresh_preset_btn = QPushButton("Refresh")
        self._refresh_preset_btn.clicked.connect(self._refresh_presets)
        preset_btn_layout.addWidget(self._load_preset_btn)
        preset_btn_layout.addWidget(self._save_preset_btn)
        preset_btn_layout.addWidget(self._refresh_preset_btn)

        self._show_mask_cb = QCheckBox("Show Mask Only")
        self._show_mask_cb.setToolTip("Display binary mask instead of filtered image")

        section.add_widget(self._color_filter_cb)
        section.add_layout(cs_layout)
        section.add_widget(self._click_sample_cb)
        section.add_layout(tolerance_layout)
        section.add_widget(self._sample_label)
        section.add_layout(sample_btn_layout)

        ch1_layout = QHBoxLayout()
        ch1_layout.addWidget(self._ch1_label)
        ch1_layout.addWidget(self._lower_ch1)
        ch1_layout.addWidget(self._upper_ch1)
        section.add_layout(ch1_layout)

        ch2_layout = QHBoxLayout()
        ch2_layout.addWidget(self._ch2_label)
        ch2_layout.addWidget(self._lower_ch2)
        ch2_layout.addWidget(self._upper_ch2)
        section.add_layout(ch2_layout)

        ch3_layout = QHBoxLayout()
        ch3_layout.addWidget(self._ch3_label)
        ch3_layout.addWidget(self._lower_ch3)
        ch3_layout.addWidget(self._upper_ch3)
        section.add_layout(ch3_layout)

        section.add_widget(preset_label)
        section.add_layout(preset_layout)
        section.add_layout(preset_btn_layout)
        section.add_widget(self._show_mask_cb)

        return section

    def _create_line_detection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Line Detection")

        self._line_detect_cb = QCheckBox("Enable Line Detection")
        self._line_detect_cb.stateChanged.connect(
            lambda: self._toggle_filter(
                "line_detection", self._line_detect_cb.isChecked()
            )
        )

        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Method:"))
        self._line_method_combo = QComboBox()
        self._line_method_combo.addItems(self.ESTIMATION_METHODS)
        self._line_method_combo.currentTextChanged.connect(self._on_line_method_changed)
        method_layout.addWidget(self._line_method_combo, 1)

        self._show_roi_cb = QCheckBox("Show ROI")
        self._show_roi_cb.setChecked(True)
        self._show_roi_cb.setToolTip("Display Region of Interest rectangle")

        roi_label = QLabel("ROI (Region of Interest)")
        roi_label.setProperty("secondary", True)

        self._roi_width = LabeledSlider("Width", 100, 640, 400, 0)
        self._roi_height = LabeledSlider("Height", 100, 480, 280, 0)

        info_label = QLabel("Line detection uses color filter if enabled")
        info_label.setProperty("secondary", True)
        info_label.setWordWrap(True)

        section.add_widget(self._line_detect_cb)
        section.add_layout(method_layout)
        section.add_widget(self._show_roi_cb)
        section.add_widget(roi_label)

        roi_layout = QHBoxLayout()
        roi_layout.addWidget(self._roi_width)
        roi_layout.addWidget(self._roi_height)
        section.add_layout(roi_layout)

        section.add_widget(info_label)

        return section

    def _create_edge_detection_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Edge Detection")

        self._canny_cb = QCheckBox("Enable Canny Edge")
        self._canny_cb.stateChanged.connect(
            lambda: self._toggle_filter("canny", self._canny_cb.isChecked())
        )

        self._lower_canny = LabeledSlider("Lower Threshold", 0, 255, 100, 0)
        self._upper_canny = LabeledSlider("Upper Threshold", 0, 255, 200, 0)

        self._contour_cb = QCheckBox("Enable Contour Detection")
        self._contour_cb.stateChanged.connect(
            lambda: self._toggle_filter("contour", self._contour_cb.isChecked())
        )

        section.add_widget(self._canny_cb)

        canny_layout = QHBoxLayout()
        canny_layout.addWidget(self._lower_canny)
        canny_layout.addWidget(self._upper_canny)
        section.add_layout(canny_layout)

        section.add_widget(self._contour_cb)
        return section

    def _create_blur_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Blur & Sharpen")

        self._blur_cb = QCheckBox("Enable Gaussian Blur")
        self._blur_cb.stateChanged.connect(
            lambda: self._toggle_filter("blur", self._blur_cb.isChecked())
        )

        self._blur_kernel = LabeledSlider("Kernel Size", 1, 31, 5, 0)

        self._sharpen_cb = QCheckBox("Enable Sharpen")
        self._sharpen_cb.stateChanged.connect(
            lambda: self._toggle_filter("sharpen", self._sharpen_cb.isChecked())
        )

        section.add_widget(self._blur_cb)
        section.add_widget(self._blur_kernel)
        section.add_widget(self._sharpen_cb)

        return section

    def _create_transform_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Transformations")

        self._rotation_cb = QCheckBox("Enable Rotation")
        self._rotation_cb.stateChanged.connect(
            lambda: self._toggle_filter("rotation", self._rotation_cb.isChecked())
        )

        self._rotation_angle = LabeledSlider("Angle", 0, 360, 0, 0)

        self._resize_cb = QCheckBox("Enable Resize")
        self._resize_cb.stateChanged.connect(
            lambda: self._toggle_filter("resize", self._resize_cb.isChecked())
        )

        self._resize_width = LabeledSlider("Width", 100, 1920, 640, 0)
        self._resize_height = LabeledSlider("Height", 100, 1080, 480, 0)

        section.add_widget(self._rotation_cb)
        section.add_widget(self._rotation_angle)
        section.add_widget(self._resize_cb)

        resize_layout = QHBoxLayout()
        resize_layout.addWidget(self._resize_width)
        resize_layout.addWidget(self._resize_height)
        section.add_layout(resize_layout)

        return section

    def _create_morphology_section(self) -> CollapsibleSection:
        section = CollapsibleSection("Morphological Ops")

        self._morphology_cb = QCheckBox("Enable Morphology")
        self._morphology_cb.stateChanged.connect(
            lambda: self._toggle_filter("morphology", self._morphology_cb.isChecked())
        )

        op_layout = QHBoxLayout()
        op_layout.addWidget(QLabel("Operation:"))
        self._morph_op_combo = QComboBox()
        self._morph_op_combo.addItems(["erode", "dilate", "open", "close"])
        op_layout.addWidget(self._morph_op_combo)

        self._morph_kernel = LabeledSlider("Kernel Size", 1, 31, 5, 0)

        self._adaptive_thresh_cb = QCheckBox("Adaptive Threshold")
        self._adaptive_thresh_cb.stateChanged.connect(
            lambda: self._toggle_filter(
                "adaptive_thresh", self._adaptive_thresh_cb.isChecked()
            )
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

        self._hand_cb = QCheckBox("Hand Tracking")
        self._hand_cb.stateChanged.connect(
            lambda: self._toggle_filter("hand", self._hand_cb.isChecked())
        )

        self._face_cb = QCheckBox("Face Mesh")
        self._face_cb.stateChanged.connect(
            lambda: self._toggle_filter("face", self._face_cb.isChecked())
        )

        section.add_widget(self._hand_cb)
        section.add_widget(self._face_cb)

        return section

    def _create_aruco_section(self) -> CollapsibleSection:
        section = CollapsibleSection("ArUco Markers")

        self._aruco_cb = QCheckBox("Enable ArUco Detection")
        self._aruco_cb.stateChanged.connect(
            lambda: self._toggle_filter("aruco", self._aruco_cb.isChecked())
        )

        dict_layout = QHBoxLayout()
        dict_layout.addWidget(QLabel("Dictionary:"))
        self._aruco_dict_combo = QComboBox()
        self._aruco_dict_combo.addItems(
            [
                "DICT_4X4_50",
                "DICT_4X4_100",
                "DICT_4X4_250",
                "DICT_4X4_1000",
                "DICT_5X5_50",
                "DICT_5X5_100",
                "DICT_5X5_250",
                "DICT_5X5_1000",
                "DICT_6X6_50",
                "DICT_6X6_100",
                "DICT_6X6_250",
                "DICT_6X6_1000",
                "DICT_7X7_50",
                "DICT_7X7_100",
                "DICT_7X7_250",
                "DICT_7X7_1000",
                "DICT_ARUCO_ORIGINAL",
            ]
        )
        self._aruco_dict_combo.setCurrentIndex(10)
        dict_layout.addWidget(self._aruco_dict_combo)

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
            self._ch2_label.setText("Saturation")
            self._ch3_label.setText("Value")
            self._lower_ch1.setValue(0)
            self._upper_ch1.setValue(179)
        else:
            self._ch1_label.setText("L (Lightness)")
            self._ch2_label.setText("A (Green-Red)")
            self._ch3_label.setText("B (Blue-Yellow)")
            self._lower_ch1.setValue(0)
            self._upper_ch1.setValue(255)

        self._update_sliders_from_manager()

    @Slot()
    def _on_click_sample_changed(self) -> None:
        enabled = self._click_sample_cb.isChecked()
        self._video_display.enable_click(enabled)

    @Slot(int, int)
    def _on_video_clicked(self, x: int, y: int) -> None:
        if not self._click_sample_cb.isChecked():
            return

        if self._current_frame is None:
            return

        success, _ = self._color_manager.sample_at_point(self._current_frame, x, y)
        if success:
            self._update_sliders_from_manager()

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

    @Slot(str)
    def _on_line_method_changed(self, method_name: str) -> None:
        try:
            from mirela_sdk.vision.algorithms.line import (
                LineDetector,
                HoughLinesP,
                RotatedRect,
                FitEllipse,
                RansacLine,
                AdaptiveHoughLinesP,
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
        except ImportError:
            self._line_detector = None

    @Slot()
    def _start_camera(self) -> None:
        source = self._source_combo.currentText()
        device = self._device_input.text()

        self._start_btn.setEnabled(False)
        self._video_display.set_placeholder("Connecting...")

        config = {
            "width": self._width_spin.value(),
            "height": self._height_spin.value(),
            "node": self._node,
        }

        if source == "webcam":
            config["device"] = int(device) if device.isdigit() else 0
        elif source == "ros":
            config["topic"] = device if device.startswith("/") else f"/{device}"
        elif source == "file":
            config["path"] = device

        self._camera_thread = QThread()
        self._camera_worker = CameraInitWorker(source, config)
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
            self._source_combo.setEnabled(False)
            self._video_display.set_placeholder("Starting...")
        else:
            self._video_display.set_placeholder(
                f"Error: {error}" if error else "Connection failed"
            )
            self._start_btn.setEnabled(True)
            self._camera = None

    @Slot()
    def _stop_camera(self) -> None:
        self._frame_timer.stop()

        if self._camera_thread and self._camera_thread.isRunning():
            self._camera_thread.quit()
            self._camera_thread.wait(1000)

        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None

        self._current_frame = None
        self._video_display.clear_display()
        self._video_display.set_placeholder("Select a camera source to start")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._source_combo.setEnabled(True)
        self._prev_gray = None

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

            frame = self._apply_filters(frame)

            self._fps_counter += 1
            if self._fps_counter >= 30:
                elapsed = time.time() - self._fps_start
                self._fps = 30 / elapsed if elapsed > 0 else 0
                self._fps_start = time.time()
                self._fps_counter = 0

            h, w = frame.shape[:2]
            self._info_label.setText(f"FPS: {self._fps:.1f} | Resolution: {w}x{h}")

            self._video_display.display_frame(frame)

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
        cv2.line(
            frame, (center_x - 15, center_y), (center_x + 15, center_y), (0, 255, 0), 1
        )
        cv2.line(
            frame, (center_x, center_y - 15), (center_x, center_y + 15), (0, 255, 0), 1
        )

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

                    frame, _, cx, cy, angle, _, _ = self._line_detector.detect_line(
                        frame, region=(roi_w, roi_h), draw=True
                    )
                except Exception:
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
            frame = self._cv_utils.rotate_image(
                frame, int(self._rotation_angle.value())
            )

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

        if "hand" in self._filter_params:
            frame = self._cv_utils.detect_hands(frame)

        if "face" in self._filter_params:
            frame = self._cv_utils.detect_faces(frame)

        if "aruco" in self._filter_params:
            dict_type = self._aruco_dict_combo.currentText()
            frame = self._cv_utils.detect_aruco_markers(frame, dict_type)

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
            except Exception:
                pass

        if self._cv_utils:
            if (
                hasattr(self._cv_utils, "_hand_tracker")
                and self._cv_utils._hand_tracker
            ):
                try:
                    self._cv_utils._hand_tracker.close()
                except Exception:
                    pass
            if (
                hasattr(self._cv_utils, "_face_tracker")
                and self._cv_utils._face_tracker
            ):
                try:
                    self._cv_utils._face_tracker.close()
                except Exception:
                    pass


class OpenCVUtils:
    """OpenCV utility functions for image processing."""

    def __init__(self) -> None:
        self._hand_tracker = None
        self._face_tracker = None
        self._aruco_dicts = {
            "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
            "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
            "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
            "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
            "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
            "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
            "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
            "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
            "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
            "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
            "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
            "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
            "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
            "DICT_7X7_100": cv2.aruco.DICT_7X7_100,
            "DICT_7X7_250": cv2.aruco.DICT_7X7_250,
            "DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
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

    def apply_edge_detection(
        self, frame: np.ndarray, lower: int, upper: int
    ) -> np.ndarray:
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
        edges = cv2.Canny(gray, lower, upper)
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    def apply_contour_detection(self, frame: np.ndarray) -> np.ndarray:
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        result = (
            frame.copy()
            if len(frame.shape) == 3
            else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        )
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

    def morphology(
        self, frame: np.ndarray, operation: str, kernel_size: int
    ) -> np.ndarray:
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
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
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
        gray, color = cv2.pencilSketch(
            frame, sigma_s=60, sigma_r=0.07, shade_factor=0.05
        )
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
        _, labels, centers = cv2.kmeans(
            data, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )
        centers = np.uint8(centers)
        result = centers[labels.flatten()]
        return result.reshape(frame.shape)

    def hough_lines(self, frame: np.ndarray) -> np.ndarray:
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10
        )
        result = (
            frame.copy()
            if len(frame.shape) == 3
            else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        )
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(result, (x1, y1), (x2, y2), (0, 255, 0), 2)
        return result

    def hough_circles(self, frame: np.ndarray) -> np.ndarray:
        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
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
        result = (
            frame.copy()
            if len(frame.shape) == 3
            else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        )
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                cv2.circle(result, (i[0], i[1]), i[2], (0, 255, 0), 2)
                cv2.circle(result, (i[0], i[1]), 2, (0, 0, 255), 3)
        return result

    def optical_flow(
        self, prev_gray: np.ndarray, curr_gray: np.ndarray, frame: np.ndarray
    ) -> np.ndarray:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        hsv = np.zeros_like(frame)
        hsv[..., 0] = ang * 180 / np.pi / 2
        hsv[..., 1] = 255
        hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def detect_hands(self, frame: np.ndarray) -> np.ndarray:
        if self._hand_tracker is None:
            try:
                from mirela_sdk.vision import HandTracker, HandTrackerConfig

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
                from mirela_sdk.vision import FaceMeshTracker, FaceMeshTrackerConfig

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

        gray = (
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        )
        corners, ids, _ = detector.detectMarkers(gray)

        result = frame.copy()
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(result, corners, ids)
        return result
