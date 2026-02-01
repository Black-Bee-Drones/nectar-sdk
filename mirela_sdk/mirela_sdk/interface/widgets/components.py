from typing import Optional
import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap

from mirela_sdk.interface.theme import COLORS


class Card(QFrame):
    """Elevated card container with rounded corners."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{
                background-color: {COLORS.surface};
                border: 1px solid {COLORS.border};
                border-radius: 8px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)


class StatusIndicator(QWidget):
    """Circular status indicator with label."""

    def __init__(
        self,
        label: str = "",
        status: str = "inactive",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._indicator = QLabel()
        self._indicator.setFixedSize(12, 12)
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
        self._indicator.setStyleSheet(f"""
            background-color: {color};
            border-radius: 6px;
        """)

    def set_label(self, label: str) -> None:
        self._label.setText(label)


class LabeledSlider(QWidget):
    """Vertical slider with label and value display."""

    valueChanged = Signal(float)

    def __init__(
        self,
        label: str,
        min_val: float = 0.0,
        max_val: float = 1.0,
        default: float = 0.0,
        decimals: int = 2,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min_val = min_val
        self._max_val = max_val
        self._decimals = decimals
        self._scale = 10 ** decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)

        self._label = QLabel(label)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setProperty("secondary", True)

        self._value_label = QLabel(f"{default:.{decimals}f}")
        self._value_label.setAlignment(Qt.AlignCenter)
        self._value_label.setStyleSheet(f"color: {COLORS.accent}; font-weight: bold;")

        self._slider = QSlider(Qt.Vertical)
        self._slider.setMinimum(int(min_val * self._scale))
        self._slider.setMaximum(int(max_val * self._scale))
        self._slider.setValue(int(default * self._scale))
        self._slider.setMinimumHeight(100)
        self._slider.valueChanged.connect(self._on_value_changed)

        layout.addWidget(self._label)
        layout.addWidget(self._slider, 1, Qt.AlignHCenter)
        layout.addWidget(self._value_label)

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
    """Collapsible section with toggle button."""

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

        arrow = "▶" if collapsed else "▼"
        self._toggle = QPushButton(f"{arrow} {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(not collapsed)
        self._toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.surface_elevated};
                color: {COLORS.text_primary};
                border: none;
                padding: 10px 16px;
                text-align: left;
                font-weight: 600;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.border};
            }}
        """)
        self._toggle.clicked.connect(self._on_toggle)

        self._content = QFrame()
        self._content.setStyleSheet("background-color: transparent;")
        self._content.setVisible(not collapsed)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(8)

        main_layout.addWidget(self._toggle)
        main_layout.addWidget(self._content)

    def _on_toggle(self) -> None:
        self._collapsed = not self._toggle.isChecked()
        self._content.setVisible(not self._collapsed)
        arrow = "▶" if self._collapsed else "▼"
        self._toggle.setText(f"{arrow} {self._title}")

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
        self.setFixedSize(48, 48)
        self._pressed = False
        self._update_style()

    def _update_style(self) -> None:
        if self._pressed:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS.accent};
                    color: {COLORS.background};
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS.surface_elevated};
                    color: {COLORS.text_primary};
                    border: 1px solid {COLORS.border};
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS.border};
                }}
                QPushButton:disabled {{
                    background-color: {COLORS.surface};
                    color: {COLORS.text_muted};
                }}
            """)

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
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.background};
                border: 2px solid {COLORS.border};
                border-radius: 8px;
            }}
        """)
        self._placeholder_text = "No video source"
        self._current_frame_size = None
        self._click_enabled = False
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self.setText(self._placeholder_text)
        self._current_frame_size = None
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.background};
                border: 2px solid {COLORS.border};
                border-radius: 8px;
                color: {COLORS.text_muted};
            }}
        """)

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

        if len(frame.shape) == 2:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
        else:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb_frame.shape
        self._current_frame_size = (w, h)
        bytes_per_line = ch * w
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

        display_size = self.size()
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
    """Image viewer with zoom and info display."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

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
