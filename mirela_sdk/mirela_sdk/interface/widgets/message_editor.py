from typing import Optional, Dict, Any, List, Type, Tuple
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QFrame,
    QPushButton,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from mirela_sdk.interface.theme import COLORS


class MessageFieldEditor(QWidget):
    valueChanged = Signal()

    ROS_TYPE_MAP = {
        "bool": "bool",
        "int8": "int",
        "uint8": "int",
        "int16": "int",
        "uint16": "int",
        "int32": "int",
        "uint32": "int",
        "int64": "int",
        "uint64": "int",
        "float32": "float",
        "float64": "float",
        "string": "string",
        "byte": "int",
        "char": "int",
    }

    def __init__(
        self,
        msg_class: Optional[Type] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._msg_class = msg_class
        self._field_widgets: Dict[str, Any] = {}
        self._nested_editors: Dict[str, "MessageFieldEditor"] = {}
        self._array_editors: Dict[str, "_ArrayFieldEditor"] = {}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        self._content_layout.setAlignment(Qt.AlignTop)

        self._scroll_area.setWidget(self._content)
        self._layout.addWidget(self._scroll_area)

        if msg_class:
            self.set_message_class(msg_class)

    def set_message_class(self, msg_class: Type) -> None:
        self._msg_class = msg_class
        self._clear_fields()

        if msg_class is None:
            return

        try:
            fields = self._get_fields_and_types(msg_class)
            for field_name, field_type in fields.items():
                self._create_field_widget(field_name, field_type)
        except Exception:
            pass

        self._content_layout.addStretch()

    def _clear_fields(self) -> None:
        self._field_widgets.clear()
        self._nested_editors.clear()
        self._array_editors.clear()

        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _get_fields_and_types(self, msg_class: Type) -> Dict[str, str]:
        if hasattr(msg_class, "get_fields_and_field_types"):
            return msg_class.get_fields_and_field_types()
        return {}

    def _create_field_widget(self, field_name: str, field_type: str) -> None:
        is_array = field_type.startswith("sequence<") or "[" in field_type

        if is_array:
            self._create_array_field(field_name, field_type)
            return

        base_type = self._parse_type(field_type)

        if base_type in self.ROS_TYPE_MAP:
            mapped = self.ROS_TYPE_MAP[base_type]
            if mapped == "bool":
                self._create_bool_field(field_name)
            elif mapped == "int":
                self._create_int_field(field_name, base_type)
            elif mapped == "float":
                self._create_float_field(field_name)
            elif mapped == "string":
                self._create_string_field(field_name)
        else:
            self._create_nested_field(field_name, field_type)

    def _parse_type(self, field_type: str) -> str:
        if field_type.startswith("sequence<"):
            inner = field_type[9:-1]
            return inner
        if "[" in field_type:
            return field_type.split("[")[0]
        return field_type

    def _create_bool_field(self, field_name: str) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        checkbox = QCheckBox(field_name)
        checkbox.stateChanged.connect(self._on_value_changed)

        layout.addWidget(checkbox)
        layout.addStretch()

        self._field_widgets[field_name] = checkbox
        self._content_layout.addWidget(row)

    def _create_int_field(self, field_name: str, type_hint: str) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        label = QLabel(field_name)
        label.setProperty("secondary", True)
        label.setMinimumWidth(100)
        label.setMaximumWidth(150)

        spinbox = QSpinBox()
        spinbox.setMinimumWidth(100)
        spinbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if "uint" in type_hint:
            spinbox.setRange(0, 2147483647)
        else:
            spinbox.setRange(-2147483648, 2147483647)

        spinbox.valueChanged.connect(self._on_value_changed)

        layout.addWidget(label)
        layout.addWidget(spinbox, 1)

        self._field_widgets[field_name] = spinbox
        self._content_layout.addWidget(row)

    def _create_float_field(self, field_name: str) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        label = QLabel(field_name)
        label.setProperty("secondary", True)
        label.setMinimumWidth(100)
        label.setMaximumWidth(150)

        spinbox = QDoubleSpinBox()
        spinbox.setMinimumWidth(100)
        spinbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        spinbox.setRange(-1e10, 1e10)
        spinbox.setDecimals(4)
        spinbox.setSingleStep(0.1)
        spinbox.valueChanged.connect(self._on_value_changed)

        layout.addWidget(label)
        layout.addWidget(spinbox, 1)

        self._field_widgets[field_name] = spinbox
        self._content_layout.addWidget(row)

    def _create_string_field(self, field_name: str) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        label = QLabel(field_name)
        label.setProperty("secondary", True)
        label.setMinimumWidth(100)
        label.setMaximumWidth(150)

        line_edit = QLineEdit()
        line_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        line_edit.textChanged.connect(self._on_value_changed)

        layout.addWidget(label)
        layout.addWidget(line_edit, 1)

        self._field_widgets[field_name] = line_edit
        self._content_layout.addWidget(row)

    def _create_nested_field(self, field_name: str, field_type: str) -> None:
        nested_class = self._resolve_message_class(field_type)
        if nested_class is None:
            self._create_string_field(field_name)
            return

        container = _CollapsibleField(field_name)
        editor = MessageFieldEditor(nested_class)
        editor.valueChanged.connect(self._on_value_changed)
        container.set_content(editor)

        self._nested_editors[field_name] = editor
        self._content_layout.addWidget(container)

    def _create_array_field(self, field_name: str, field_type: str) -> None:
        base_type = self._parse_type(field_type)
        container = _CollapsibleField(f"{field_name} (array)")

        array_editor = _ArrayFieldEditor(base_type, self)
        array_editor.valueChanged.connect(self._on_value_changed)
        container.set_content(array_editor)

        self._array_editors[field_name] = array_editor
        self._content_layout.addWidget(container)

    def _resolve_message_class(self, type_str: str) -> Optional[Type]:
        try:
            parts = type_str.split("/")
            if len(parts) == 3:
                package, folder, msg_name = parts
                module = __import__(f"{package}.{folder}", fromlist=[msg_name])
                return getattr(module, msg_name, None)
            elif len(parts) == 2:
                package, msg_name = parts
                module = __import__(f"{package}.msg", fromlist=[msg_name])
                return getattr(module, msg_name, None)
        except Exception:
            pass
        return None

    def _on_value_changed(self) -> None:
        self.valueChanged.emit()

    def get_values(self) -> Dict[str, Any]:
        result = {}

        for field_name, widget in self._field_widgets.items():
            if isinstance(widget, QCheckBox):
                result[field_name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[field_name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                result[field_name] = widget.value()
            elif isinstance(widget, QLineEdit):
                result[field_name] = widget.text()

        for field_name, editor in self._nested_editors.items():
            result[field_name] = editor.get_values()

        for field_name, editor in self._array_editors.items():
            result[field_name] = editor.get_values()

        return result

    def set_values(self, data: Dict[str, Any]) -> None:
        if not data:
            return

        for field_name, value in data.items():
            if field_name in self._field_widgets:
                widget = self._field_widgets[field_name]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
            elif field_name in self._nested_editors:
                self._nested_editors[field_name].set_values(value)
            elif field_name in self._array_editors:
                self._array_editors[field_name].set_values(value)

    def clear_values(self) -> None:
        for widget in self._field_widgets.values():
            if isinstance(widget, QCheckBox):
                widget.setChecked(False)
            elif isinstance(widget, QSpinBox):
                widget.setValue(0)
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(0.0)
            elif isinstance(widget, QLineEdit):
                widget.clear()

        for editor in self._nested_editors.values():
            editor.clear_values()

        for editor in self._array_editors.values():
            editor.clear()


class _CollapsibleField(QWidget):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QPushButton(f"+ {title}")
        self._header.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.surface_elevated};
                color: {COLORS.text_secondary};
                border: 1px solid {COLORS.border};
                border-radius: 4px;
                padding: 6px 10px;
                text-align: left;
                font-weight: 500;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.border};
                color: {COLORS.text_primary};
            }}
        """)
        self._header.clicked.connect(self._toggle)

        self._container = QFrame()
        self._container.setStyleSheet(f"""
            QFrame {{
                border-left: 2px solid {COLORS.accent_muted};
                margin-left: 8px;
                padding-left: 8px;
            }}
        """)
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(8, 4, 0, 4)
        self._container_layout.setSpacing(0)
        self._container.setVisible(False)

        self._title = title
        layout.addWidget(self._header)
        layout.addWidget(self._container)

    def set_content(self, widget: QWidget) -> None:
        self._container_layout.addWidget(widget)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._container.setVisible(self._expanded)
        prefix = "-" if self._expanded else "+"
        self._header.setText(f"{prefix} {self._title}")


class _ArrayFieldEditor(QWidget):
    valueChanged = Signal()

    def __init__(
        self,
        element_type: str,
        parent_editor: MessageFieldEditor,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._element_type = element_type
        self._parent_editor = parent_editor
        self._items: List[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._items_layout = QVBoxLayout()
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(2)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._add_btn = QPushButton("+ Add")
        self._add_btn.setMaximumWidth(80)
        self._add_btn.clicked.connect(self._add_item)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setMaximumWidth(80)
        self._clear_btn.clicked.connect(self.clear)

        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._clear_btn)
        btn_layout.addStretch()

        layout.addLayout(self._items_layout)
        layout.addLayout(btn_layout)

    def _add_item(self) -> None:
        base = self._element_type.split("/")[-1] if "/" in self._element_type else self._element_type

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        idx = len(self._items)
        label = QLabel(f"[{idx}]")
        label.setProperty("muted", True)
        label.setFixedWidth(30)

        if base in MessageFieldEditor.ROS_TYPE_MAP:
            mapped = MessageFieldEditor.ROS_TYPE_MAP[base]
            if mapped == "bool":
                widget = QCheckBox()
                widget.stateChanged.connect(self._on_changed)
            elif mapped == "int":
                widget = QSpinBox()
                widget.setRange(-2147483648, 2147483647)
                widget.valueChanged.connect(self._on_changed)
            elif mapped == "float":
                widget = QDoubleSpinBox()
                widget.setRange(-1e10, 1e10)
                widget.setDecimals(4)
                widget.valueChanged.connect(self._on_changed)
            else:
                widget = QLineEdit()
                widget.textChanged.connect(self._on_changed)
        else:
            widget = QLineEdit()
            widget.setPlaceholderText("Enter as YAML")
            widget.textChanged.connect(self._on_changed)

        remove_btn = QPushButton("x")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS.error};
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLORS.error};
                color: {COLORS.text_primary};
                border-radius: 4px;
            }}
        """)
        remove_btn.clicked.connect(lambda: self._remove_item(row))

        row_layout.addWidget(label)
        row_layout.addWidget(widget, 1)
        row_layout.addWidget(remove_btn)

        row.widget_ref = widget
        self._items.append(row)
        self._items_layout.addWidget(row)
        self.valueChanged.emit()

    def _remove_item(self, row: QWidget) -> None:
        if row in self._items:
            self._items.remove(row)
            self._items_layout.removeWidget(row)
            row.deleteLater()
            self._update_indices()
            self.valueChanged.emit()

    def _update_indices(self) -> None:
        for i, row in enumerate(self._items):
            label = row.layout().itemAt(0).widget()
            if isinstance(label, QLabel):
                label.setText(f"[{i}]")

    def _on_changed(self) -> None:
        self.valueChanged.emit()

    def get_values(self) -> List[Any]:
        result = []
        base = self._element_type.split("/")[-1] if "/" in self._element_type else self._element_type
        mapped = MessageFieldEditor.ROS_TYPE_MAP.get(base, "string")

        for row in self._items:
            widget = row.widget_ref
            if isinstance(widget, QCheckBox):
                result.append(widget.isChecked())
            elif isinstance(widget, QSpinBox):
                result.append(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                result.append(widget.value())
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                if mapped == "string":
                    result.append(text)
                else:
                    import yaml
                    try:
                        result.append(yaml.safe_load(text))
                    except Exception:
                        result.append(text)

        return result

    def set_values(self, values: List[Any]) -> None:
        self.clear()
        if not values:
            return

        for value in values:
            self._add_item()
            row = self._items[-1]
            widget = row.widget_ref

            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QLineEdit):
                if isinstance(value, (dict, list)):
                    import yaml
                    widget.setText(yaml.dump(value, default_flow_style=True).strip())
                else:
                    widget.setText(str(value))

    def clear(self) -> None:
        for row in self._items[:]:
            self._items_layout.removeWidget(row)
            row.deleteLater()
        self._items.clear()
        self.valueChanged.emit()
