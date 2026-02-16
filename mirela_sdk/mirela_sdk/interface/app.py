#!/usr/bin/env python3
import pathlib
import signal
import sys

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mirela_sdk.interface.ros_executor import ROSExecutor
from mirela_sdk.interface.tabs import ControlTab, ROSTab, VisionTab
from mirela_sdk.interface.theme import COLORS, get_stylesheet


class MirelaApp(QMainWindow):
    """
    Mirela SDK main application window.

    Professional drone control and vision tools interface
    for robotics competition teams.
    """

    def __init__(self) -> None:
        super().__init__()
        self._ros_executor = ROSExecutor(self)
        self._images_dir = pathlib.Path(__file__).parent / "images"

        self._setup_window()
        self._setup_ui()
        self._setup_statusbar()
        self._connect_signals()
        self._start_ros()

    def _setup_window(self) -> None:
        self.setWindowTitle("Mirela SDK")
        self.setMinimumSize(1100, 700)

        logo_path = self._images_dir / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        self.setStyleSheet(get_stylesheet())

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = self._create_header()
        layout.addWidget(header)

        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(True)

        self._control_tab = ControlTab()
        self._vision_tab = VisionTab()
        self._ros_tab = ROSTab()

        self._tab_widget.addTab(self._control_tab, "  Control  ")
        self._tab_widget.addTab(self._vision_tab, "  Vision  ")
        self._tab_widget.addTab(self._ros_tab, "  ROS  ")

        layout.addWidget(self._tab_widget, 1)

    def _create_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS.surface};
                border-bottom: 1px solid {COLORS.border};
            }}
        """
        )
        header.setFixedHeight(48)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 6, 12, 6)

        # Logo and title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(10)

        logo_path = self._images_dir / "logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
            logo_layout.addWidget(logo_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("MIRELA SDK")
        title.setStyleSheet(
            f"""
            font-size: 14px;
            font-weight: 700;
            color: {COLORS.text_primary};
            letter-spacing: 1px;
        """
        )

        subtitle = QLabel("Drone Control & Vision Tools")
        subtitle.setStyleSheet(
            f"""
            font-size: 10px;
            color: {COLORS.text_muted};
        """
        )

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        logo_layout.addLayout(title_layout)

        # ROS status
        self._ros_status_label = QLabel("● ROS2: Initializing")
        self._ros_status_label.setStyleSheet(
            f"""
            color: {COLORS.warning};
            font-size: 11px;
            font-weight: 500;
        """
        )

        layout.addLayout(logo_layout)
        layout.addStretch()
        layout.addWidget(self._ros_status_label)

        return header

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_message = QLabel("Ready")
        self._statusbar.addWidget(self._status_message)

        version_label = QLabel("Mirela SDK v2.0")
        version_label.setStyleSheet(f"color: {COLORS.text_muted};")
        self._statusbar.addPermanentWidget(version_label)

    def _connect_signals(self) -> None:
        self._ros_executor.status_changed.connect(self._on_ros_status_changed)
        self._ros_executor.error_occurred.connect(self._on_ros_error)

    def _start_ros(self) -> None:
        success = self._ros_executor.start("mirela_gui")
        if success and self._ros_executor.node:
            self._control_tab.set_node(self._ros_executor.node)
            self._vision_tab.set_node(self._ros_executor.node)
            self._ros_tab.set_node(self._ros_executor.node)

    @Slot(bool)
    def _on_ros_status_changed(self, running: bool) -> None:
        if running:
            self._ros_status_label.setText("● ROS2: Connected")
            self._ros_status_label.setStyleSheet(
                f"""
                color: {COLORS.success};
                font-size: 11px;
                font-weight: 500;
            """
            )
            self._status_message.setText("ROS2 node active")
        else:
            self._ros_status_label.setText("● ROS2: Disconnected")
            self._ros_status_label.setStyleSheet(
                f"""
                color: {COLORS.error};
                font-size: 11px;
                font-weight: 500;
            """
            )
            self._status_message.setText("ROS2 node inactive")

    @Slot(str)
    def _on_ros_error(self, error: str) -> None:
        self._status_message.setText(f"Error: {error}")

    def closeEvent(self, event) -> None:
        """Handle window close event with proper cleanup."""
        self._cleanup()
        event.accept()

    def _cleanup(self) -> None:
        """Perform cleanup of all resources."""
        self._control_tab.cleanup()
        self._vision_tab.cleanup()
        self._ros_tab.cleanup()
        self._ros_executor.shutdown()


def main() -> None:
    """Main entry point for the Mirela SDK GUI application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("JetBrains Mono", 10)
    if not font.exactMatch():
        font = QFont("SF Mono", 10)
        if not font.exactMatch():
            font = QFont("Consolas", 10)
            if not font.exactMatch():
                font = QFont("monospace", 10)
    app.setFont(font)

    window = MirelaApp()
    window.show()

    def _handle_sigint(signum, frame):
        """Handle SIGINT (Ctrl+C) by closing window and quitting app."""
        window.close()
        app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        window._cleanup()
        sys.exit(0)


if __name__ == "__main__":
    main()
