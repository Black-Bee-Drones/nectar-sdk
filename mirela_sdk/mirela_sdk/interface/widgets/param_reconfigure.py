from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QFrame,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QSplitter,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer

from rclpy.node import Node
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.srv import ListParameters, GetParameters, SetParameters

from mirela_sdk.interface.theme import COLORS


class ParamType(Enum):
    """ROS2 parameter types mapped to editor types."""

    BOOL = 1
    INTEGER = 2
    DOUBLE = 3
    STRING = 4
    BYTE_ARRAY = 5
    BOOL_ARRAY = 6
    INTEGER_ARRAY = 7
    DOUBLE_ARRAY = 8
    STRING_ARRAY = 9
    NOT_SET = 0


@dataclass
class ParameterInfo:
    """Container for parameter metadata and value."""

    name: str
    type: ParamType
    value: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None


class ParameterEditor(QWidget):
    """
    Base parameter editor widget.

    Creates appropriate editor controls based on parameter type.
    Emits valueChanged signal when user modifies the value.

    Parameters
    ----------
    param : ParameterInfo
        Parameter metadata and initial value.
    parent : QWidget, optional
        Parent widget.

    Signals
    -------
    valueChanged : Signal(str, Any)
        Emitted with parameter name and new value when changed.
    """

    valueChanged = Signal(str, object)

    def __init__(self, param: ParameterInfo, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._param = param
        self._updating = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._name_label = QLabel(self._get_short_name(param.name))
        self._name_label.setFixedWidth(150)
        self._name_label.setToolTip(param.name)
        if param.description:
            self._name_label.setToolTip(f"{param.name}\n\n{param.description}")

        layout.addWidget(self._name_label)

        self._editor = self._create_editor()
        layout.addWidget(self._editor, 1)

        self._value_display = QLabel()
        self._value_display.setFixedWidth(80)
        self._value_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._value_display.setStyleSheet(f"color: {COLORS.accent}; font-weight: 500;")
        layout.addWidget(self._value_display)

        self._update_display()

    def _get_short_name(self, full_name: str) -> str:
        """Extract short parameter name from full path."""
        parts = full_name.split(".")
        return parts[-1] if parts else full_name

    def _create_editor(self) -> QWidget:
        """Create appropriate editor widget based on parameter type."""
        param = self._param

        if param.type == ParamType.BOOL:
            editor = QCheckBox()
            editor.setChecked(bool(param.value))
            editor.stateChanged.connect(self._on_bool_changed)
            return editor

        elif param.type == ParamType.INTEGER:
            editor = QWidget()
            layout = QHBoxLayout(editor)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            self._int_slider = QSlider(Qt.Horizontal)
            self._int_spin = QSpinBox()

            min_val = int(param.min_value) if param.min_value is not None else -1000
            max_val = int(param.max_value) if param.max_value is not None else 1000
            current = int(param.value) if param.value is not None else 0

            self._int_slider.setRange(min_val, max_val)
            self._int_slider.setValue(current)
            self._int_spin.setRange(min_val, max_val)
            self._int_spin.setValue(current)

            self._int_slider.valueChanged.connect(self._on_int_slider_changed)
            self._int_spin.valueChanged.connect(self._on_int_spin_changed)

            layout.addWidget(self._int_slider, 1)
            layout.addWidget(self._int_spin)
            return editor

        elif param.type == ParamType.DOUBLE:
            editor = QWidget()
            layout = QHBoxLayout(editor)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            self._double_slider = QSlider(Qt.Horizontal)
            self._double_spin = QDoubleSpinBox()

            min_val = param.min_value if param.min_value is not None else -100.0
            max_val = param.max_value if param.max_value is not None else 100.0
            step = param.step if param.step is not None else 0.01
            current = float(param.value) if param.value is not None else 0.0

            self._double_scale = 1000
            self._double_slider.setRange(
                int(min_val * self._double_scale), int(max_val * self._double_scale)
            )
            self._double_slider.setValue(int(current * self._double_scale))

            self._double_spin.setRange(min_val, max_val)
            self._double_spin.setSingleStep(step)
            self._double_spin.setDecimals(4)
            self._double_spin.setValue(current)

            self._double_slider.valueChanged.connect(self._on_double_slider_changed)
            self._double_spin.valueChanged.connect(self._on_double_spin_changed)

            layout.addWidget(self._double_slider, 1)
            layout.addWidget(self._double_spin)
            return editor

        elif param.type == ParamType.STRING:
            editor = QLineEdit()
            editor.setText(str(param.value) if param.value else "")
            editor.editingFinished.connect(self._on_string_changed)
            return editor

        else:
            editor = QLineEdit()
            editor.setText(str(param.value) if param.value else "")
            editor.setReadOnly(True)
            editor.setStyleSheet(f"color: {COLORS.text_muted};")
            return editor

    def _on_bool_changed(self, state: int) -> None:
        if not self._updating:
            value = state == Qt.Checked
            self._param.value = value
            self._update_display()
            self.valueChanged.emit(self._param.name, value)

    def _on_int_slider_changed(self, value: int) -> None:
        if not self._updating:
            self._updating = True
            self._int_spin.setValue(value)
            self._param.value = value
            self._update_display()
            self.valueChanged.emit(self._param.name, value)
            self._updating = False

    def _on_int_spin_changed(self, value: int) -> None:
        if not self._updating:
            self._updating = True
            self._int_slider.setValue(value)
            self._param.value = value
            self._update_display()
            self.valueChanged.emit(self._param.name, value)
            self._updating = False

    def _on_double_slider_changed(self, value: int) -> None:
        if not self._updating:
            self._updating = True
            real_value = value / self._double_scale
            self._double_spin.setValue(real_value)
            self._param.value = real_value
            self._update_display()
            self.valueChanged.emit(self._param.name, real_value)
            self._updating = False

    def _on_double_spin_changed(self, value: float) -> None:
        if not self._updating:
            self._updating = True
            self._double_slider.setValue(int(value * self._double_scale))
            self._param.value = value
            self._update_display()
            self.valueChanged.emit(self._param.name, value)
            self._updating = False

    def _on_string_changed(self) -> None:
        if not self._updating:
            value = self._editor.text()
            self._param.value = value
            self._update_display()
            self.valueChanged.emit(self._param.name, value)

    def _update_display(self) -> None:
        """Update the value display label."""
        value = self._param.value
        if isinstance(value, bool):
            self._value_display.setText("true" if value else "false")
        elif isinstance(value, float):
            self._value_display.setText(f"{value:.4f}")
        elif isinstance(value, int):
            self._value_display.setText(str(value))
        else:
            display = str(value)[:15]
            if len(str(value)) > 15:
                display += "..."
            self._value_display.setText(display)

    def set_value(self, value: Any) -> None:
        """Update editor with new value without emitting signal."""
        self._updating = True
        self._param.value = value

        if self._param.type == ParamType.BOOL:
            self._editor.setChecked(bool(value))
        elif self._param.type == ParamType.INTEGER:
            self._int_slider.setValue(int(value))
            self._int_spin.setValue(int(value))
        elif self._param.type == ParamType.DOUBLE:
            self._double_slider.setValue(int(float(value) * self._double_scale))
            self._double_spin.setValue(float(value))
        elif self._param.type == ParamType.STRING:
            self._editor.setText(str(value))

        self._update_display()
        self._updating = False


class ParameterGroupWidget(QGroupBox):
    """
    Collapsible group of parameter editors.

    Parameters
    ----------
    group_name : str
        Display name for the group.
    parent : QWidget, optional
        Parent widget.

    Signals
    -------
    parameterChanged : Signal(str, Any)
        Emitted when any parameter in the group changes.
    """

    parameterChanged = Signal(str, object)

    def __init__(self, group_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(group_name, parent)
        self._editors: Dict[str, ParameterEditor] = {}

        self.setCheckable(True)
        self.setChecked(True)
        self.toggled.connect(self._on_toggled)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 8, 8)
        self._content_layout.setSpacing(2)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        self._content.setVisible(checked)

    def add_parameter(self, param: ParameterInfo) -> None:
        """Add a parameter editor to the group."""
        editor = ParameterEditor(param)
        editor.valueChanged.connect(self.parameterChanged.emit)
        self._editors[param.name] = editor
        self._content_layout.addWidget(editor)

    def update_parameter(self, name: str, value: Any) -> None:
        """Update a parameter value without emitting signal."""
        if name in self._editors:
            self._editors[name].set_value(value)


class ParameterReconfigureWidget(QWidget):
    """
    Dynamic parameter reconfigure widget for ROS2 nodes.

    Provides RQT-style parameter editing with automatic type detection,
    appropriate editor widgets, and live parameter updates.

    Parameters
    ----------
    node : Node, optional
        ROS2 node for parameter service calls.
    parent : QWidget, optional
        Parent widget.

    Signals
    -------
    parameterSet : Signal(str, str, Any)
        Emitted when a parameter is successfully set (node, param_name, value).
    errorOccurred : Signal(str)
        Emitted when an error occurs.
    """

    parameterSet = Signal(str, str, object)
    errorOccurred = Signal(str)

    def __init__(
        self, node: Optional[Node] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._node = node
        self._current_node: Optional[str] = None
        self._parameters: Dict[str, ParameterInfo] = {}
        self._groups: Dict[str, ParameterGroupWidget] = {}
        self._param_clients: Dict[str, Any] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._create_node_panel()
        right_panel = self._create_params_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 750])

        layout.addWidget(splitter)

    def _create_node_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Nodes"))

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh_nodes)
        header_layout.addWidget(self._refresh_btn)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter nodes...")
        self._filter_input.textChanged.connect(self._filter_nodes)

        self._node_list = QListWidget()
        self._node_list.setAlternatingRowColors(True)
        self._node_list.itemClicked.connect(self._on_node_selected)

        layout.addLayout(header_layout)
        layout.addWidget(self._filter_input)
        layout.addWidget(self._node_list, 1)

        return panel

    def _create_params_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()

        self._node_label = QLabel("Select a node to configure parameters")
        self._node_label.setProperty("header", True)
        header_layout.addWidget(self._node_label, 1)

        self._param_filter = QLineEdit()
        self._param_filter.setPlaceholderText("Filter parameters...")
        self._param_filter.setFixedWidth(200)
        self._param_filter.textChanged.connect(self._filter_parameters)
        self._param_filter.setVisible(False)
        header_layout.addWidget(self._param_filter)

        self._reload_btn = QPushButton("Reload")
        self._reload_btn.clicked.connect(self._reload_parameters)
        self._reload_btn.setVisible(False)
        header_layout.addWidget(self._reload_btn)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._params_container = QWidget()
        self._params_layout = QVBoxLayout(self._params_container)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(8)
        self._params_layout.addStretch()

        self._scroll.setWidget(self._params_container)

        self._status_label = QLabel()
        self._status_label.setProperty("secondary", True)
        self._status_label.setAlignment(Qt.AlignRight)

        layout.addLayout(header_layout)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._status_label)

        return panel

    def set_node(self, node: Node) -> None:
        """Set the ROS2 node for service calls."""
        self._node = node
        self._refresh_nodes()

    @Slot()
    def _refresh_nodes(self) -> None:
        """Refresh the list of available nodes."""
        if not self._node:
            return

        self._node_list.clear()

        try:
            nodes = self._node.get_node_names_and_namespaces()
            for node_name, namespace in sorted(nodes):
                full_name = (
                    f"{namespace}/{node_name}" if namespace != "/" else f"/{node_name}"
                )
                full_name = full_name.replace("//", "/")
                item = QListWidgetItem(full_name)
                self._node_list.addItem(item)
        except Exception as e:
            self.errorOccurred.emit(f"Failed to get node list: {e}")

    @Slot(str)
    def _filter_nodes(self, text: str) -> None:
        """Filter node list by search text."""
        text = text.lower()
        for i in range(self._node_list.count()):
            item = self._node_list.item(i)
            item.setHidden(text not in item.text().lower())

    @Slot(QListWidgetItem)
    def _on_node_selected(self, item: QListWidgetItem) -> None:
        """Handle node selection and load its parameters."""
        node_name = item.text()
        self._current_node = node_name
        self._node_label.setText(f"Parameters: {node_name}")
        self._param_filter.setVisible(True)
        self._reload_btn.setVisible(True)
        self._load_parameters(node_name)

    def _load_parameters(self, node_name: str) -> None:
        """Load parameters from the selected node."""
        if not self._node:
            return

        self._clear_parameters()
        self._status_label.setText("Loading parameters...")

        try:
            self._list_and_load_params(node_name)
        except Exception as e:
            self.errorOccurred.emit(f"Failed to load parameters: {e}")
            self._status_label.setText(f"Error: {e}")

    def _list_and_load_params(self, node_name: str) -> None:
        """List and load parameters using ROS2 parameter services."""
        parts = node_name.strip("/").split("/")
        if len(parts) >= 2:
            namespace = "/" + "/".join(parts[:-1])
            name = parts[-1]
        else:
            namespace = "/"
            name = parts[0] if parts else node_name.strip("/")

        service_name = f"{node_name}/list_parameters"
        if service_name.startswith("//"):
            service_name = service_name[1:]

        if service_name not in self._param_clients:
            client = self._node.create_client(ListParameters, service_name)
            self._param_clients[service_name] = client
        else:
            client = self._param_clients[service_name]

        if not client.wait_for_service(timeout_sec=1.0):
            self._status_label.setText("Parameter service not available")
            return

        request = ListParameters.Request()
        future = client.call_async(request)

        QTimer.singleShot(100, lambda: self._handle_list_response(future, node_name))

    def _handle_list_response(self, future, node_name: str) -> None:
        """Handle list_parameters response."""
        if not future.done():
            QTimer.singleShot(50, lambda: self._handle_list_response(future, node_name))
            return

        try:
            result = future.result()
            param_names = list(result.result.names)

            if not param_names:
                self._status_label.setText("No parameters found")
                return

            self._get_parameter_values(node_name, param_names)

        except Exception as e:
            self.errorOccurred.emit(f"Failed to list parameters: {e}")
            self._status_label.setText(f"Error: {e}")

    def _get_parameter_values(self, node_name: str, param_names: List[str]) -> None:
        """Get values for all parameters."""
        service_name = f"{node_name}/get_parameters"
        if service_name.startswith("//"):
            service_name = service_name[1:]

        if service_name not in self._param_clients:
            client = self._node.create_client(GetParameters, service_name)
            self._param_clients[service_name] = client
        else:
            client = self._param_clients[service_name]

        if not client.wait_for_service(timeout_sec=1.0):
            self._status_label.setText("Get parameters service not available")
            return

        request = GetParameters.Request()
        request.names = param_names
        future = client.call_async(request)

        QTimer.singleShot(
            100, lambda: self._handle_get_response(future, node_name, param_names)
        )

    def _handle_get_response(
        self, future, node_name: str, param_names: List[str]
    ) -> None:
        """Handle get_parameters response and create editors."""
        if not future.done():
            QTimer.singleShot(
                50, lambda: self._handle_get_response(future, node_name, param_names)
            )
            return

        try:
            result = future.result()
            parameters = []

            for name, value in zip(param_names, result.values):
                param_type, param_value = self._convert_parameter_value(value)
                param_info = ParameterInfo(
                    name=name,
                    type=param_type,
                    value=param_value,
                    min_value=self._get_default_min(param_type),
                    max_value=self._get_default_max(param_type),
                )
                parameters.append(param_info)

            self._create_parameter_editors(parameters)
            self._status_label.setText(f"{len(parameters)} parameters loaded")

        except Exception as e:
            self.errorOccurred.emit(f"Failed to get parameters: {e}")
            self._status_label.setText(f"Error: {e}")

    def _convert_parameter_value(self, value) -> Tuple[ParamType, Any]:
        """Convert ROS2 parameter value to Python type."""
        if value.type == ParameterType.PARAMETER_BOOL:
            return ParamType.BOOL, value.bool_value
        elif value.type == ParameterType.PARAMETER_INTEGER:
            return ParamType.INTEGER, value.integer_value
        elif value.type == ParameterType.PARAMETER_DOUBLE:
            return ParamType.DOUBLE, value.double_value
        elif value.type == ParameterType.PARAMETER_STRING:
            return ParamType.STRING, value.string_value
        elif value.type == ParameterType.PARAMETER_BYTE_ARRAY:
            return ParamType.BYTE_ARRAY, list(value.byte_array_value)
        elif value.type == ParameterType.PARAMETER_BOOL_ARRAY:
            return ParamType.BOOL_ARRAY, list(value.bool_array_value)
        elif value.type == ParameterType.PARAMETER_INTEGER_ARRAY:
            return ParamType.INTEGER_ARRAY, list(value.integer_array_value)
        elif value.type == ParameterType.PARAMETER_DOUBLE_ARRAY:
            return ParamType.DOUBLE_ARRAY, list(value.double_array_value)
        elif value.type == ParameterType.PARAMETER_STRING_ARRAY:
            return ParamType.STRING_ARRAY, list(value.string_array_value)
        else:
            return ParamType.NOT_SET, None

    def _get_default_min(self, param_type: ParamType) -> Optional[float]:
        """Get default minimum value for numeric types."""
        if param_type == ParamType.INTEGER:
            return -1000
        elif param_type == ParamType.DOUBLE:
            return -100.0
        return None

    def _get_default_max(self, param_type: ParamType) -> Optional[float]:
        """Get default maximum value for numeric types."""
        if param_type == ParamType.INTEGER:
            return 1000
        elif param_type == ParamType.DOUBLE:
            return 100.0
        return None

    def _create_parameter_editors(self, parameters: List[ParameterInfo]) -> None:
        """Create grouped parameter editors."""
        groups: Dict[str, List[ParameterInfo]] = {}

        for param in parameters:
            parts = param.name.split(".")
            if len(parts) > 1:
                group_name = parts[0]
            else:
                group_name = "General"

            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(param)

        for group_name in sorted(groups.keys()):
            group_widget = ParameterGroupWidget(group_name)
            group_widget.parameterChanged.connect(self._on_parameter_changed)

            for param in sorted(groups[group_name], key=lambda p: p.name):
                group_widget.add_parameter(param)
                self._parameters[param.name] = param

            self._groups[group_name] = group_widget
            self._params_layout.insertWidget(
                self._params_layout.count() - 1, group_widget
            )

    @Slot(str, object)
    def _on_parameter_changed(self, param_name: str, value: Any) -> None:
        """Handle parameter value change from editor."""
        if not self._node or not self._current_node:
            return

        self._set_parameter(self._current_node, param_name, value)

    def _set_parameter(self, node_name: str, param_name: str, value: Any) -> None:
        """Set a parameter on the target node."""
        service_name = f"{node_name}/set_parameters"
        if service_name.startswith("//"):
            service_name = service_name[1:]

        if service_name not in self._param_clients:
            client = self._node.create_client(SetParameters, service_name)
            self._param_clients[service_name] = client
        else:
            client = self._param_clients[service_name]

        if not client.wait_for_service(timeout_sec=0.5):
            self.errorOccurred.emit("Set parameters service not available")
            return

        from rcl_interfaces.msg import Parameter as ParameterMsg
        from rcl_interfaces.msg import ParameterValue

        param_msg = ParameterMsg()
        param_msg.name = param_name
        param_msg.value = self._create_parameter_value(value)

        request = SetParameters.Request()
        request.parameters = [param_msg]

        future = client.call_async(request)
        QTimer.singleShot(
            50, lambda: self._handle_set_response(future, param_name, value)
        )

    def _create_parameter_value(self, value: Any):
        """Create ROS2 ParameterValue from Python value."""
        from rcl_interfaces.msg import ParameterValue, ParameterType as PT

        pv = ParameterValue()

        if isinstance(value, bool):
            pv.type = PT.PARAMETER_BOOL
            pv.bool_value = value
        elif isinstance(value, int):
            pv.type = PT.PARAMETER_INTEGER
            pv.integer_value = value
        elif isinstance(value, float):
            pv.type = PT.PARAMETER_DOUBLE
            pv.double_value = value
        elif isinstance(value, str):
            pv.type = PT.PARAMETER_STRING
            pv.string_value = value
        else:
            pv.type = PT.PARAMETER_STRING
            pv.string_value = str(value)

        return pv

    def _handle_set_response(self, future, param_name: str, value: Any) -> None:
        """Handle set_parameters response."""
        if not future.done():
            QTimer.singleShot(
                50, lambda: self._handle_set_response(future, param_name, value)
            )
            return

        try:
            result = future.result()
            if result.results and result.results[0].successful:
                self._status_label.setText(f"Set {param_name}")
                self.parameterSet.emit(self._current_node, param_name, value)
            else:
                reason = result.results[0].reason if result.results else "Unknown"
                self.errorOccurred.emit(f"Failed to set {param_name}: {reason}")
                self._status_label.setText(f"Failed: {reason}")
        except Exception as e:
            self.errorOccurred.emit(f"Error setting parameter: {e}")
            self._status_label.setText(f"Error: {e}")

    @Slot(str)
    def _filter_parameters(self, text: str) -> None:
        """Filter displayed parameters by name."""
        text = text.lower()
        for group_name, group_widget in self._groups.items():
            group_visible = False
            for param_name, editor in group_widget._editors.items():
                visible = text in param_name.lower() or not text
                editor.setVisible(visible)
                if visible:
                    group_visible = True
            group_widget.setVisible(group_visible or not text)

    @Slot()
    def _reload_parameters(self) -> None:
        """Reload parameters for the current node."""
        if self._current_node:
            self._load_parameters(self._current_node)

    def _clear_parameters(self) -> None:
        """Clear all parameter editors."""
        for group in self._groups.values():
            group.deleteLater()
        self._groups.clear()
        self._parameters.clear()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._clear_parameters()
        self._destroy_clients()

    def _destroy_clients(self) -> None:
        """Destroy all ROS2 service clients."""
        if not self._node:
            self._param_clients.clear()
            return

        for service_name, client in self._param_clients.items():
            try:
                self._node.destroy_client(client)
            except Exception:
                pass
        self._param_clients.clear()
