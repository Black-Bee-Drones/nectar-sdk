from typing import Optional, Dict, Any
import yaml
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
    QCheckBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont

from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from mirela_sdk.interface.theme import COLORS
from mirela_sdk.interface.widgets import VideoDisplay, ParameterReconfigureWidget


class ROSTab(QWidget):
    """ROS2 tools tab with topics, services, and parameters browser."""

    message_received = Signal(str, str)
    image_received = Signal(object)

    def __init__(self, node: Optional[Node] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._node = node
        self._subscriptions: Dict[str, Any] = {}
        self._topic_data: Dict[str, Any] = {}
        self._selected_topic: Optional[str] = None
        self._publisher = None
        self._cv_bridge = None

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
        self._tab_widget.addTab(self._create_image_viewer_tab(), "Image Viewer")

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
        self._message_display.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS.background};
                font-family: "JetBrains Mono", "Consolas", monospace;
            }}
        """)

        sub_layout.addLayout(sub_btn_layout)
        sub_layout.addWidget(self._message_display, 1)

        pub_group = QGroupBox("Publish")
        pub_layout = QVBoxLayout(pub_group)

        self._publish_topic_input = QLineEdit()
        self._publish_topic_input.setPlaceholderText("Topic name...")

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type:"))
        self._publish_type_combo = QComboBox()
        self._publish_type_combo.setEditable(True)
        self._publish_type_combo.addItems([
            "std_msgs/msg/String",
            "std_msgs/msg/Int32",
            "std_msgs/msg/Float64",
            "std_msgs/msg/Bool",
            "geometry_msgs/msg/Twist",
            "geometry_msgs/msg/PoseStamped",
            "sensor_msgs/msg/Joy",
        ])
        type_layout.addWidget(self._publish_type_combo, 1)

        self._publish_message = QPlainTextEdit()
        self._publish_message.setPlaceholderText("Enter message as YAML or JSON...")
        self._publish_message.setMaximumHeight(150)
        self._publish_message.setFont(QFont("JetBrains Mono", 10))

        pub_btn_layout = QHBoxLayout()
        self._publish_btn = QPushButton("Publish")
        self._publish_btn.setProperty("accent", True)
        self._publish_btn.clicked.connect(self._publish_message_action)

        self._publish_rate_spin = QSpinBox()
        self._publish_rate_spin.setRange(0, 100)
        self._publish_rate_spin.setValue(0)
        self._publish_rate_spin.setSuffix(" Hz")
        self._publish_rate_spin.setToolTip("0 = single publish")

        pub_btn_layout.addWidget(self._publish_btn)
        pub_btn_layout.addWidget(QLabel("Rate:"))
        pub_btn_layout.addWidget(self._publish_rate_spin)

        pub_layout.addWidget(self._publish_topic_input)
        pub_layout.addLayout(type_layout)
        pub_layout.addWidget(self._publish_message)
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

        self._service_name_input = QLineEdit()
        self._service_name_input.setPlaceholderText("Service name...")

        srv_type_layout = QHBoxLayout()
        srv_type_layout.addWidget(QLabel("Type:"))
        self._service_type_combo = QComboBox()
        self._service_type_combo.setEditable(True)
        self._service_type_combo.addItems([
            "std_srvs/srv/Empty",
            "std_srvs/srv/SetBool",
            "std_srvs/srv/Trigger",
        ])
        srv_type_layout.addWidget(self._service_type_combo, 1)

        self._service_request = QPlainTextEdit()
        self._service_request.setPlaceholderText("Enter request as YAML or JSON...")
        self._service_request.setFont(QFont("JetBrains Mono", 10))
        self._service_request.setMaximumHeight(120)

        self._call_service_btn = QPushButton("Call Service")
        self._call_service_btn.setProperty("accent", True)
        self._call_service_btn.clicked.connect(self._call_service)

        resp_label = QLabel("Response:")
        resp_label.setProperty("secondary", True)

        self._service_response = QPlainTextEdit()
        self._service_response.setReadOnly(True)
        self._service_response.setFont(QFont("JetBrains Mono", 10))
        self._service_response.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS.background};
            }}
        """)

        call_layout.addWidget(self._service_name_input)
        call_layout.addLayout(srv_type_layout)
        call_layout.addWidget(QLabel("Request:"))
        call_layout.addWidget(self._service_request)
        call_layout.addWidget(self._call_service_btn)
        call_layout.addWidget(resp_label)
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

    @Slot(str, str, object)
    def _on_parameter_set(self, node_name: str, param_name: str, value: Any) -> None:
        pass

    @Slot(str)
    def _on_param_error(self, error: str) -> None:
        pass

    def _create_image_viewer_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("Topic:"))
        self._image_topic_input = QLineEdit()
        self._image_topic_input.setPlaceholderText("/camera/image_raw")
        control_layout.addWidget(self._image_topic_input, 1)

        self._image_compressed_cb = QCheckBox("Compressed")
        control_layout.addWidget(self._image_compressed_cb)

        control_layout.addWidget(QLabel("QoS:"))
        self._image_qos_combo = QComboBox()
        self._image_qos_combo.addItems(["Best Effort", "Reliable"])
        self._image_qos_combo.setToolTip("Match publisher's QoS policy")
        control_layout.addWidget(self._image_qos_combo)

        self._image_subscribe_btn = QPushButton("Subscribe")
        self._image_subscribe_btn.setProperty("accent", True)
        self._image_subscribe_btn.clicked.connect(self._subscribe_image_topic)
        control_layout.addWidget(self._image_subscribe_btn)

        self._image_unsubscribe_btn = QPushButton("Unsubscribe")
        self._image_unsubscribe_btn.clicked.connect(self._unsubscribe_image_topic)
        self._image_unsubscribe_btn.setEnabled(False)
        control_layout.addWidget(self._image_unsubscribe_btn)

        self._image_display = VideoDisplay()
        self._image_display.set_placeholder("Subscribe to an image topic")

        self._image_info_label = QLabel("No image")
        self._image_info_label.setProperty("secondary", True)
        self._image_info_label.setAlignment(Qt.AlignCenter)

        layout.addLayout(control_layout)
        layout.addWidget(self._image_display, 1)
        layout.addWidget(self._image_info_label)

        return widget

    def _setup_timers(self) -> None:
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.start()

    def _connect_signals(self) -> None:
        self.message_received.connect(self._display_message)
        self.image_received.connect(self._display_image)

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
            matches = text.lower() in item.text(0).lower() or text.lower() in item.text(1).lower()
            item.setHidden(not matches)

    @Slot(QTreeWidgetItem, int)
    def _on_topic_selected(self, item: QTreeWidgetItem, column: int) -> None:
        self._selected_topic = item.text(0)
        topic_type = item.text(1)

        self._topic_info_label.setText(f"Topic: {self._selected_topic}\nType: {topic_type}")

        is_subscribed = self._selected_topic in self._subscriptions
        self._subscribe_btn.setEnabled(not is_subscribed)
        self._unsubscribe_btn.setEnabled(is_subscribed)

        self._publish_topic_input.setText(self._selected_topic)
        self._publish_type_combo.setCurrentText(topic_type)

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
                self._message_display.appendPlainText(f"Error: Could not find type for {topic}")
                return

            msg_class = self._get_message_class(topic_type)
            if msg_class is None:
                self._message_display.appendPlainText(f"Error: Unknown message type {topic_type}")
                return

            sub = self._node.create_subscription(
                msg_class,
                topic,
                lambda msg, t=topic: self._on_message_received(t, msg),
                10
            )
            self._subscriptions[topic] = sub
            self._subscribe_btn.setEnabled(False)
            self._unsubscribe_btn.setEnabled(True)
            self._message_display.appendPlainText(f"Subscribed to {topic}")

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
                        self._message_to_dict(v) if hasattr(v, "get_fields_and_field_types") else v
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
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, doc.blockCount() - max_lines)
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
                self._message_display.appendPlainText(f"Error destroying subscription: {e}")
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
        msg_text = self._publish_message.toPlainText().strip()

        if not topic or not type_str:
            return

        try:
            msg_class = self._get_message_class(type_str)
            if msg_class is None:
                self._message_display.appendPlainText(f"Error: Unknown type {type_str}")
                return

            msg = msg_class()

            if msg_text:
                try:
                    data = yaml.safe_load(msg_text)
                    if data:
                        self._fill_message(msg, data)
                except Exception as e:
                    self._message_display.appendPlainText(f"Error parsing message: {e}")
                    return

            if self._publisher is None or self._publisher.topic != topic:
                self._publisher = self._node.create_publisher(msg_class, topic, 10)

            self._publisher.publish(msg)
            self._message_display.appendPlainText(f"Published to {topic}")

        except Exception as e:
            self._message_display.appendPlainText(f"Error publishing: {e}")

    def _fill_message(self, msg: Any, data: Dict) -> None:
        for key, value in data.items():
            if hasattr(msg, key):
                attr = getattr(msg, key)
                if hasattr(attr, "get_fields_and_field_types") and isinstance(value, dict):
                    self._fill_message(attr, value)
                else:
                    setattr(msg, key, value)

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
        service_name = item.text(0)
        service_type = item.text(1)

        self._service_info_label.setText(f"Service: {service_name}\nType: {service_type}")
        self._service_name_input.setText(service_name)
        self._service_type_combo.setCurrentText(service_type)

    @Slot()
    def _call_service(self) -> None:
        if not self._node:
            return

        service_name = self._service_name_input.text().strip()
        type_str = self._service_type_combo.currentText().strip()
        request_text = self._service_request.toPlainText().strip()

        if not service_name or not type_str:
            return

        try:
            srv_class = self._get_service_class(type_str)
            if srv_class is None:
                self._service_response.setPlainText(f"Error: Unknown service type {type_str}")
                return

            client = self._node.create_client(srv_class, service_name)

            if not client.wait_for_service(timeout_sec=2.0):
                self._service_response.setPlainText(f"Service {service_name} not available")
                return

            request = srv_class.Request()

            if request_text:
                try:
                    data = yaml.safe_load(request_text)
                    if data:
                        self._fill_message(request, data)
                except Exception as e:
                    self._service_response.setPlainText(f"Error parsing request: {e}")
                    return

            future = client.call_async(request)

            def handle_response():
                try:
                    response = future.result()
                    resp_dict = self._message_to_dict(response)
                    resp_str = yaml.dump(resp_dict, default_flow_style=False)
                    self._service_response.setPlainText(resp_str)
                except Exception as e:
                    self._service_response.setPlainText(f"Error: {e}")

            QTimer.singleShot(100, lambda: self._check_service_response(future, handle_response))

        except Exception as e:
            self._service_response.setPlainText(f"Error: {e}")

    def _check_service_response(self, future, callback):
        if future.done():
            callback()
        else:
            QTimer.singleShot(100, lambda: self._check_service_response(future, callback))

    def _get_service_class(self, type_str: str):
        try:
            parts = type_str.split("/")
            if len(parts) == 3:
                package, folder, srv_name = parts
                module = __import__(f"{package}.{folder}", fromlist=[srv_name])
                return getattr(module, srv_name)
        except Exception:
            pass
        return None


    @Slot()
    def _subscribe_image_topic(self) -> None:
        if not self._node:
            return

        topic = self._image_topic_input.text().strip()
        if not topic:
            return

        try:
            if self._cv_bridge is None:
                from cv_bridge import CvBridge
                self._cv_bridge = CvBridge()

            if self._image_compressed_cb.isChecked():
                from sensor_msgs.msg import CompressedImage
                msg_type = CompressedImage
            else:
                from sensor_msgs.msg import Image
                msg_type = Image

            if "image_subscription" in self._subscriptions:
                self._node.destroy_subscription(self._subscriptions["image_subscription"])

            qos_selection = self._image_qos_combo.currentText()
            if qos_selection == "Best Effort":
                reliability = ReliabilityPolicy.BEST_EFFORT
            else:
                reliability = ReliabilityPolicy.RELIABLE

            qos = QoSProfile(
                reliability=reliability,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
                durability=DurabilityPolicy.VOLATILE,
            )

            sub = self._node.create_subscription(
                msg_type,
                topic,
                self._on_image_received,
                qos
            )
            self._subscriptions["image_subscription"] = sub

            self._image_subscribe_btn.setEnabled(False)
            self._image_unsubscribe_btn.setEnabled(True)
            self._image_info_label.setText(f"Subscribed to {topic} ({qos_selection})")

        except Exception as e:
            self._image_info_label.setText(f"Error: {e}")

    def _on_image_received(self, msg: Any) -> None:
        try:
            if hasattr(msg, "format"):
                import cv2
                import numpy as np
                np_arr = np.frombuffer(msg.data, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            else:
                frame = self._cv_bridge.imgmsg_to_cv2(msg, "bgr8")

            self.image_received.emit(frame)
        except Exception as e:
            self.image_received.emit(None)

    @Slot(object)
    def _display_image(self, frame) -> None:
        if frame is not None:
            self._image_display.display_frame(frame)
            h, w = frame.shape[:2]
            self._image_info_label.setText(f"Resolution: {w}×{h}")
        else:
            self._image_display.clear_display()

    @Slot()
    def _unsubscribe_image_topic(self) -> None:
        if "image_subscription" in self._subscriptions:
            self._node.destroy_subscription(self._subscriptions["image_subscription"])
            del self._subscriptions["image_subscription"]

        self._image_display.clear_display()
        self._image_subscribe_btn.setEnabled(True)
        self._image_unsubscribe_btn.setEnabled(False)
        self._image_info_label.setText("Unsubscribed")

    @Slot()
    def _auto_refresh(self) -> None:
        if self._tab_widget.currentIndex() == 0:
            pass

    def set_node(self, node: Node) -> None:
        self._node = node
        self._refresh_topics()
        self._refresh_services()
        self._param_reconfigure.set_node(node)

    def cleanup(self) -> None:
        self._refresh_timer.stop()

        for sub in self._subscriptions.values():
            try:
                self._node.destroy_subscription(sub)
            except Exception:
                pass
        self._subscriptions.clear()

        if self._publisher:
            try:
                self._node.destroy_publisher(self._publisher)
            except Exception:
                pass

        self._param_reconfigure.cleanup()
