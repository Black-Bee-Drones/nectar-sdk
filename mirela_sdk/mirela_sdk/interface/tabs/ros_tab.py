from typing import Optional, Dict, Any, List, Callable
from collections import deque
import time
import json
import yaml
import csv
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QPlainTextEdit,
    QLineEdit,
    QSplitter,
    QSpinBox,
    QDoubleSpinBox,
    QHeaderView,
    QStackedWidget,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QTextCursor

import pyqtgraph as pg
from pyqtgraph import PlotWidget, PlotDataItem

from rclpy.node import Node
from rclpy.qos import (
    QoSProfile,
    QoSReliabilityPolicy,
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    qos_profile_sensor_data,
    qos_profile_system_default,
)

from mirela_sdk.interface.theme import COLORS
from mirela_sdk.interface.widgets import ParameterReconfigureWidget
from mirela_sdk.interface.widgets.message_editor import MessageFieldEditor


QOS_PROFILES = {
    "Default (Reliable)": QoSProfile(
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.VOLATILE,
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=10,
    ),
    "Sensor Data (Best Effort)": qos_profile_sensor_data,
    "System Default": qos_profile_system_default,
    "Reliable + Transient Local": QoSProfile(
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=10,
    ),
    "Best Effort": QoSProfile(
        reliability=QoSReliabilityPolicy.BEST_EFFORT,
        durability=QoSDurabilityPolicy.VOLATILE,
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=10,
    ),
}


class ROSTab(QWidget):
    message_received = Signal(str, str)

    def __init__(
        self, node: Optional[Node] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._node = node
        self._subscriptions: Dict[str, Any] = {}
        self._topic_data: Dict[str, Any] = {}
        self._selected_topic: Optional[str] = None
        self._selected_service: Optional[str] = None
        self._publisher = None
        self._current_pub_msg_class = None
        self._current_srv_class = None
        self._service_clients: Dict[str, Any] = {}
        self._plot_subscriptions: Dict[str, Any] = {}
        self._plot_data: Dict[str, Any] = {}
        self._plot_items: Dict[str, Any] = {}
        self._plot_available_topics: Dict[str, str] = {}
        self._plot_is_paused = False
        self._plot_time_window = 30.0
        self._plot_start_time: Optional[float] = None
        self._plot_colors: Dict[str, str] = {}

        self._setup_ui()
        self._setup_timers()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.addTab(self._create_topics_tab(), "Topics")
        self._tab_widget.addTab(self._create_services_tab(), "Services")
        self._tab_widget.addTab(self._create_parameters_tab(), "Parameters")
        self._tab_widget.addTab(self._create_plot_tab(), "Plot")

        layout.addWidget(self._tab_widget)

    def _create_topics_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_topics_list_panel()
        right_panel = self._create_topic_details_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        return widget

    def _create_topics_list_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Available Topics"))

        self._refresh_topics_btn = QPushButton("Refresh")
        self._refresh_topics_btn.clicked.connect(self._refresh_topics)
        header_layout.addWidget(self._refresh_topics_btn)

        self._topics_filter = QLineEdit()
        self._topics_filter.setPlaceholderText("Filter topics...")
        self._topics_filter.textChanged.connect(self._filter_topics)

        self._topics_tree = QTreeWidget()
        self._topics_tree.setHeaderLabels(["Topic", "Type"])
        self._topics_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._topics_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._topics_tree.itemClicked.connect(self._on_topic_selected)
        self._topics_tree.setAlternatingRowColors(True)

        layout.addLayout(header_layout)
        layout.addWidget(self._topics_filter)
        layout.addWidget(self._topics_tree, 1)

        return container

    def _create_topic_details_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 0, 0, 0)

        self._topic_info_label = QLabel("Select a topic to view details")
        self._topic_info_label.setProperty("secondary", True)

        sub_group = QGroupBox("Subscribe")
        sub_layout = QVBoxLayout(sub_group)

        qos_layout = QHBoxLayout()
        qos_layout.addWidget(QLabel("QoS:"))
        self._sub_qos_combo = QComboBox()
        self._sub_qos_combo.addItems(list(QOS_PROFILES.keys()))
        self._sub_qos_combo.setCurrentText("Default (Reliable)")
        self._sub_qos_combo.setToolTip("Select QoS profile to match publisher settings")
        qos_layout.addWidget(self._sub_qos_combo, 1)

        self._auto_qos_btn = QPushButton("Auto")
        self._auto_qos_btn.setToolTip("Auto-detect QoS from publisher")
        self._auto_qos_btn.clicked.connect(lambda: self._auto_detect_qos(verbose=True))
        qos_layout.addWidget(self._auto_qos_btn)

        sub_layout.addLayout(qos_layout)

        sub_btn_layout = QHBoxLayout()
        self._subscribe_btn = QPushButton("Subscribe")
        self._subscribe_btn.setProperty("accent", True)
        self._subscribe_btn.clicked.connect(self._subscribe_to_topic)
        self._subscribe_btn.setEnabled(False)

        self._unsubscribe_btn = QPushButton("Unsubscribe")
        self._unsubscribe_btn.clicked.connect(self._unsubscribe_from_topic)
        self._unsubscribe_btn.setEnabled(False)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear_messages)

        sub_btn_layout.addWidget(self._subscribe_btn)
        sub_btn_layout.addWidget(self._unsubscribe_btn)
        sub_btn_layout.addWidget(self._clear_btn)

        self._message_display = QPlainTextEdit()
        self._message_display.setReadOnly(True)
        self._message_display.setFont(QFont("JetBrains Mono", 10))
        self._message_display.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {COLORS.background};
                font-family: "JetBrains Mono", "Consolas", monospace;
            }}
        """
        )

        sub_layout.addLayout(sub_btn_layout)
        sub_layout.addWidget(self._message_display, 1)

        pub_group = QGroupBox("Publish")
        pub_layout = QVBoxLayout(pub_group)

        topic_row = QHBoxLayout()
        topic_row.addWidget(QLabel("Topic:"))
        self._publish_topic_input = QLineEdit()
        self._publish_topic_input.setPlaceholderText("Topic name...")
        topic_row.addWidget(self._publish_topic_input, 1)
        pub_layout.addLayout(topic_row)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self._publish_type_combo = QComboBox()
        self._publish_type_combo.setEditable(True)
        self._publish_type_combo.addItems(
            [
                "std_msgs/msg/String",
                "std_msgs/msg/Int32",
                "std_msgs/msg/Float64",
                "std_msgs/msg/Bool",
                "geometry_msgs/msg/Twist",
                "geometry_msgs/msg/PoseStamped",
                "sensor_msgs/msg/Joy",
            ]
        )
        self._publish_type_combo.currentTextChanged.connect(
            self._on_publish_type_changed
        )
        type_layout.addWidget(self._publish_type_combo, 1)

        self._load_type_btn = QPushButton("Load Fields")
        self._load_type_btn.clicked.connect(self._load_publish_fields)
        type_layout.addWidget(self._load_type_btn)

        pub_layout.addLayout(type_layout)

        pub_qos_layout = QHBoxLayout()
        pub_qos_layout.addWidget(QLabel("QoS:"))
        self._pub_qos_combo = QComboBox()
        self._pub_qos_combo.addItems(list(QOS_PROFILES.keys()))
        self._pub_qos_combo.setCurrentText("Default (Reliable)")
        pub_qos_layout.addWidget(self._pub_qos_combo, 1)
        pub_layout.addLayout(pub_qos_layout)

        self._pub_input_stack = QStackedWidget()

        self._pub_fields_editor = MessageFieldEditor()
        self._pub_fields_editor.setMinimumHeight(120)
        self._pub_fields_editor.setMaximumHeight(200)

        self._pub_raw_input = QPlainTextEdit()
        self._pub_raw_input.setPlaceholderText("Enter message as YAML or JSON...")
        self._pub_raw_input.setFont(QFont("JetBrains Mono", 10))
        self._pub_raw_input.setMinimumHeight(120)
        self._pub_raw_input.setMaximumHeight(200)

        self._pub_input_stack.addWidget(self._pub_fields_editor)
        self._pub_input_stack.addWidget(self._pub_raw_input)

        mode_layout = QHBoxLayout()
        self._pub_mode_combo = QComboBox()
        self._pub_mode_combo.addItems(["Form Fields", "Raw YAML/JSON"])
        self._pub_mode_combo.currentIndexChanged.connect(self._on_pub_mode_changed)
        mode_layout.addWidget(QLabel("Input Mode:"))
        mode_layout.addWidget(self._pub_mode_combo)
        mode_layout.addStretch()

        pub_layout.addLayout(mode_layout)
        pub_layout.addWidget(self._pub_input_stack)

        pub_btn_layout = QHBoxLayout()
        self._publish_btn = QPushButton("Publish")
        self._publish_btn.setProperty("accent", True)
        self._publish_btn.clicked.connect(self._publish_message_action)

        self._publish_rate_spin = QSpinBox()
        self._publish_rate_spin.setRange(0, 100)
        self._publish_rate_spin.setValue(0)
        self._publish_rate_spin.setSuffix(" Hz")
        self._publish_rate_spin.setToolTip("0 = single publish")

        self._clear_pub_fields_btn = QPushButton("Clear")
        self._clear_pub_fields_btn.clicked.connect(self._clear_publish_fields)

        pub_btn_layout.addWidget(self._publish_btn)
        pub_btn_layout.addWidget(QLabel("Rate:"))
        pub_btn_layout.addWidget(self._publish_rate_spin)
        pub_btn_layout.addStretch()
        pub_btn_layout.addWidget(self._clear_pub_fields_btn)

        pub_layout.addLayout(pub_btn_layout)

        layout.addWidget(self._topic_info_label)
        layout.addWidget(sub_group, 2)
        layout.addWidget(pub_group)

        return container

    def _create_services_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Available Services"))

        self._refresh_services_btn = QPushButton("Refresh")
        self._refresh_services_btn.clicked.connect(self._refresh_services)
        header_layout.addWidget(self._refresh_services_btn)

        self._services_filter = QLineEdit()
        self._services_filter.setPlaceholderText("Filter services...")
        self._services_filter.textChanged.connect(self._filter_services)

        self._services_tree = QTreeWidget()
        self._services_tree.setHeaderLabels(["Service", "Type"])
        self._services_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._services_tree.itemClicked.connect(self._on_service_selected)
        self._services_tree.setAlternatingRowColors(True)

        left_layout.addLayout(header_layout)
        left_layout.addWidget(self._services_filter)
        left_layout.addWidget(self._services_tree, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self._service_info_label = QLabel("Select a service to call")
        self._service_info_label.setProperty("secondary", True)

        call_group = QGroupBox("Call Service")
        call_layout = QVBoxLayout(call_group)

        srv_name_row = QHBoxLayout()
        srv_name_row.addWidget(QLabel("Service:"))
        self._service_name_input = QLineEdit()
        self._service_name_input.setPlaceholderText("Service name...")
        srv_name_row.addWidget(self._service_name_input, 1)
        call_layout.addLayout(srv_name_row)

        srv_type_layout = QHBoxLayout()
        srv_type_layout.addWidget(QLabel("Type:"))
        self._service_type_combo = QComboBox()
        self._service_type_combo.setEditable(True)
        self._service_type_combo.addItems(
            [
                "std_srvs/srv/Empty",
                "std_srvs/srv/SetBool",
                "std_srvs/srv/Trigger",
            ]
        )
        self._service_type_combo.currentTextChanged.connect(
            self._on_service_type_changed
        )
        srv_type_layout.addWidget(self._service_type_combo, 1)

        self._load_srv_type_btn = QPushButton("Load Fields")
        self._load_srv_type_btn.clicked.connect(self._load_service_fields)
        srv_type_layout.addWidget(self._load_srv_type_btn)

        call_layout.addLayout(srv_type_layout)

        req_label = QLabel("Request:")
        req_label.setProperty("secondary", True)
        call_layout.addWidget(req_label)

        self._srv_input_stack = QStackedWidget()

        self._srv_fields_editor = MessageFieldEditor()
        self._srv_fields_editor.setMinimumHeight(100)

        self._srv_raw_input = QPlainTextEdit()
        self._srv_raw_input.setPlaceholderText("Enter request as YAML or JSON...")
        self._srv_raw_input.setFont(QFont("JetBrains Mono", 10))
        self._srv_raw_input.setMinimumHeight(100)

        self._srv_input_stack.addWidget(self._srv_fields_editor)
        self._srv_input_stack.addWidget(self._srv_raw_input)

        srv_mode_layout = QHBoxLayout()
        self._srv_mode_combo = QComboBox()
        self._srv_mode_combo.addItems(["Form Fields", "Raw YAML/JSON"])
        self._srv_mode_combo.currentIndexChanged.connect(self._on_srv_mode_changed)
        srv_mode_layout.addWidget(QLabel("Input Mode:"))
        srv_mode_layout.addWidget(self._srv_mode_combo)
        srv_mode_layout.addStretch()

        call_layout.addLayout(srv_mode_layout)
        call_layout.addWidget(self._srv_input_stack)

        srv_btn_layout = QHBoxLayout()
        self._call_service_btn = QPushButton("Call Service")
        self._call_service_btn.setProperty("accent", True)
        self._call_service_btn.clicked.connect(self._call_service)

        self._clear_srv_fields_btn = QPushButton("Clear")
        self._clear_srv_fields_btn.clicked.connect(self._clear_service_fields)

        srv_btn_layout.addWidget(self._call_service_btn)
        srv_btn_layout.addStretch()
        srv_btn_layout.addWidget(self._clear_srv_fields_btn)

        call_layout.addLayout(srv_btn_layout)

        resp_label = QLabel("Response:")
        resp_label.setProperty("secondary", True)
        call_layout.addWidget(resp_label)

        self._service_response = QPlainTextEdit()
        self._service_response.setReadOnly(True)
        self._service_response.setFont(QFont("JetBrains Mono", 10))
        self._service_response.setStyleSheet(
            f"""
            QPlainTextEdit {{
                background-color: {COLORS.background};
            }}
        """
        )

        call_layout.addWidget(self._service_response, 1)

        right_layout.addWidget(self._service_info_label)
        right_layout.addWidget(call_group, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter)
        return widget

    def _create_parameters_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        self._param_reconfigure = ParameterReconfigureWidget()
        self._param_reconfigure.parameterSet.connect(self._on_parameter_set)
        self._param_reconfigure.errorOccurred.connect(self._on_param_error)

        layout.addWidget(self._param_reconfigure)
        return widget

    def _create_plot_tab(self) -> QWidget:
        """Create the plot tab for real-time topic visualization."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        pg.setConfigOptions(antialias=True)
        pg.setConfigOption("background", COLORS.background)
        pg.setConfigOption("foreground", COLORS.text_primary)

        controls = self._create_plot_controls()
        layout.addWidget(controls)

        splitter = QSplitter(Qt.Horizontal)
        left_panel = self._create_plot_topic_panel()
        right_panel = self._create_plot_display_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 650])

        layout.addWidget(splitter, 1)

        self._plot_update_timer = QTimer()
        self._plot_update_timer.timeout.connect(self._update_plot_curves)
        self._plot_update_timer.start(50)

        self._plot_topic_refresh_timer = QTimer()
        self._plot_topic_refresh_timer.timeout.connect(self._refresh_plot_topics)
        self._plot_topic_refresh_timer.start(5000)

        return widget

    @Slot(str, str, object)
    def _on_parameter_set(self, node_name: str, param_name: str, value: Any) -> None:
        pass

    @Slot(str)
    def _on_param_error(self, error: str) -> None:
        pass

    def _setup_timers(self) -> None:
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.start()

        self._publish_timer = QTimer(self)
        self._publish_timer.timeout.connect(self._timed_publish)

    def _connect_signals(self) -> None:
        self.message_received.connect(self._display_message)

    @Slot()
    def _refresh_topics(self) -> None:
        if not self._node:
            return

        self._topics_tree.clear()
        topics = self._node.get_topic_names_and_types()

        for topic_name, topic_types in sorted(topics):
            type_str = topic_types[0] if topic_types else "unknown"
            item = QTreeWidgetItem([topic_name, type_str])
            self._topics_tree.addTopLevelItem(item)

    @Slot(str)
    def _filter_topics(self, text: str) -> None:
        for i in range(self._topics_tree.topLevelItemCount()):
            item = self._topics_tree.topLevelItem(i)
            matches = (
                text.lower() in item.text(0).lower()
                or text.lower() in item.text(1).lower()
            )
            item.setHidden(not matches)

    @Slot(QTreeWidgetItem, int)
    def _on_topic_selected(self, item: QTreeWidgetItem, column: int) -> None:
        self._selected_topic = item.text(0)
        topic_type = item.text(1)

        self._topic_info_label.setText(
            f"Topic: {self._selected_topic}\nType: {topic_type}"
        )

        is_subscribed = self._selected_topic in self._subscriptions
        self._subscribe_btn.setEnabled(not is_subscribed)
        self._unsubscribe_btn.setEnabled(is_subscribed)

        self._publish_topic_input.setText(self._selected_topic)
        self._publish_type_combo.setCurrentText(topic_type)

        self._load_publish_fields()
        self._auto_detect_qos()

    @Slot(str)
    def _on_publish_type_changed(self, type_str: str) -> None:
        pass

    @Slot()
    def _load_publish_fields(self) -> None:
        type_str = self._publish_type_combo.currentText().strip()
        if not type_str:
            return

        msg_class = self._get_message_class(type_str)
        if msg_class:
            self._current_pub_msg_class = msg_class
            self._pub_fields_editor.set_message_class(msg_class)
        else:
            self._current_pub_msg_class = None
            self._message_display.appendPlainText(
                f"Could not load message type: {type_str}"
            )

    @Slot(int)
    def _on_pub_mode_changed(self, index: int) -> None:
        self._pub_input_stack.setCurrentIndex(index)

    @Slot()
    def _clear_publish_fields(self) -> None:
        self._pub_fields_editor.clear_values()
        self._pub_raw_input.clear()

    @Slot()
    def _auto_detect_qos(self, verbose: bool = False) -> None:
        if not self._node or not self._selected_topic:
            return

        topic = self._selected_topic
        try:
            endpoint_info_list = self._node.get_publishers_info_by_topic(topic)
            if not endpoint_info_list:
                if verbose:
                    self._message_display.appendPlainText(
                        f"No publishers found for {topic}"
                    )
                return

            endpoint_info = endpoint_info_list[0]
            qos = endpoint_info.qos_profile

            if qos.reliability == QoSReliabilityPolicy.BEST_EFFORT:
                if qos.durability == QoSDurabilityPolicy.VOLATILE:
                    self._sub_qos_combo.setCurrentText("Best Effort")
                else:
                    self._sub_qos_combo.setCurrentText("Sensor Data (Best Effort)")
            else:
                if qos.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL:
                    self._sub_qos_combo.setCurrentText("Reliable + Transient Local")
                else:
                    self._sub_qos_combo.setCurrentText("Default (Reliable)")

            if verbose:
                self._message_display.appendPlainText(
                    f"Detected QoS for {topic}: "
                    f"reliability={qos.reliability.name}, "
                    f"durability={qos.durability.name}"
                )

        except Exception as e:
            if verbose:
                self._message_display.appendPlainText(f"Error detecting QoS: {e}")

    @Slot()
    def _subscribe_to_topic(self) -> None:
        if not self._node or not self._selected_topic:
            return

        topic = self._selected_topic
        if topic in self._subscriptions:
            return

        try:
            topics = self._node.get_topic_names_and_types()
            topic_type = None
            for t_name, t_types in topics:
                if t_name == topic:
                    topic_type = t_types[0] if t_types else None
                    break

            if not topic_type:
                self._message_display.appendPlainText(
                    f"Error: Could not find type for {topic}"
                )
                return

            msg_class = self._get_message_class(topic_type)
            if msg_class is None:
                self._message_display.appendPlainText(
                    f"Error: Unknown message type {topic_type}"
                )
                return

            qos_name = self._sub_qos_combo.currentText()
            qos_profile = QOS_PROFILES.get(qos_name, QOS_PROFILES["Default (Reliable)"])

            sub = self._node.create_subscription(
                msg_class,
                topic,
                lambda msg, t=topic: self._on_message_received(t, msg),
                qos_profile,
            )
            self._subscriptions[topic] = sub
            self._subscribe_btn.setEnabled(False)
            self._unsubscribe_btn.setEnabled(True)
            self._message_display.appendPlainText(
                f"Subscribed to {topic} (QoS: {qos_name})"
            )

        except Exception as e:
            self._message_display.appendPlainText(f"Error: {e}")

    def _get_message_class(self, type_str: str):
        try:
            parts = type_str.split("/")
            if len(parts) == 3:
                package, folder, msg_name = parts
                module = __import__(f"{package}.{folder}", fromlist=[msg_name])
                return getattr(module, msg_name)
        except Exception:
            # Message class not found or import failed
            pass
        return None

    def _on_message_received(self, topic: str, msg: Any) -> None:
        try:
            msg_dict = self._message_to_dict(msg)
            msg_str = yaml.dump(msg_dict, default_flow_style=False, allow_unicode=True)
            self.message_received.emit(topic, msg_str)
        except Exception as e:
            self.message_received.emit(topic, f"Error parsing message: {e}")

    def _message_to_dict(self, msg: Any) -> Dict:
        if hasattr(msg, "get_fields_and_field_types"):
            fields = msg.get_fields_and_field_types()
            result = {}
            for field_name in fields:
                value = getattr(msg, field_name)
                if hasattr(value, "get_fields_and_field_types"):
                    result[field_name] = self._message_to_dict(value)
                elif isinstance(value, (list, tuple)):
                    result[field_name] = [
                        (
                            self._message_to_dict(v)
                            if hasattr(v, "get_fields_and_field_types")
                            else v
                        )
                        for v in value
                    ]
                else:
                    result[field_name] = value
            return result
        return str(msg)

    @Slot(str, str)
    def _display_message(self, topic: str, msg: str) -> None:
        timestamp = self._get_timestamp()
        self._message_display.appendPlainText(f"[{timestamp}] {topic}:\n{msg}\n")

        max_lines = 1000
        doc = self._message_display.document()
        if doc.blockCount() > max_lines:
            cursor = self._message_display.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor,
                doc.blockCount() - max_lines,
            )
            cursor.removeSelectedText()

    def _get_timestamp(self) -> str:
        from datetime import datetime

        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    @Slot()
    def _unsubscribe_from_topic(self) -> None:
        if not self._node or not self._selected_topic:
            return

        topic = self._selected_topic
        if topic in self._subscriptions:
            try:
                self._node.destroy_subscription(self._subscriptions[topic])
            except Exception as e:
                self._message_display.appendPlainText(
                    f"Error destroying subscription: {e}"
                )
            del self._subscriptions[topic]
            self._message_display.appendPlainText(f"Unsubscribed from {topic}")
            self._subscribe_btn.setEnabled(True)
            self._unsubscribe_btn.setEnabled(False)
        else:
            self._message_display.appendPlainText(f"Not subscribed to {topic}")

    @Slot()
    def _clear_messages(self) -> None:
        self._message_display.clear()

    @Slot()
    def _publish_message_action(self) -> None:
        if not self._node:
            return

        topic = self._publish_topic_input.text().strip()
        type_str = self._publish_type_combo.currentText().strip()

        if not topic or not type_str:
            return

        try:
            msg_class = self._get_message_class(type_str)
            if msg_class is None:
                self._message_display.appendPlainText(f"Error: Unknown type {type_str}")
                return

            msg = msg_class()

            if self._pub_input_stack.currentIndex() == 0:
                data = self._pub_fields_editor.get_values()
                if data:
                    self._fill_message(msg, data)
            else:
                msg_text = self._pub_raw_input.toPlainText().strip()
                if msg_text:
                    try:
                        data = yaml.safe_load(msg_text)
                        if data:
                            self._fill_message(msg, data)
                    except Exception as e:
                        self._message_display.appendPlainText(
                            f"Error parsing message: {e}"
                        )
                        return

            if self._publisher is None or self._publisher.topic_name != topic:
                if self._publisher:
                    try:
                        self._node.destroy_publisher(self._publisher)
                    except Exception:
                        # Publisher may already be destroyed
                        pass
                pub_qos_name = self._pub_qos_combo.currentText()
                pub_qos = QOS_PROFILES.get(
                    pub_qos_name, QOS_PROFILES["Default (Reliable)"]
                )
                self._publisher = self._node.create_publisher(msg_class, topic, pub_qos)

            rate = self._publish_rate_spin.value()
            if rate > 0:
                if not self._publish_timer.isActive():
                    interval = int(1000 / rate)
                    self._publish_timer.setInterval(interval)
                    self._publish_timer.start()
                    self._publish_btn.setText("Stop")
                else:
                    self._publish_timer.stop()
                    self._publish_btn.setText("Publish")
            else:
                self._publisher.publish(msg)
                self._message_display.appendPlainText(f"Published to {topic}")

        except Exception as e:
            self._message_display.appendPlainText(f"Error publishing: {e}")

    @Slot()
    def _timed_publish(self) -> None:
        if not self._publisher:
            return

        type_str = self._publish_type_combo.currentText().strip()

        try:
            msg_class = self._get_message_class(type_str)
            if msg_class is None:
                return

            msg = msg_class()

            if self._pub_input_stack.currentIndex() == 0:
                data = self._pub_fields_editor.get_values()
                if data:
                    self._fill_message(msg, data)
            else:
                msg_text = self._pub_raw_input.toPlainText().strip()
                if msg_text:
                    try:
                        data = yaml.safe_load(msg_text)
                        if data:
                            self._fill_message(msg, data)
                    except Exception:
                        # Invalid YAML; skip publish
                        return

            self._publisher.publish(msg)

        except Exception:
            # Timed publish failures are non-critical
            pass

    def _fill_message(self, msg: Any, data: Dict) -> None:
        for key, value in data.items():
            if hasattr(msg, key):
                attr = getattr(msg, key)
                if hasattr(attr, "get_fields_and_field_types") and isinstance(
                    value, dict
                ):
                    self._fill_message(attr, value)
                else:
                    try:
                        setattr(msg, key, value)
                    except Exception:
                        # Skip incompatible field assignments
                        pass

    @Slot()
    def _refresh_services(self) -> None:
        if not self._node:
            return

        self._services_tree.clear()
        services = self._node.get_service_names_and_types()

        for srv_name, srv_types in sorted(services):
            type_str = srv_types[0] if srv_types else "unknown"
            item = QTreeWidgetItem([srv_name, type_str])
            self._services_tree.addTopLevelItem(item)

    @Slot(str)
    def _filter_services(self, text: str) -> None:
        for i in range(self._services_tree.topLevelItemCount()):
            item = self._services_tree.topLevelItem(i)
            matches = text.lower() in item.text(0).lower()
            item.setHidden(not matches)

    @Slot(QTreeWidgetItem, int)
    def _on_service_selected(self, item: QTreeWidgetItem, column: int) -> None:
        self._selected_service = item.text(0)
        service_type = item.text(1)

        self._service_info_label.setText(
            f"Service: {self._selected_service}\nType: {service_type}"
        )
        self._service_name_input.setText(self._selected_service)
        self._service_type_combo.setCurrentText(service_type)

        self._load_service_fields()

    @Slot(str)
    def _on_service_type_changed(self, type_str: str) -> None:
        pass

    @Slot()
    def _load_service_fields(self) -> None:
        type_str = self._service_type_combo.currentText().strip()
        if not type_str:
            return

        srv_class = self._get_service_class(type_str)
        if srv_class:
            self._current_srv_class = srv_class
            if hasattr(srv_class, "Request"):
                self._srv_fields_editor.set_message_class(srv_class.Request)
        else:
            self._current_srv_class = None
            self._service_response.setPlainText(
                f"Could not load service type: {type_str}"
            )

    @Slot(int)
    def _on_srv_mode_changed(self, index: int) -> None:
        self._srv_input_stack.setCurrentIndex(index)

    @Slot()
    def _clear_service_fields(self) -> None:
        self._srv_fields_editor.clear_values()
        self._srv_raw_input.clear()
        self._service_response.clear()

    @Slot()
    def _call_service(self) -> None:
        if not self._node:
            return

        service_name = self._service_name_input.text().strip()
        type_str = self._service_type_combo.currentText().strip()

        if not service_name or not type_str:
            return

        try:
            srv_class = self._get_service_class(type_str)
            if srv_class is None:
                self._service_response.setPlainText(
                    f"Error: Unknown service type {type_str}"
                )
                return

            if service_name in self._service_clients:
                client = self._service_clients[service_name]
            else:
                client = self._node.create_client(srv_class, service_name)
                self._service_clients[service_name] = client

            if not client.wait_for_service(timeout_sec=2.0):
                self._service_response.setPlainText(
                    f"Service {service_name} not available"
                )
                return

            request = srv_class.Request()

            if self._srv_input_stack.currentIndex() == 0:
                data = self._srv_fields_editor.get_values()
                if data:
                    self._fill_message(request, data)
            else:
                request_text = self._srv_raw_input.toPlainText().strip()
                if request_text:
                    try:
                        data = yaml.safe_load(request_text)
                        if data:
                            self._fill_message(request, data)
                    except Exception as e:
                        self._service_response.setPlainText(
                            f"Error parsing request: {e}"
                        )
                        return

            self._service_response.setPlainText("Calling service...")
            future = client.call_async(request)

            def handle_response():
                try:
                    response = future.result()
                    resp_dict = self._message_to_dict(response)
                    resp_str = yaml.dump(resp_dict, default_flow_style=False)
                    self._service_response.setPlainText(resp_str)
                except Exception as e:
                    self._service_response.setPlainText(f"Error: {e}")

            QTimer.singleShot(
                100, lambda: self._check_service_response(future, handle_response)
            )

        except Exception as e:
            self._service_response.setPlainText(f"Error: {e}")

    def _check_service_response(self, future, callback):
        if future.done():
            callback()
        else:
            QTimer.singleShot(
                100, lambda: self._check_service_response(future, callback)
            )

    def _get_service_class(self, type_str: str):
        try:
            parts = type_str.split("/")
            if len(parts) == 3:
                package, folder, srv_name = parts
                module = __import__(f"{package}.{folder}", fromlist=[srv_name])
                return getattr(module, srv_name)
        except Exception:
            # Service class not found or import failed
            pass
        return None

    @Slot()
    def _auto_refresh(self) -> None:
        pass

    def set_node(self, node: Node) -> None:
        self._node = node
        self._refresh_topics()
        self._refresh_services()
        self._param_reconfigure.set_node(node)
        if hasattr(self, "_plot_topic_combo"):
            self._refresh_plot_topics()

    # Plot Tab Methods
    def _create_plot_controls(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        time_window_layout = QHBoxLayout()
        time_window_layout.addWidget(QLabel("Time Window (s):"))
        self._plot_time_window_spin = QDoubleSpinBox()
        self._plot_time_window_spin.setRange(1.0, 300.0)
        self._plot_time_window_spin.setValue(30.0)
        self._plot_time_window_spin.setSuffix(" s")
        self._plot_time_window_spin.setDecimals(1)
        self._plot_time_window_spin.valueChanged.connect(
            lambda v: setattr(self, "_plot_time_window", v)
        )
        time_window_layout.addWidget(self._plot_time_window_spin)

        max_points_layout = QHBoxLayout()
        max_points_layout.addWidget(QLabel("Max Points:"))
        self._plot_max_points_spin = QSpinBox()
        self._plot_max_points_spin.setRange(100, 100000)
        self._plot_max_points_spin.setValue(10000)
        max_points_layout.addWidget(self._plot_max_points_spin)

        self._plot_pause_btn = QPushButton("Pause")
        self._plot_pause_btn.setCheckable(True)
        self._plot_pause_btn.toggled.connect(
            lambda p: setattr(self, "_plot_is_paused", p) or self._plot_pause_btn.setText("Resume" if p else "Pause")
        )

        self._plot_clear_btn = QPushButton("Clear All")
        self._plot_clear_btn.clicked.connect(self._clear_all_plots)

        self._plot_export_btn = QPushButton("Export Data")
        self._plot_export_btn.clicked.connect(self._export_plot_data)

        layout.addLayout(time_window_layout)
        layout.addLayout(max_points_layout)
        layout.addStretch()
        layout.addWidget(self._plot_pause_btn)
        layout.addWidget(self._plot_clear_btn)
        layout.addWidget(self._plot_export_btn)

        return widget

    def _create_plot_topic_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        topic_group = QGroupBox("Add Plot")
        topic_layout = QVBoxLayout(topic_group)

        topic_row = QHBoxLayout()
        topic_row.addWidget(QLabel("Topic:"))
        self._plot_topic_combo = QComboBox()
        self._plot_topic_combo.setEditable(True)
        self._plot_topic_combo.setMinimumWidth(200)
        self._plot_topic_combo.currentTextChanged.connect(self._on_plot_topic_changed)
        self._plot_refresh_topics_btn = QPushButton("Refresh")
        self._plot_refresh_topics_btn.clicked.connect(self._refresh_plot_topics)
        topic_row.addWidget(self._plot_topic_combo, 1)
        topic_row.addWidget(self._plot_refresh_topics_btn)
        topic_layout.addLayout(topic_row)

        field_row = QHBoxLayout()
        field_row.addWidget(QLabel("Field:"))
        self._plot_field_combo = QComboBox()
        self._plot_field_combo.setEditable(True)
        self._plot_load_fields_btn = QPushButton("Load Fields")
        self._plot_load_fields_btn.clicked.connect(self._load_plot_fields)
        field_row.addWidget(self._plot_field_combo, 1)
        field_row.addWidget(self._plot_load_fields_btn)
        topic_layout.addLayout(field_row)

        qos_row = QHBoxLayout()
        qos_row.addWidget(QLabel("QoS:"))
        self._plot_qos_combo = QComboBox()
        self._plot_qos_combo.addItems(list(QOS_PROFILES.keys()))
        self._plot_qos_combo.setCurrentText("Default (Reliable)")
        self._plot_auto_qos_btn = QPushButton("Auto")
        self._plot_auto_qos_btn.setToolTip("Auto-detect QoS from publisher")
        self._plot_auto_qos_btn.clicked.connect(self._auto_detect_plot_qos)
        qos_row.addWidget(self._plot_qos_combo, 1)
        qos_row.addWidget(self._plot_auto_qos_btn)
        topic_layout.addLayout(qos_row)

        self._plot_add_btn = QPushButton("Add Plot")
        self._plot_add_btn.clicked.connect(self._add_plot)
        topic_layout.addWidget(self._plot_add_btn)

        layout.addWidget(topic_group)

        plots_group = QGroupBox("Active Plots")
        plots_layout = QVBoxLayout(plots_group)

        self._plots_tree = QTreeWidget()
        self._plots_tree.setHeaderLabels(["Color", "Plot", "Topic", "Field", ""])
        self._plots_tree.setRootIsDecorated(False)
        self._plots_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._plots_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self._plots_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._plots_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._plots_tree.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        plots_layout.addWidget(self._plots_tree)

        layout.addWidget(plots_group, 1)

        return widget

    def _create_plot_display_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot_widget = PlotWidget()
        self._plot_widget.setLabel("left", "Value")
        self._plot_widget.setLabel("bottom", "Time (s)")
        self._plot_widget.setTitle("Real-time Topic Data")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.setBackground(COLORS.background)

        self._plot_color_index = 0
        self._plot_color_palette = [
            COLORS.accent,
            COLORS.info,
            COLORS.success,
            COLORS.warning,
            COLORS.error,
            "#FF6B9D",
            "#C44569",
            "#6C5CE7",
        ]

        layout.addWidget(self._plot_widget)
        return widget

    def _refresh_plot_topics(self) -> None:
        if not self._node:
            return
        try:
            topic_names_and_types = self._node.get_topic_names_and_types()
            self._plot_available_topics = {
                name: types[0] for name, types in topic_names_and_types
            }
            current_text = self._plot_topic_combo.currentText()
            self._plot_topic_combo.clear()
            self._plot_topic_combo.addItems(sorted(self._plot_available_topics.keys()))
            if current_text in self._plot_available_topics:
                self._plot_topic_combo.setCurrentText(current_text)
        except Exception as e:
            if self._node:
                self._node.get_logger().warn(f"Failed to refresh plot topics: {e}")

    def _on_plot_topic_changed(self, topic: str) -> None:
        if topic in self._plot_available_topics:
            self._load_plot_fields()
            self._auto_detect_plot_qos()

    def _load_plot_fields(self) -> None:
        topic = self._plot_topic_combo.currentText()
        if not topic or topic not in self._plot_available_topics:
            return
        try:
            msg_type_str = self._plot_available_topics[topic]
            msg_class = self._get_message_class(msg_type_str)
            if msg_class:
                sample_msg = msg_class()
                fields = self._get_numeric_fields(sample_msg)
                self._plot_field_combo.clear()
                if fields:
                    self._plot_field_combo.addItems(fields)
                    self._plot_field_combo.setCurrentIndex(0)
                else:
                    self._plot_field_combo.addItem("(No numeric fields found)")
        except Exception as e:
            if self._node:
                self._node.get_logger().warn(f"Failed to load plot fields: {e}")

    def _get_numeric_fields(self, msg: Any, prefix: str = "") -> List[str]:
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
                    fields.extend(self._get_numeric_fields(value, field_path))
                elif isinstance(value, (list, tuple)) and len(value) > 0:
                    if isinstance(value[0], (int, float)):
                        for i in range(len(value)):
                            fields.append(f"{field_path}[{i}]")
        return fields

    def _extract_plot_value(self, msg: Any, field_path: str) -> Optional[float]:
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

    def _auto_detect_plot_qos(self) -> None:
        if not self._node:
            return
        topic = self._plot_topic_combo.currentText()
        if not topic:
            return
        try:
            endpoint_info_list = self._node.get_publishers_info_by_topic(topic)
            if not endpoint_info_list:
                return
            endpoint_info = endpoint_info_list[0]
            qos = endpoint_info.qos_profile
            if qos.reliability == QoSReliabilityPolicy.BEST_EFFORT:
                if qos.durability == QoSDurabilityPolicy.VOLATILE:
                    self._plot_qos_combo.setCurrentText("Best Effort")
                else:
                    self._plot_qos_combo.setCurrentText("Sensor Data (Best Effort)")
            else:
                if qos.durability == QoSDurabilityPolicy.TRANSIENT_LOCAL:
                    self._plot_qos_combo.setCurrentText("Reliable + Transient Local")
                else:
                    self._plot_qos_combo.setCurrentText("Default (Reliable)")
        except Exception:
            pass

    def _add_plot(self) -> None:
        topic = self._plot_topic_combo.currentText()
        field = self._plot_field_combo.currentText()
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
            msg_type_str = self._plot_available_topics.get(topic)
            if not msg_type_str:
                return
            msg_class = self._get_message_class(msg_type_str)
            if not msg_class:
                return
            qos_name = self._plot_qos_combo.currentText()
            qos_profile = QOS_PROFILES.get(qos_name, QOS_PROFILES["Default (Reliable)"])
            max_points = self._plot_max_points_spin.value()

            if self._plot_start_time is None:
                self._plot_start_time = time.time()

            class PlotData:
                def __init__(self, max_points: int, shared_start_time: float):
                    self.max_points = max_points
                    self.times = deque(maxlen=max_points)
                    self.values = deque(maxlen=max_points)
                    self.shared_start_time = shared_start_time

                def add_point(self, value: float):
                    elapsed = time.time() - self.shared_start_time
                    self.times.append(elapsed)
                    self.values.append(value)

                def clear(self):
                    self.times.clear()
                    self.values.clear()

                def reset_start_time(self, new_start_time: float):
                    self.shared_start_time = new_start_time

                def get_arrays(self):
                    if len(self.times) == 0:
                        return [], []
                    return list(self.times), list(self.values)

            def callback(msg):
                if not self._plot_is_paused:
                    value = self._extract_plot_value(msg, field)
                    if value is not None and plot_id in self._plot_data:
                        self._plot_data[plot_id].add_point(value)

            subscription = self._node.create_subscription(
                msg_class, topic, callback, qos_profile
            )
            self._plot_subscriptions[plot_id] = subscription
            self._plot_data[plot_id] = PlotData(max_points, self._plot_start_time)

            color = self._plot_color_palette[self._plot_color_index % len(self._plot_color_palette)]
            self._plot_colors[plot_id] = color
            self._plot_color_index += 1
            pen = pg.mkPen(color, width=2)
            plot_item = self._plot_widget.plot([], [], pen=pen, name=plot_id)
            self._plot_items[plot_id] = plot_item

            item = QTreeWidgetItem(self._plots_tree)
            color_label = QLabel()
            color_label.setFixedSize(20, 20)
            color_label.setStyleSheet(f"background-color: {color}; border: 1px solid {COLORS.border}; border-radius: 3px;")
            color_label.setToolTip(f"Color: {color}")
            item.setText(1, plot_id)
            item.setText(2, topic)
            item.setText(3, field)
            self._plots_tree.setItemWidget(item, 0, color_label)
            remove_btn = QPushButton("Remove")
            remove_btn.clicked.connect(lambda: self._remove_plot(plot_id))
            self._plots_tree.setItemWidget(item, 4, remove_btn)

            if self._node:
                self._node.get_logger().info(f"Added plot: {plot_id}")
        except Exception as e:
            if self._node:
                self._node.get_logger().error(f"Failed to add plot: {e}")

    def _remove_plot(self, plot_id: str) -> None:
        if plot_id in self._plot_subscriptions:
            self._node.destroy_subscription(self._plot_subscriptions[plot_id])
            del self._plot_subscriptions[plot_id]
        if plot_id in self._plot_data:
            del self._plot_data[plot_id]
        if plot_id in self._plot_items:
            self._plot_widget.removeItem(self._plot_items[plot_id])
            del self._plot_items[plot_id]
        if plot_id in self._plot_colors:
            del self._plot_colors[plot_id]
        for i in range(self._plots_tree.topLevelItemCount()):
            item = self._plots_tree.topLevelItem(i)
            if item and item.text(1) == plot_id:
                self._plots_tree.takeTopLevelItem(i)
                break
        if len(self._plot_data) == 0:
            self._plot_start_time = None
        if self._node:
            self._node.get_logger().info(f"Removed plot: {plot_id}")

    def _update_plot_curves(self) -> None:
        if not self._plot_items or self._plot_start_time is None:
            return
        time_window = self._plot_time_window
        min_time = float("inf")
        max_time = float("-inf")
        
        for plot_id, plot_item in self._plot_items.items():
            if plot_id not in self._plot_data:
                continue
            data = self._plot_data[plot_id]
            times, values = data.get_arrays()
            if len(times) == 0:
                continue
            
            if not self._plot_is_paused and time_window > 0:
                current_relative_time = time.time() - self._plot_start_time
                cutoff_time = current_relative_time - time_window
                filtered_times = [t for t in times if t >= cutoff_time]
                if len(filtered_times) < len(values):
                    filtered_values = list(values)[-len(filtered_times):]
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

    def _clear_all_plots(self) -> None:
        for plot_data in self._plot_data.values():
            plot_data.clear()
        for plot_item in self._plot_items.values():
            plot_item.setData([], [])
        
        if self._plot_start_time is not None:
            self._plot_start_time = time.time()
            for plot_data in self._plot_data.values():
                plot_data.reset_start_time(self._plot_start_time)
        
        if self._node:
            self._node.get_logger().info("Cleared all plot data, restarting capture")

    def _export_plot_data(self) -> None:
        if not self._plot_data:
            QMessageBox.warning(self, "Export", "No data to export")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"plot_data_{timestamp}.csv"
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Plot Data", default_filename, "CSV Files (*.csv)"
        )
        if not filename:
            return
        
        try:
            with open(filename, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Time (s)"] + [plot_id for plot_id in self._plot_data.keys()])
                
                all_times = set()
                for plot_data in self._plot_data.values():
                    times, _ = plot_data.get_arrays()
                    all_times.update(times)
                
                sorted_times = sorted(all_times)
                
                for t in sorted_times:
                    row = [t]
                    for plot_id in self._plot_data.keys():
                        times, values = self._plot_data[plot_id].get_arrays()
                        if t in times:
                            idx = times.index(t)
                            row.append(values[idx])
                        else:
                            row.append("")
                    writer.writerow(row)
            
            QMessageBox.information(self, "Export", f"Data exported to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def cleanup(self) -> None:
        self._refresh_timer.stop()
        self._publish_timer.stop()

        if hasattr(self, "_plot_update_timer"):
            self._plot_update_timer.stop()
        if hasattr(self, "_plot_topic_refresh_timer"):
            self._plot_topic_refresh_timer.stop()

        if self._node:
            for sub in self._subscriptions.values():
                try:
                    self._node.destroy_subscription(sub)
                except Exception:
                    pass

            for sub in self._plot_subscriptions.values():
                try:
                    self._node.destroy_subscription(sub)
                except Exception:
                    pass

            if self._publisher:
                try:
                    self._node.destroy_publisher(self._publisher)
                except Exception:
                    pass

            for client in self._service_clients.values():
                try:
                    self._node.destroy_client(client)
                except Exception:
                    pass

        self._subscriptions.clear()
        self._service_clients.clear()
        self._publisher = None

        self._param_reconfigure.cleanup()
