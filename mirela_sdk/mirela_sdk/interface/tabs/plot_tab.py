import json
import time
from collections import deque
from typing import Any, Callable, Dict, List, Optional

import pyqtgraph as pg
from pyqtgraph import PlotDataItem, PlotWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)

from mirela_sdk.interface.theme import COLORS

QOS_PROFILES = {
    "Default (Reliable)": QoSProfile(
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.VOLATILE,
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=10,
    ),
    "Sensor Data (Best Effort)": qos_profile_sensor_data,
    "Best Effort": QoSProfile(
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE,
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=10,
    ),
}


class PlotData:
    """Container for plot data with time series."""

    def __init__(self, max_points: int = 10000):
        self.max_points = max_points
        self.times = deque(maxlen=max_points)
        self.values = deque(maxlen=max_points)
        self.start_time = time.time()

    def add_point(self, value: float) -> None:
        """Add a data point with current relative time."""
        elapsed = time.time() - self.start_time
        self.times.append(elapsed)
        self.values.append(value)

    def clear(self) -> None:
        """Clear all data and reset start time."""
        self.times.clear()
        self.values.clear()
        self.start_time = time.time()

    def get_arrays(self) -> tuple:
        """Get numpy arrays for plotting."""
        if len(self.times) == 0:
            return [], []
        return list(self.times), list(self.values)


class FieldExtractor:
    """Extract numeric fields from ROS2 messages."""

    @staticmethod
    def extract_value(msg: Any, field_path: str) -> Optional[float]:
        """
        Extract numeric value from message using dot notation.

        Examples:
            "data" -> msg.data
            "pose.position.x" -> msg.pose.position.x
            "linear.x" -> msg.linear.x
        """
        try:
            parts = field_path.split(".")
            value = msg
            for part in parts:
                value = getattr(value, part, None)
                if value is None:
                    return None
            return float(value)
        except (AttributeError, ValueError, TypeError):
            return None

    @staticmethod
    def get_numeric_fields(msg: Any, prefix: str = "") -> List[str]:
        """
        Recursively find all numeric fields in a message.

        Returns list of field paths (e.g., ["data", "pose.position.x"]).
        """
        fields = []
        if hasattr(msg, "__slots__"):
            for slot in msg.__slots__:
                field_path = f"{prefix}.{slot}" if prefix else slot
                value = getattr(msg, slot, None)
                if value is None:
                    continue

                if isinstance(value, (int, float)):
                    fields.append(field_path)
                elif hasattr(value, "__slots__"):
                    fields.extend(FieldExtractor.get_numeric_fields(value, field_path))
                elif isinstance(value, (list, tuple)) and len(value) > 0:
                    if isinstance(value[0], (int, float)):
                        for i in range(len(value)):
                            fields.append(f"{field_path}[{i}]")
        return fields


class PlotTab(QWidget):
    """Real-time ROS2 topic plotting with pyqtgraph."""

    def __init__(self, node: Optional[Node] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._node = node
        self._subscriptions: Dict[str, Any] = {}
        self._plot_data: Dict[str, PlotData] = {}
        self._plot_items: Dict[str, PlotDataItem] = {}
        self._field_extractors: Dict[str, Callable] = {}
        self._available_topics: Dict[str, str] = {}
        self._is_paused = False
        self._time_window = 30.0

        pg.setConfigOptions(antialias=True)
        pg.setConfigOption("background", COLORS.background)
        pg.setConfigOption("foreground", COLORS.text_primary)

        self._setup_ui()
        self._setup_timers()
        self._connect_signals()

    def set_node(self, node: Node) -> None:
        """Set ROS2 node for topic subscription."""
        self._node = node
        self._refresh_topics()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        controls = self._create_controls_panel()
        layout.addWidget(controls)

        splitter = QSplitter(Qt.Horizontal)
        left_panel = self._create_topic_panel()
        right_panel = self._create_plot_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter, 1)

    def _create_controls_panel(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        time_window_layout = QHBoxLayout()
        time_window_layout.addWidget(QLabel("Time Window (s):"))
        self._time_window_spin = QDoubleSpinBox()
        self._time_window_spin.setRange(1.0, 300.0)
        self._time_window_spin.setValue(30.0)
        self._time_window_spin.setSuffix(" s")
        self._time_window_spin.setDecimals(1)
        time_window_layout.addWidget(self._time_window_spin)

        max_points_layout = QHBoxLayout()
        max_points_layout.addWidget(QLabel("Max Points:"))
        self._max_points_spin = QSpinBox()
        self._max_points_spin.setRange(100, 100000)
        self._max_points_spin.setValue(10000)
        max_points_layout.addWidget(self._max_points_spin)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setCheckable(True)

        self._clear_btn = QPushButton("Clear All")
        self._export_btn = QPushButton("Export Data")

        layout.addLayout(time_window_layout)
        layout.addLayout(max_points_layout)
        layout.addStretch()
        layout.addWidget(self._pause_btn)
        layout.addWidget(self._clear_btn)
        layout.addWidget(self._export_btn)

        return widget

    def _create_topic_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        topic_group = QGroupBox("Add Plot")
        topic_layout = QVBoxLayout(topic_group)

        topic_row = QHBoxLayout()
        topic_row.addWidget(QLabel("Topic:"))
        self._topic_combo = QComboBox()
        self._topic_combo.setEditable(True)
        self._topic_combo.setMinimumWidth(200)
        self._refresh_topics_btn = QPushButton("Refresh")
        topic_row.addWidget(self._topic_combo, 1)
        topic_row.addWidget(self._refresh_topics_btn)
        topic_layout.addLayout(topic_row)

        field_row = QHBoxLayout()
        field_row.addWidget(QLabel("Field:"))
        self._field_combo = QComboBox()
        self._field_combo.setEditable(True)
        self._load_fields_btn = QPushButton("Load Fields")
        field_row.addWidget(self._field_combo, 1)
        field_row.addWidget(self._load_fields_btn)
        topic_layout.addLayout(field_row)

        qos_row = QHBoxLayout()
        qos_row.addWidget(QLabel("QoS:"))
        self._qos_combo = QComboBox()
        self._qos_combo.addItems(list(QOS_PROFILES.keys()))
        self._qos_combo.setCurrentText("Sensor Data (Best Effort)")
        qos_row.addWidget(self._qos_combo, 1)
        topic_layout.addLayout(qos_row)

        self._add_plot_btn = QPushButton("Add Plot")
        topic_layout.addWidget(self._add_plot_btn)

        layout.addWidget(topic_group)

        plots_group = QGroupBox("Active Plots")
        plots_layout = QVBoxLayout(plots_group)

        self._plots_tree = QTreeWidget()
        self._plots_tree.setHeaderLabels(["Plot", "Topic", "Field", ""])
        self._plots_tree.setRootIsDecorated(False)
        self._plots_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._plots_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._plots_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._plots_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        plots_layout.addWidget(self._plots_tree)

        layout.addWidget(plots_group, 1)

        return widget

    def _create_plot_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot_widget = PlotWidget()
        self._plot_widget.setLabel("left", "Value")
        self._plot_widget.setLabel("bottom", "Time (s)")
        self._plot_widget.setTitle("Real-time Topic Data")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.setBackground(COLORS.background)

        pen_colors = [
            COLORS.accent,
            COLORS.info,
            COLORS.success,
            COLORS.warning,
            COLORS.error,
            "#FF6B9D",
            "#C44569",
            "#6C5CE7",
        ]

        self._color_index = 0
        self._color_palette = pen_colors

        layout.addWidget(self._plot_widget)

        return widget

    def _setup_timers(self) -> None:
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_plots)
        self._update_timer.start(50)

        self._topic_refresh_timer = QTimer()
        self._topic_refresh_timer.timeout.connect(self._refresh_topics)
        self._topic_refresh_timer.start(5000)

    def _connect_signals(self) -> None:
        self._refresh_topics_btn.clicked.connect(self._refresh_topics)
        self._load_fields_btn.clicked.connect(self._load_fields)
        self._add_plot_btn.clicked.connect(self._add_plot)
        self._pause_btn.toggled.connect(self._on_pause_toggled)
        self._clear_btn.clicked.connect(self._clear_all_plots)
        self._export_btn.clicked.connect(self._export_data)
        self._time_window_spin.valueChanged.connect(self._on_time_window_changed)
        self._topic_combo.currentTextChanged.connect(self._on_topic_changed)
        self._plots_tree.itemDoubleClicked.connect(self._on_plot_item_double_clicked)

    def _refresh_topics(self) -> None:
        """Refresh list of available ROS2 topics."""
        if not self._node:
            return

        try:
            topic_names_and_types = self._node.get_topic_names_and_types()
            self._available_topics = {name: types[0] for name, types in topic_names_and_types}

            current_text = self._topic_combo.currentText()
            self._topic_combo.clear()
            self._topic_combo.addItems(sorted(self._available_topics.keys()))

            if current_text in self._available_topics:
                self._topic_combo.setCurrentText(current_text)
        except Exception as e:
            if self._node:
                self._node.get_logger().warn(f"Failed to refresh topics: {e}")

    def _on_topic_changed(self, topic: str) -> None:
        """Load fields when topic selection changes."""
        if topic in self._available_topics:
            self._load_fields()

    def _load_fields(self) -> None:
        """Load numeric fields from selected topic."""
        topic = self._topic_combo.currentText()
        if not topic or topic not in self._available_topics:
            return

        try:
            msg_type_str = self._available_topics[topic]
            msg_class = self._node.get_msg_class(msg_type_str)

            if msg_class:
                sample_msg = msg_class()
                fields = FieldExtractor.get_numeric_fields(sample_msg)

                self._field_combo.clear()
                if fields:
                    self._field_combo.addItems(fields)
                    self._field_combo.setCurrentIndex(0)
                else:
                    self._field_combo.addItem("(No numeric fields found)")
        except Exception as e:
            if self._node:
                self._node.get_logger().warn(f"Failed to load fields: {e}")

    def _add_plot(self) -> None:
        """Add a new plot for the selected topic and field."""
        topic = self._topic_combo.currentText()
        field = self._field_combo.currentText()

        if not topic or not field or field == "(No numeric fields found)":
            return

        plot_id = f"{topic}::{field}"

        if plot_id in self._plot_data:
            if self._node:
                self._node.get_logger().warn(f"Plot already exists: {plot_id}")
            return

        if not self._node:
            return

        try:
            msg_type_str = self._available_topics.get(topic)
            if not msg_type_str:
                return

            msg_class = self._node.get_msg_class(msg_type_str)
            if not msg_class:
                return

            qos_profile = QOS_PROFILES.get(
                self._qos_combo.currentText(), QOS_PROFILES["Sensor Data (Best Effort)"]
            )

            def callback(msg):
                if not self._is_paused:
                    value = FieldExtractor.extract_value(msg, field)
                    if value is not None and plot_id in self._plot_data:
                        self._plot_data[plot_id].add_point(value)

            subscription = self._node.create_subscription(msg_class, topic, callback, qos_profile)

            self._subscriptions[plot_id] = subscription
            self._plot_data[plot_id] = PlotData(max_points=self._max_points_spin.value())

            color = self._color_palette[self._color_index % len(self._color_palette)]
            self._color_index += 1

            pen = pg.mkPen(color, width=2)
            plot_item = self._plot_widget.plot([], [], pen=pen, name=plot_id)
            self._plot_items[plot_id] = plot_item

            item = QTreeWidgetItem(self._plots_tree)
            item.setText(0, plot_id)
            item.setText(1, topic)
            item.setText(2, field)
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda: self._remove_plot(plot_id))
            self._plots_tree.setItemWidget(item, 3, remove_btn)

            if self._node:
                self._node.get_logger().info(f"Added plot: {plot_id}")

        except Exception as e:
            if self._node:
                self._node.get_logger().error(f"Failed to add plot: {e}")

    def _remove_plot(self, plot_id: str) -> None:
        """Remove a plot and its subscription."""
        if plot_id in self._subscriptions:
            self._node.destroy_subscription(self._subscriptions[plot_id])
            del self._subscriptions[plot_id]

        if plot_id in self._plot_data:
            del self._plot_data[plot_id]

        if plot_id in self._plot_items:
            self._plot_widget.removeItem(self._plot_items[plot_id])
            del self._plot_items[plot_id]

        for i in range(self._plots_tree.topLevelItemCount()):
            item = self._plots_tree.topLevelItem(i)
            if item and item.text(0) == plot_id:
                self._plots_tree.takeTopLevelItem(i)
                break

        if self._node:
            self._node.get_logger().info(f"Removed plot: {plot_id}")

    def _update_plots(self) -> None:
        """Update all plot curves with latest data."""
        if not self._plot_items:
            return

        time_window = self._time_window
        min_time = float("inf")
        max_time = float("-inf")

        for plot_id, plot_item in self._plot_items.items():
            if plot_id not in self._plot_data:
                continue

            data = self._plot_data[plot_id]
            times, values = data.get_arrays()

            if len(times) == 0:
                continue

            if time_window > 0 and len(times) > 0:
                current_relative_time = time.time() - data.start_time
                cutoff_time = current_relative_time - time_window
                filtered_times = [t for t in times if t >= cutoff_time]
                if len(filtered_times) < len(values):
                    filtered_values = list(values)[-len(filtered_times) :]
                else:
                    filtered_values = list(values)
                times = filtered_times
                values = filtered_values

            if len(times) > 0:
                plot_item.setData(times, values)
                min_time = min(min_time, min(times))
                max_time = max(max_time, max(times))

        if min_time != float("inf") and max_time != float("-inf"):
            self._plot_widget.setXRange(min_time, max_time, padding=0.05)

    def _on_pause_toggled(self, paused: bool) -> None:
        """Handle pause button toggle."""
        self._is_paused = paused
        self._pause_btn.setText("Resume" if paused else "Pause")

    def _clear_all_plots(self) -> None:
        """Clear all plot data."""
        for plot_data in self._plot_data.values():
            plot_data.clear()

        if self._node:
            self._node.get_logger().info("Cleared all plot data")

    def _on_time_window_changed(self, value: float) -> None:
        """Handle time window change."""
        self._time_window = value

    def _on_plot_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click on plot item (focus plot)."""
        plot_id = item.text(0)
        if plot_id in self._plot_items:
            times, values = self._plot_data[plot_id].get_arrays()
            if len(times) > 0:
                self._plot_widget.setXRange(min(times), max(times), padding=0.1)
                self._plot_widget.setYRange(min(values), max(values), padding=0.1)

    def _export_data(self) -> None:
        """Export all plot data to JSON file."""
        if not self._plot_data:
            QMessageBox.warning(self, "Export", "No data to export")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Data", "", "JSON Files (*.json)"
        )

        if not filename:
            return

        try:
            export_data = {}
            for plot_id, plot_data in self._plot_data.items():
                times, values = plot_data.get_arrays()
                export_data[plot_id] = {
                    "times": list(times),
                    "values": list(values),
                }

            with open(filename, "w") as f:
                json.dump(export_data, f, indent=2)

            QMessageBox.information(self, "Export", f"Data exported to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def cleanup(self) -> None:
        """Cleanup all subscriptions and resources."""
        for plot_id in list(self._subscriptions.keys()):
            self._remove_plot(plot_id)

        if self._update_timer:
            self._update_timer.stop()
        if self._topic_refresh_timer:
            self._topic_refresh_timer.stop()
