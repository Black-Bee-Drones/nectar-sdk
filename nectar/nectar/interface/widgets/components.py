from typing import Any, Dict, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nectar.interface.theme import COLORS


class Card(QFrame):
    """Elevated card container with rounded corners."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"""
            Card {{
                background-color: {COLORS.surface};
                border: 1px solid {COLORS.border};
                border-radius: 6px;
            }}
        """
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class StatusIndicator(QWidget):
    """Compact circular status indicator with label."""

    def __init__(
        self,
        label: str = "",
        status: str = "inactive",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._indicator = QLabel()
        self._indicator.setFixedSize(8, 8)
        self._label = QLabel(label)
        self._label.setProperty("secondary", True)

        layout.addWidget(self._indicator)
        layout.addWidget(self._label)
        layout.addStretch()

        self.set_status(status)

    def set_status(self, status: str) -> None:
        colors = {
            "active": COLORS.success,
            "inactive": COLORS.text_muted,
            "warning": COLORS.warning,
            "error": COLORS.error,
            "info": COLORS.info,
        }
        color = colors.get(status, COLORS.text_muted)
        self._indicator.setStyleSheet(
            f"""
            background-color: {color};
            border-radius: 4px;
        """
        )

    def set_label(self, label: str) -> None:
        self._label.setText(label)


class LabeledSlider(QWidget):
    """Compact slider with label and value display. Supports vertical and horizontal orientations."""

    valueChanged = Signal(float)

    def __init__(
        self,
        label: str,
        min_val: float = 0.0,
        max_val: float = 1.0,
        default: float = 0.0,
        decimals: int = 2,
        orientation: Qt.Orientation = Qt.Vertical,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min_val = min_val
        self._max_val = max_val
        self._decimals = decimals
        self._scale = 10**decimals
        self._orientation = orientation

        if orientation == Qt.Horizontal:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)
            layout.setAlignment(Qt.AlignCenter)

            self._label = QLabel(label)
            self._label.setAlignment(Qt.AlignCenter)
            self._label.setProperty("muted", True)

            self._value_label = QLabel(f"{default:.{decimals}f}")
            self._value_label.setAlignment(Qt.AlignCenter)
            self._value_label.setStyleSheet(
                f"color: {COLORS.accent}; font-weight: 600; font-size: 12px;"
            )

            self._slider = QSlider(Qt.Horizontal)
            self._slider.setMinimum(int(min_val * self._scale))
            self._slider.setMaximum(int(max_val * self._scale))
            self._slider.setValue(int(default * self._scale))
            self._slider.setMinimumWidth(100)
            self._slider.setFixedHeight(20)
            self._slider.valueChanged.connect(self._on_value_changed)

            layout.addWidget(self._label, 0, Qt.AlignHCenter)
            layout.addWidget(self._slider, 0, Qt.AlignHCenter)
            layout.addWidget(self._value_label, 0, Qt.AlignHCenter)

            self.setMinimumHeight(60)
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)
            layout.setAlignment(Qt.AlignCenter)

            self._label = QLabel(label)
            self._label.setAlignment(Qt.AlignCenter)
            self._label.setProperty("muted", True)

            self._value_label = QLabel(f"{default:.{decimals}f}")
            self._value_label.setAlignment(Qt.AlignCenter)
            self._value_label.setStyleSheet(
                f"color: {COLORS.accent}; font-weight: 600; font-size: 12px;"
            )

            self._slider = QSlider(Qt.Vertical)
            self._slider.setMinimum(int(min_val * self._scale))
            self._slider.setMaximum(int(max_val * self._scale))
            self._slider.setValue(int(default * self._scale))
            self._slider.setMinimumHeight(100)
            self._slider.setFixedWidth(20)
            self._slider.valueChanged.connect(self._on_value_changed)

            layout.addWidget(self._label, 0, Qt.AlignHCenter)
            layout.addWidget(self._slider, 1, Qt.AlignHCenter)
            layout.addWidget(self._value_label, 0, Qt.AlignHCenter)

            self.setMinimumWidth(50)
            self.setMaximumWidth(70)

    def _on_value_changed(self, value: int) -> None:
        real_value = value / self._scale
        self._value_label.setText(f"{real_value:.{self._decimals}f}")
        self.valueChanged.emit(real_value)

    def value(self) -> float:
        return self._slider.value() / self._scale

    def setValue(self, value: float) -> None:
        self._slider.setValue(int(value * self._scale))

    def setEnabled(self, enabled: bool) -> None:
        self._slider.setEnabled(enabled)


class CollapsibleSection(QWidget):
    """Compact collapsible section with toggle button."""

    def __init__(
        self,
        title: str,
        collapsed: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._collapsed = collapsed

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        arrow = "▸" if collapsed else "▾"
        self._toggle = QPushButton(f"{arrow}  {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {COLORS.surface_elevated};
                color: {COLORS.text_primary};
                border: none;
                padding: 6px 10px;
                text-align: left;
                font-weight: 500;
                font-size: 11px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.border};
            }}
            QPushButton:checked {{
                color: {COLORS.accent};
            }}
        """
        )
        self._toggle.clicked.connect(self._on_toggle)

        self._content = QFrame()
        self._content.setStyleSheet("background-color: transparent;")
        self._content.setVisible(not collapsed)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(6, 6, 6, 6)
        self._content_layout.setSpacing(6)

        main_layout.addWidget(self._toggle)
        main_layout.addWidget(self._content)

    def _on_toggle(self) -> None:
        self._collapsed = not self._toggle.isChecked()
        self._content.setVisible(not self._collapsed)
        arrow = "▸" if self._collapsed else "▾"
        self._toggle.setText(f"{arrow}  {self._title}")

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._content_layout.addLayout(layout)


class KeyButton(QPushButton):
    """Keyboard control button with visual feedback."""

    def __init__(
        self,
        text: str,
        key_code: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self.key_code = key_code
        self.setFixedSize(42, 42)
        self._pressed = False
        self._update_style()

    def _update_style(self) -> None:
        if self._pressed:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {COLORS.accent};
                    color: {COLORS.background};
                    border: none;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 14px;
                }}
            """
            )
        else:
            self.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {COLORS.surface_elevated};
                    color: {COLORS.text_primary};
                    border: 1px solid {COLORS.border};
                    border-radius: 8px;
                    font-weight: 600;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS.border};
                    border-color: {COLORS.border_focus};
                }}
                QPushButton:disabled {{
                    background-color: {COLORS.surface};
                    color: {COLORS.text_muted};
                    border-color: {COLORS.surface_elevated};
                }}
            """
            )

    def set_pressed(self, pressed: bool) -> None:
        self._pressed = pressed
        self._update_style()


class VideoDisplay(QLabel):
    """
    Video/image display widget with aspect ratio preservation.

    Supports mouse click events for color sampling operations.

    Signals
    -------
    clicked : Signal(int, int)
        Emitted when display is clicked with frame coordinates (x, y).
    """

    clicked = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._placeholder_text = "No video source"
        self._current_frame_size = None
        self._click_enabled = False
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.setText(self._placeholder_text)
        self._current_frame_size = None
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {COLORS.background};
                border: 1px solid {COLORS.border};
                border-radius: 6px;
                color: {COLORS.text_muted};
                font-size: 11px;
            }}
        """
        )

    def set_placeholder(self, text: str) -> None:
        self._placeholder_text = text
        self._show_placeholder()

    def enable_click(self, enabled: bool = True) -> None:
        self._click_enabled = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def display_frame(self, frame: np.ndarray) -> None:
        if frame is None or frame.size == 0:
            self._show_placeholder()
            return

        # Restore normal style when displaying
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {COLORS.background};
                border: 1px solid {COLORS.border};
                border-radius: 6px;
            }}
        """
        )

        if len(frame.shape) == 2:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb_frame.shape
        self._current_frame_size = (w, h)
        bytes_per_line = ch * w
        display_size = self.size()
        # QImage wraps rgb_frame's buffer without copying; QPixmap.fromImage on the
        # next line deep-copies it, so keep them adjacent (and rgb_frame alive until
        # then) rather than paying for an extra per-frame QImage.copy().
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        scaled_pixmap = QPixmap.fromImage(q_img).scaled(
            display_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._scaled_pixmap_size = (scaled_pixmap.width(), scaled_pixmap.height())
        self.setPixmap(scaled_pixmap)

    def mousePressEvent(self, event) -> None:
        if not self._click_enabled or self._current_frame_size is None:
            return super().mousePressEvent(event)

        if event.button() == Qt.LeftButton:
            pixmap = self.pixmap()
            if pixmap is None:
                return

            widget_w, widget_h = self.width(), self.height()
            pixmap_w, pixmap_h = pixmap.width(), pixmap.height()
            frame_w, frame_h = self._current_frame_size

            offset_x = (widget_w - pixmap_w) // 2
            offset_y = (widget_h - pixmap_h) // 2

            click_x = event.position().x() - offset_x
            click_y = event.position().y() - offset_y

            if 0 <= click_x < pixmap_w and 0 <= click_y < pixmap_h:
                frame_x = int(click_x * frame_w / pixmap_w)
                frame_y = int(click_y * frame_h / pixmap_h)
                self.clicked.emit(frame_x, frame_y)

    def clear_display(self) -> None:
        self._current_frame_size = None
        self._show_placeholder()


class ImageViewer(QWidget):
    """Compact image viewer with info display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._display = VideoDisplay()
        self._info_label = QLabel()
        self._info_label.setProperty("secondary", True)
        self._info_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._display, 1)
        layout.addWidget(self._info_label)

    def display_frame(self, frame: np.ndarray, info: str = "") -> None:
        self._display.display_frame(frame)
        if frame is not None and frame.size > 0:
            h, w = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) > 2 else 1
            info_text = f"{w}×{h} | {channels}ch"
            if info:
                info_text += f" | {info}"
            self._info_label.setText(info_text)
        else:
            self._info_label.setText(info if info else "")

    def clear(self) -> None:
        self._display.clear_display()
        self._info_label.setText("")


class CompactFormRow(QWidget):
    """Horizontal form row with label and widget."""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(70)

        layout.addWidget(lbl)
        layout.addWidget(widget, 1)


class SectionHeader(QLabel):
    """Styled section header label."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS.accent};
                font-weight: 600;
                font-size: 11px;
                padding: 4px 0;
                border-bottom: 1px solid {COLORS.border};
                margin-bottom: 4px;
            }}
        """
        )


class DualVideoDisplay(QWidget):
    """
    Dual video display widget for RGB and depth side-by-side view.

    Signals
    -------
    rgb_clicked : Signal(int, int)
        Emitted when RGB display is clicked with frame coordinates.
    depth_clicked : Signal(int, int)
        Emitted when depth display is clicked with frame coordinates.
    """

    rgb_clicked = Signal(int, int)
    depth_clicked = Signal(int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._dual_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # RGB display container
        self._rgb_container = QWidget()
        rgb_layout = QVBoxLayout(self._rgb_container)
        rgb_layout.setContentsMargins(0, 0, 0, 0)
        rgb_layout.setSpacing(2)

        self._rgb_header = QLabel("RGB")
        self._rgb_header.setStyleSheet(
            f"color: {COLORS.text_secondary}; font-size: 10px; font-weight: 500;"
        )
        self._rgb_header.setAlignment(Qt.AlignCenter)

        self._rgb_display = VideoDisplay()
        self._rgb_display.clicked.connect(self.rgb_clicked.emit)

        rgb_layout.addWidget(self._rgb_header)
        rgb_layout.addWidget(self._rgb_display, 1)

        # Depth display container
        self._depth_container = QWidget()
        depth_layout = QVBoxLayout(self._depth_container)
        depth_layout.setContentsMargins(0, 0, 0, 0)
        depth_layout.setSpacing(2)

        self._depth_header = QLabel("Depth")
        self._depth_header.setStyleSheet(
            f"color: {COLORS.accent}; font-size: 10px; font-weight: 500;"
        )
        self._depth_header.setAlignment(Qt.AlignCenter)

        self._depth_display = VideoDisplay()
        self._depth_display.clicked.connect(self.depth_clicked.emit)

        depth_layout.addWidget(self._depth_header)
        depth_layout.addWidget(self._depth_display, 1)

        layout.addWidget(self._rgb_container, 1)
        layout.addWidget(self._depth_container, 1)

        # Initially hide depth and headers
        self._depth_container.setVisible(False)
        self._rgb_header.setVisible(False)

    def set_dual_mode(self, enabled: bool) -> None:
        """Enable or disable side-by-side dual display mode."""
        self._dual_mode = enabled
        self._depth_container.setVisible(enabled)
        self._rgb_header.setVisible(enabled)
        self._depth_header.setVisible(enabled)

    def display_rgb(self, frame: np.ndarray) -> None:
        """Display RGB frame."""
        self._rgb_display.display_frame(frame)

    def display_depth(self, frame: np.ndarray) -> None:
        """Display depth frame (colorized)."""
        if self._dual_mode:
            self._depth_display.display_frame(frame)

    def set_placeholder(self, text: str) -> None:
        """Set placeholder text for RGB display."""
        self._rgb_display.set_placeholder(text)
        self._depth_display.set_placeholder("No depth data")

    def clear_display(self) -> None:
        """Clear both displays."""
        self._rgb_display.clear_display()
        self._depth_display.clear_display()

    def enable_rgb_click(self, enabled: bool) -> None:
        """Enable click events on RGB display."""
        self._rgb_display.enable_click(enabled)

    def enable_depth_click(self, enabled: bool) -> None:
        """Enable click events on depth display."""
        self._depth_display.enable_click(enabled)

    @property
    def rgb_display(self) -> VideoDisplay:
        """Access underlying RGB VideoDisplay."""
        return self._rgb_display

    @property
    def depth_display(self) -> VideoDisplay:
        """Access underlying depth VideoDisplay."""
        return self._depth_display


class CameraConfigPanel(QWidget):
    """
    Dynamic camera configuration panel.

    Shows different configuration options based on selected camera type.
    Emits configChanged signal when any setting is modified.

    Signals
    -------
    configChanged : Signal()
        Emitted when any configuration value changes.
    """

    configChanged = Signal()

    CAMERA_TYPES = [
        "webcam",
        "realsense",
        "t265",
        "oakd",
        "ros",
        "ros_depth",
        "file",
        "c920",
        "imx219",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        self._emit_config_changed = lambda *_: self.configChanged.emit()
        super().__init__(parent)
        self._current_type = "webcam"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Camera type selector
        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        type_lbl = QLabel("Camera:")
        type_lbl.setProperty("secondary", True)
        type_lbl.setFixedWidth(55)

        self._type_combo = QComboBox()
        self._type_combo.addItems(self.CAMERA_TYPES)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_layout.addWidget(type_lbl)
        type_layout.addWidget(self._type_combo, 1)
        main_layout.addLayout(type_layout)

        # Stacked widget for different camera configs
        self._stack = QStackedWidget()
        self._config_pages: Dict[str, QWidget] = {}

        self._create_webcam_config()
        self._create_realsense_config()
        self._create_t265_config()
        self._create_oakd_config()
        self._create_ros_config()
        self._create_ros_depth_config()
        self._create_file_config()
        self._create_c920_config()
        self._create_imx219_config()

        main_layout.addWidget(self._stack)

    def _create_config_page(self, name: str) -> QWidget:
        """Create a config page and add to stack."""
        page = QWidget()
        page.setObjectName(name)
        self._config_pages[name] = page
        self._stack.addWidget(page)
        return page

    def _create_webcam_config(self) -> None:
        """Create webcam (OpenCV) configuration panel."""
        page = self._create_config_page("webcam")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Device index
        layout.addWidget(self._make_label("Device:"), 0, 0)
        self._webcam_device = QSpinBox()
        self._webcam_device.setRange(0, 10)
        self._webcam_device.setValue(0)
        self._webcam_device.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_device, 0, 1)

        # Resolution
        layout.addWidget(self._make_label("Width:"), 1, 0)
        self._webcam_width = QSpinBox()
        self._webcam_width.setRange(320, 1920)
        self._webcam_width.setValue(640)
        self._webcam_width.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_width, 1, 1)

        layout.addWidget(self._make_label("Height:"), 2, 0)
        self._webcam_height = QSpinBox()
        self._webcam_height.setRange(240, 1080)
        self._webcam_height.setValue(480)
        self._webcam_height.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_height, 2, 1)

        # FPS
        layout.addWidget(self._make_label("FPS:"), 3, 0)
        self._webcam_fps = QSpinBox()
        self._webcam_fps.setRange(1, 120)
        self._webcam_fps.setValue(30)
        self._webcam_fps.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_fps, 3, 1)

        # Autofocus
        self._webcam_autofocus = QCheckBox("Autofocus")
        self._webcam_autofocus.setChecked(True)
        self._webcam_autofocus.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_autofocus, 4, 0, 1, 2)

        # Threaded
        self._webcam_threaded = QCheckBox("Threaded capture")
        self._webcam_threaded.setChecked(True)
        self._webcam_threaded.setToolTip("Use background thread for capture")
        self._webcam_threaded.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._webcam_threaded, 5, 0, 1, 2)

    def _create_realsense_config(self) -> None:
        """Create RealSense configuration panel."""
        page = self._create_config_page("realsense")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Resolution
        layout.addWidget(self._make_label("Width:"), 0, 0)
        self._rs_width = QSpinBox()
        self._rs_width.setRange(320, 1920)
        self._rs_width.setValue(640)
        self._rs_width.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_width, 0, 1)

        layout.addWidget(self._make_label("Height:"), 1, 0)
        self._rs_height = QSpinBox()
        self._rs_height.setRange(240, 1080)
        self._rs_height.setValue(480)
        self._rs_height.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_height, 1, 1)

        # FPS
        layout.addWidget(self._make_label("FPS:"), 2, 0)
        self._rs_fps = QSpinBox()
        self._rs_fps.setRange(6, 90)
        self._rs_fps.setValue(30)
        self._rs_fps.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_fps, 2, 1)

        # Align to color
        self._rs_align = QCheckBox("Align depth to color")
        self._rs_align.setChecked(True)
        self._rs_align.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_align, 3, 0, 1, 2)

        # Use ROS topics
        self._rs_use_ros = QCheckBox("Use ROS topics")
        self._rs_use_ros.setToolTip("Subscribe to ROS topics instead of direct SDK")
        self._rs_use_ros.stateChanged.connect(self._on_rs_ros_toggled)
        layout.addWidget(self._rs_use_ros, 4, 0, 1, 2)

        # ROS topic fields (initially hidden)
        self._rs_color_topic_lbl = self._make_label("Color topic:")
        layout.addWidget(self._rs_color_topic_lbl, 5, 0)
        self._rs_color_topic = QLineEdit("/camera/color/image_raw")
        self._rs_color_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_color_topic, 5, 1)

        self._rs_depth_topic_lbl = self._make_label("Depth topic:")
        layout.addWidget(self._rs_depth_topic_lbl, 6, 0)
        self._rs_depth_topic = QLineEdit("/camera/depth/image_rect_raw")
        self._rs_depth_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_depth_topic, 6, 1)

        self._rs_compressed = QCheckBox("Color compressed")
        self._rs_compressed.setChecked(True)
        self._rs_compressed.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_compressed, 7, 0, 1, 2)

        self._rs_depth_compressed = QCheckBox("Depth compressed")
        self._rs_depth_compressed.setChecked(False)
        self._rs_depth_compressed.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._rs_depth_compressed, 8, 0, 1, 2)

        # Initially hide ROS topic fields
        self._toggle_rs_ros_fields(False)

    def _on_rs_ros_toggled(self) -> None:
        """Handle ROS topics toggle."""
        use_ros = self._rs_use_ros.isChecked()
        self._toggle_rs_ros_fields(use_ros)
        self.configChanged.emit()

    def _toggle_rs_ros_fields(self, visible: bool) -> None:
        """Show/hide ROS topic configuration fields."""
        self._rs_color_topic_lbl.setVisible(visible)
        self._rs_color_topic.setVisible(visible)
        self._rs_depth_topic_lbl.setVisible(visible)
        self._rs_depth_topic.setVisible(visible)
        self._rs_compressed.setVisible(visible)
        self._rs_depth_compressed.setVisible(visible)

    def _create_t265_config(self) -> None:
        """Create T265 tracking camera configuration panel."""
        page = self._create_config_page("t265")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        row = 0

        self._t265_enable_depth = QCheckBox("Enable stereo depth")
        self._t265_enable_depth.setChecked(True)
        self._t265_enable_depth.setToolTip("Compute depth from fisheye stereo pair (StereoSGBM)")
        self._t265_enable_depth.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_enable_depth, row, 0, 1, 2)
        row += 1

        self._t265_enable_pose = QCheckBox("Enable pose")
        self._t265_enable_pose.setChecked(True)
        self._t265_enable_pose.setToolTip("Capture 6DOF pose from T265 VIO")
        self._t265_enable_pose.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_enable_pose, row, 0, 1, 2)
        row += 1

        layout.addWidget(self._make_label("Stereo FOV:"), row, 0)
        self._t265_fov = QSpinBox()
        self._t265_fov.setRange(60, 120)
        self._t265_fov.setValue(90)
        self._t265_fov.setSuffix("°")
        self._t265_fov.setToolTip("Output FOV for rectified stereo depth")
        self._t265_fov.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_fov, row, 1)
        row += 1

        layout.addWidget(self._make_label("Stereo res:"), row, 0)
        self._t265_stereo_height = QSpinBox()
        self._t265_stereo_height.setRange(100, 600)
        self._t265_stereo_height.setValue(300)
        self._t265_stereo_height.setSuffix("px")
        self._t265_stereo_height.setToolTip("Stereo output height (width = height + max_disp)")
        self._t265_stereo_height.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_stereo_height, row, 1)
        row += 1

        layout.addWidget(self._make_label("Max depth:"), row, 0)
        self._t265_max_depth = QDoubleSpinBox()
        self._t265_max_depth.setRange(0.5, 10.0)
        self._t265_max_depth.setValue(3.0)
        self._t265_max_depth.setSingleStep(0.5)
        self._t265_max_depth.setSuffix("m")
        self._t265_max_depth.setToolTip("Clip depth beyond this range (reduces far-field noise)")
        self._t265_max_depth.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_max_depth, row, 1)
        row += 1

        layout.addWidget(self._make_label("Uniqueness:"), row, 0)
        self._t265_uniqueness = QSpinBox()
        self._t265_uniqueness.setRange(0, 30)
        self._t265_uniqueness.setValue(10)
        self._t265_uniqueness.setSuffix("%")
        self._t265_uniqueness.setToolTip(
            "StereoSGBM uniqueness ratio: reject matches where best cost "
            "is less than this % better than second-best. Higher = less noise, more holes."
        )
        self._t265_uniqueness.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_uniqueness, row, 1)
        row += 1

        layout.addWidget(self._make_label("Speckle:"), row, 0)
        self._t265_speckle_size = QSpinBox()
        self._t265_speckle_size.setRange(0, 500)
        self._t265_speckle_size.setValue(100)
        self._t265_speckle_size.setSuffix("px")
        self._t265_speckle_size.setToolTip(
            "StereoSGBM speckle filter: connected components smaller than this are removed. "
            "Higher = more aggressive noise removal."
        )
        self._t265_speckle_size.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_speckle_size, row, 1)
        row += 1

        layout.addWidget(self._make_label("Smoothness:"), row, 0)
        self._t265_smoothness = QSpinBox()
        self._t265_smoothness.setRange(3, 11)
        self._t265_smoothness.setValue(5)
        self._t265_smoothness.setToolTip(
            "StereoSGBM smoothness window: controls P1/P2 penalties. "
            "Higher = smoother depth, less detail. P1=8*3*w^2, P2=32*3*w^2."
        )
        self._t265_smoothness.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_smoothness, row, 1)
        row += 1

        layout.addWidget(self._make_label("Display:"), row, 0)
        self._t265_display_mode = QComboBox()
        self._t265_display_mode.addItems(
            ["Left Fisheye", "Right Fisheye", "Both Fisheye", "Rectified"]
        )
        self._t265_display_mode.setToolTip("Which T265 view to show in the RGB panel")
        self._t265_display_mode.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_display_mode, row, 1)
        row += 1

        self._t265_use_ros = QCheckBox("Use ROS topics")
        self._t265_use_ros.setToolTip(
            "Subscribe to realsense2_camera topics (use when node is already running)"
        )
        self._t265_use_ros.stateChanged.connect(self._on_t265_ros_toggled)
        layout.addWidget(self._t265_use_ros, row, 0, 1, 2)
        row += 1

        self._t265_fisheye1_lbl = self._make_label("Fisheye 1:")
        layout.addWidget(self._t265_fisheye1_lbl, row, 0)
        self._t265_fisheye1_topic = QLineEdit("/camera/fisheye1/image_raw")
        self._t265_fisheye1_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_fisheye1_topic, row, 1)
        row += 1

        self._t265_fisheye2_lbl = self._make_label("Fisheye 2:")
        layout.addWidget(self._t265_fisheye2_lbl, row, 0)
        self._t265_fisheye2_topic = QLineEdit("/camera/fisheye2/image_raw")
        self._t265_fisheye2_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_fisheye2_topic, row, 1)
        row += 1

        self._t265_pose_lbl = self._make_label("Pose topic:")
        layout.addWidget(self._t265_pose_lbl, row, 0)
        self._t265_pose_topic = QLineEdit("/camera/pose/sample")
        self._t265_pose_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._t265_pose_topic, row, 1)

        self._toggle_t265_ros_fields(False)

    def _on_t265_ros_toggled(self) -> None:
        use_ros = self._t265_use_ros.isChecked()
        self._toggle_t265_ros_fields(use_ros)
        self.configChanged.emit()

    def _toggle_t265_ros_fields(self, visible: bool) -> None:
        self._t265_fisheye1_lbl.setVisible(visible)
        self._t265_fisheye1_topic.setVisible(visible)
        self._t265_fisheye2_lbl.setVisible(visible)
        self._t265_fisheye2_topic.setVisible(visible)
        self._t265_pose_lbl.setVisible(visible)
        self._t265_pose_topic.setVisible(visible)

    def _create_oakd_config(self) -> None:
        """Create OAK-D configuration panel."""
        page = self._create_config_page("oakd")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Camera number
        layout.addWidget(self._make_label("Camera:"), 0, 0)
        self._oakd_cam = QComboBox()
        self._oakd_cam.addItems(["RGB (1)", "Left Mono (2)", "Right Mono (3)"])
        self._oakd_cam.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._oakd_cam, 0, 1)

        # Info label
        info = QLabel("Depth enabled in Depth Estimation section")
        info.setProperty("muted", True)
        info.setWordWrap(True)
        layout.addWidget(info, 1, 0, 1, 2)

    def _create_ros_config(self) -> None:
        """Create ROS camera configuration panel."""
        page = self._create_config_page("ros")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._make_label("Topic:"), 0, 0)
        self._ros_topic = QLineEdit("/camera/image_raw")
        self._ros_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_topic, 0, 1)

        self._ros_compressed = QCheckBox("Compressed topic")
        self._ros_compressed.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_compressed, 1, 0, 1, 2)

        layout.addWidget(self._make_label("QoS:"), 2, 0)
        self._ros_reliability = QComboBox()
        self._ros_reliability.addItems(["Best Effort", "Reliable"])
        self._ros_reliability.setToolTip("QoS reliability policy")
        self._ros_reliability.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_reliability, 2, 1)

        layout.addWidget(self._make_label("Durability:"), 3, 0)
        self._ros_durability = QComboBox()
        self._ros_durability.addItems(["Volatile", "Transient Local"])
        self._ros_durability.setToolTip("QoS durability policy")
        self._ros_durability.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_durability, 3, 1)

        layout.addWidget(self._make_label("History:"), 4, 0)
        self._ros_history_depth = QSpinBox()
        self._ros_history_depth.setRange(1, 100)
        self._ros_history_depth.setValue(1)
        self._ros_history_depth.setToolTip("QoS history depth")
        self._ros_history_depth.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_history_depth, 4, 1)

        layout.addWidget(self._make_label("Encoding:"), 5, 0)
        self._ros_encoding = QComboBox()
        self._ros_encoding.addItems(["bgr8", "rgb8", "mono8", "passthrough"])
        self._ros_encoding.setToolTip("Image encoding for cv_bridge conversion")
        self._ros_encoding.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_encoding, 5, 1)

    def _create_ros_depth_config(self) -> None:
        """Create ROS depth camera (RGBD) configuration panel."""
        page = self._create_config_page("ros_depth")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._make_label("Color:"), 0, 0)
        self._ros_depth_color_topic = QLineEdit("/front_camera/image")
        self._ros_depth_color_topic.setToolTip("ROS topic for RGB image")
        self._ros_depth_color_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_depth_color_topic, 0, 1)

        self._ros_depth_color_compressed = QCheckBox("Color compressed")
        self._ros_depth_color_compressed.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_depth_color_compressed, 1, 0, 1, 2)

        layout.addWidget(self._make_label("Depth:"), 2, 0)
        self._ros_depth_depth_topic = QLineEdit("/front_camera/depth_image")
        self._ros_depth_depth_topic.setToolTip("ROS topic for depth image")
        self._ros_depth_depth_topic.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_depth_depth_topic, 2, 1)

        self._ros_depth_depth_compressed = QCheckBox("Depth compressed")
        self._ros_depth_depth_compressed.stateChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_depth_depth_compressed, 3, 0, 1, 2)

        layout.addWidget(self._make_label("QoS:"), 4, 0)
        self._ros_depth_reliability = QComboBox()
        self._ros_depth_reliability.addItems(["Best Effort", "Reliable"])
        self._ros_depth_reliability.setToolTip("QoS reliability policy")
        self._ros_depth_reliability.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._ros_depth_reliability, 4, 1)

    def _create_file_config(self) -> None:
        """Create file image configuration panel."""
        page = self._create_config_page("file")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Path
        layout.addWidget(self._make_label("Path:"), 0, 0)
        self._file_path = QLineEdit()
        self._file_path.setPlaceholderText("/path/to/image.jpg")
        self._file_path.textChanged.connect(self._emit_config_changed)
        layout.addWidget(self._file_path, 0, 1)

    def _create_c920_config(self) -> None:
        """Create Logitech C920 configuration panel."""
        page = self._create_config_page("c920")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Profile
        layout.addWidget(self._make_label("Profile:"), 0, 0)
        self._c920_profile = QComboBox()
        self._c920_profile.addItems(["640×480", "1280×720", "1920×1080"])
        self._c920_profile.setCurrentIndex(1)
        self._c920_profile.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._c920_profile, 0, 1)

        # Fallback device
        layout.addWidget(self._make_label("Fallback:"), 1, 0)
        self._c920_fallback = QSpinBox()
        self._c920_fallback.setRange(0, 10)
        self._c920_fallback.setValue(0)
        self._c920_fallback.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._c920_fallback, 1, 1)

    def _create_imx219_config(self) -> None:
        """Create IMX219 (Jetson) configuration panel."""
        page = self._create_config_page("imx219")
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        # Sensor ID
        layout.addWidget(self._make_label("Sensor ID:"), 0, 0)
        self._imx_sensor = QSpinBox()
        self._imx_sensor.setRange(0, 3)
        self._imx_sensor.setValue(0)
        self._imx_sensor.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._imx_sensor, 0, 1)

        # Resolution
        layout.addWidget(self._make_label("Width:"), 1, 0)
        self._imx_width = QSpinBox()
        self._imx_width.setRange(640, 3280)
        self._imx_width.setValue(1920)
        self._imx_width.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._imx_width, 1, 1)

        layout.addWidget(self._make_label("Height:"), 2, 0)
        self._imx_height = QSpinBox()
        self._imx_height.setRange(480, 2464)
        self._imx_height.setValue(1080)
        self._imx_height.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._imx_height, 2, 1)

        # FPS
        layout.addWidget(self._make_label("FPS:"), 3, 0)
        self._imx_fps = QSpinBox()
        self._imx_fps.setRange(1, 60)
        self._imx_fps.setValue(30)
        self._imx_fps.valueChanged.connect(self._emit_config_changed)
        layout.addWidget(self._imx_fps, 3, 1)

        # Flip
        layout.addWidget(self._make_label("Flip:"), 4, 0)
        self._imx_flip = QComboBox()
        self._imx_flip.addItems(["None (0)", "Horizontal (1)", "Rotate 180 (2)"])
        self._imx_flip.currentIndexChanged.connect(self._emit_config_changed)
        layout.addWidget(self._imx_flip, 4, 1)

    def _make_label(self, text: str) -> QLabel:
        """Create a styled label for config fields."""
        lbl = QLabel(text)
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(70)
        return lbl

    def _on_type_changed(self, camera_type: str) -> None:
        """Handle camera type selection change."""
        self._current_type = camera_type
        if camera_type in self._config_pages:
            self._stack.setCurrentWidget(self._config_pages[camera_type])
        self.configChanged.emit()

    @property
    def camera_type(self) -> str:
        """Current selected camera type."""
        return self._current_type

    def set_camera_type(self, camera_type: str) -> None:
        """Set the camera type programmatically."""
        idx = self._type_combo.findText(camera_type)
        if idx >= 0:
            self._type_combo.setCurrentIndex(idx)

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration as dictionary.

        Returns
        -------
        Dict[str, Any]
            Configuration dictionary with camera type and settings.
        """
        config = {"type": self._current_type}

        if self._current_type == "webcam":
            config.update(
                {
                    "device_index": self._webcam_device.value(),
                    "width": self._webcam_width.value(),
                    "height": self._webcam_height.value(),
                    "fps": self._webcam_fps.value(),
                    "autofocus": self._webcam_autofocus.isChecked(),
                    "threaded": self._webcam_threaded.isChecked(),
                }
            )
        elif self._current_type == "realsense":
            config.update(
                {
                    "width": self._rs_width.value(),
                    "height": self._rs_height.value(),
                    "fps": self._rs_fps.value(),
                    "align_to_color": self._rs_align.isChecked(),
                    "use_ros_topics": self._rs_use_ros.isChecked(),
                    "color_topic": self._rs_color_topic.text(),
                    "depth_topic": self._rs_depth_topic.text(),
                    "color_compressed": self._rs_compressed.isChecked(),
                    "depth_compressed": self._rs_depth_compressed.isChecked(),
                }
            )
        elif self._current_type == "t265":
            config.update(
                {
                    "enable_depth": self._t265_enable_depth.isChecked(),
                    "enable_pose": self._t265_enable_pose.isChecked(),
                    "stereo_fov_deg": self._t265_fov.value(),
                    "stereo_height_px": self._t265_stereo_height.value(),
                    "max_depth_m": self._t265_max_depth.value(),
                    "uniqueness_ratio": self._t265_uniqueness.value(),
                    "speckle_window_size": self._t265_speckle_size.value(),
                    "smoothness_window": self._t265_smoothness.value(),
                    "display_mode": self._t265_display_mode.currentText(),
                    "use_ros_topics": self._t265_use_ros.isChecked(),
                    "fisheye1_topic": self._t265_fisheye1_topic.text(),
                    "fisheye2_topic": self._t265_fisheye2_topic.text(),
                    "pose_topic": self._t265_pose_topic.text(),
                }
            )
        elif self._current_type == "oakd":
            config.update(
                {
                    "cam_num": self._oakd_cam.currentIndex() + 1,
                }
            )
        elif self._current_type == "ros":
            config.update(
                {
                    "topic": self._ros_topic.text(),
                    "compressed": self._ros_compressed.isChecked(),
                    "reliability": self._ros_reliability.currentText(),
                    "durability": self._ros_durability.currentText(),
                    "history_depth": self._ros_history_depth.value(),
                    "encoding": self._ros_encoding.currentText(),
                }
            )
        elif self._current_type == "ros_depth":
            config.update(
                {
                    "topic": self._ros_depth_color_topic.text(),
                    "compressed": self._ros_depth_color_compressed.isChecked(),
                    "depth_topic": self._ros_depth_depth_topic.text(),
                    "depth_compressed": self._ros_depth_depth_compressed.isChecked(),
                    "reliability": self._ros_depth_reliability.currentText(),
                }
            )
        elif self._current_type == "file":
            config.update(
                {
                    "path": self._file_path.text(),
                }
            )
        elif self._current_type == "c920":
            config.update(
                {
                    "profile": self._c920_profile.currentIndex(),
                    "fallback_device_index": self._c920_fallback.value(),
                }
            )
        elif self._current_type == "imx219":
            config.update(
                {
                    "sensor_id": self._imx_sensor.value(),
                    "width": self._imx_width.value(),
                    "height": self._imx_height.value(),
                    "fps": self._imx_fps.value(),
                    "flip": self._imx_flip.currentIndex(),
                }
            )

        return config

    def setEnabled(self, enabled: bool) -> None:
        """Enable or disable all config controls."""
        self._type_combo.setEnabled(enabled)
        for page in self._config_pages.values():
            page.setEnabled(enabled)
