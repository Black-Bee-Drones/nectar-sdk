from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from nectar.interface.theme import COLORS


class DroneConfigPanel(QWidget):
    """
    Compact configuration panel for drone settings.

    Dynamically generates UI based on drone config dataclass fields.
    Supports Mavros and Bebop configuration types.

    Signals
    -------
    config_changed : Signal
        Emitted when any configuration value changes.
    """

    config_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._drone_type: str = "mavros"
        self._config_widgets: Dict[str, QWidget] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._mavros_panel = self._create_mavros_panel()
        self._bebop_panel = self._create_bebop_panel()

        layout.addWidget(self._mavros_panel)
        layout.addWidget(self._bebop_panel)

        self._bebop_panel.setVisible(False)

    def _create_config_row(self, label: str, widget: QWidget, tooltip: str = "") -> QHBoxLayout:
        """Create a compact horizontal config row."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(72)
        if tooltip:
            lbl.setToolTip(tooltip)
            widget.setToolTip(tooltip)

        row.addWidget(lbl)
        row.addWidget(widget, 1)
        return row

    def _create_mavros_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.surface_elevated};
                border: 1px solid {COLORS.border};
                border-radius: 4px;
                padding: 4px;
            }}
        """
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QLabel("MAVROS")
        header.setStyleSheet(
            f"""
            color: {COLORS.accent};
            font-weight: 600;
            font-size: 10px;
            letter-spacing: 1px;
        """
        )
        layout.addWidget(header)

        # Pose source
        self._mavros_pose_source = QComboBox()
        self._mavros_pose_source.addItems(["GPS (Outdoor)", "Vision (Indoor)"])
        self._mavros_pose_source.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("Pose:", self._mavros_pose_source, "Position estimation source")
        )

        # LiDAR checkbox
        lidar_row = QHBoxLayout()
        lidar_row.setContentsMargins(0, 0, 0, 0)
        lidar_row.setSpacing(8)
        self._mavros_use_lidar = QCheckBox("Use LiDAR altitude")
        self._mavros_use_lidar.setChecked(True)
        self._mavros_use_lidar.stateChanged.connect(self._on_config_changed)
        lidar_row.addWidget(self._mavros_use_lidar)
        layout.addLayout(lidar_row)

        # LiDAR topic
        self._mavros_lidar_topic = QLineEdit()
        self._mavros_lidar_topic.setText("/mavros/rangefinder/rangefinder")
        self._mavros_lidar_topic.setPlaceholderText("/mavros/rangefinder/rangefinder")
        self._mavros_lidar_topic.textChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Lidar topic:",
                self._mavros_lidar_topic,
                "ROS topic for rangefinder data",
            )
        )

        # Connection string
        self._mavros_connection = QLineEdit()
        self._mavros_connection.setText("serial:///dev/ttyUSB0:921600")
        self._mavros_connection.setPlaceholderText("serial:///dev/ttyUSB0:921600")
        self._mavros_connection.textChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("Connection:", self._mavros_connection, "FCU connection string")
        )

        # PID config file
        self._mavros_pid_file = QComboBox()
        self._mavros_pid_file.addItem("(default)", "")
        for f in self._list_config_files("position_"):
            self._mavros_pid_file.addItem(f, f)
        self._mavros_pid_file.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "PID:",
                self._mavros_pid_file,
                "PID parameters YAML (default = auto by mode)",
            )
        )

        # Setpoint config file
        self._mavros_setpoint_file = QComboBox()
        self._mavros_setpoint_file.addItem("(default)", "")
        for f in self._list_config_files("setpoint_"):
            self._mavros_setpoint_file.addItem(f, f)
        self._mavros_setpoint_file.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Setpoint:",
                self._mavros_setpoint_file,
                "Setpoint nav YAML (default = auto by mode)",
            )
        )

        # Apply setpoint params to FCU
        apply_row = QHBoxLayout()
        apply_row.setContentsMargins(0, 0, 0, 0)
        apply_row.setSpacing(8)
        self._mavros_apply_setpoint = QCheckBox("Apply setpoint params to FCU")
        self._mavros_apply_setpoint.setChecked(False)
        self._mavros_apply_setpoint.setToolTip(
            "Push WPNAV/GUID_OPTIONS from YAML to Pixhawk on arm. "
            "Off = use existing FCU values (default)."
        )
        self._mavros_apply_setpoint.stateChanged.connect(self._on_config_changed)
        apply_row.addWidget(self._mavros_apply_setpoint)
        layout.addLayout(apply_row)

        return panel

    def _create_bebop_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: {COLORS.surface_elevated};
                border: 1px solid {COLORS.border};
                border-radius: 4px;
                padding: 4px;
            }}
        """
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header = QLabel("BEBOP")
        header.setStyleSheet(
            f"""
            color: {COLORS.accent};
            font-weight: 600;
            font-size: 10px;
            letter-spacing: 1px;
        """
        )
        layout.addWidget(header)

        # IP Address
        self._bebop_ip = QLineEdit()
        self._bebop_ip.setText("192.168.42.1")
        self._bebop_ip.setPlaceholderText("192.168.42.1")
        self._bebop_ip.textChanged.connect(self._on_config_changed)
        layout.addLayout(self._create_config_row("IP:", self._bebop_ip, "Bebop drone IP address"))

        # Namespace
        self._bebop_namespace = QLineEdit()
        self._bebop_namespace.setText("bebop")
        self._bebop_namespace.setPlaceholderText("bebop")
        self._bebop_namespace.textChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("Namespace:", self._bebop_namespace, "ROS namespace for topics")
        )

        return panel

    @staticmethod
    def _mavros_config_dir() -> str:
        import os

        # widgets/ -> interface/ -> nectar/ -> control/config/mavros
        nectar_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(nectar_dir, "control", "config", "mavros")

    @classmethod
    def _list_config_files(cls, prefix: str) -> list:
        """List YAML filenames matching prefix in the mavros config dir."""
        import glob
        import os

        files = sorted(glob.glob(os.path.join(cls._mavros_config_dir(), f"{prefix}*.yaml")))
        return [os.path.basename(f) for f in files]

    @classmethod
    def _resolve_config_path(cls, filename: str) -> "Optional[str]":
        """Resolve a config filename to full path, or None if empty."""
        import os

        if not filename:
            return None
        return os.path.join(cls._mavros_config_dir(), filename)

    def _on_config_changed(self) -> None:
        self.config_changed.emit()

    def set_drone_type(self, drone_type: str) -> None:
        """
        Set the active drone type and show corresponding config panel.

        Parameters
        ----------
        drone_type : str
            Drone type ('mavros' or 'bebop').
        """
        self._drone_type = drone_type.lower()
        is_mavros = self._drone_type == "mavros"
        self._mavros_panel.setVisible(is_mavros)
        self._bebop_panel.setVisible(not is_mavros)

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration as dictionary.

        Returns
        -------
        Dict[str, Any]
            Configuration values for current drone type.
        """
        if self._drone_type == "mavros":
            return self._get_mavros_config()
        return self._get_bebop_config()

    def _get_mavros_config(self) -> Dict[str, Any]:
        from nectar.control import PoseSource

        pose_source_map = {
            0: PoseSource.GPS,
            1: PoseSource.VISION,
        }

        return {
            "pose_source": pose_source_map.get(
                self._mavros_pose_source.currentIndex(), PoseSource.GPS
            ),
            "use_lidar": self._mavros_use_lidar.isChecked(),
            "lidar_topic": self._mavros_lidar_topic.text().strip()
            or "/mavros/rangefinder/rangefinder",
            "connection_string": self._mavros_connection.text().strip()
            or "serial:///dev/ttyUSB0:921600",
            "pid_config_file": self._resolve_config_path(self._mavros_pid_file.currentData()),
            "setpoint_config_file": self._resolve_config_path(
                self._mavros_setpoint_file.currentData()
            ),
            "apply_setpoint_params": self._mavros_apply_setpoint.isChecked(),
        }

    def _get_bebop_config(self) -> Dict[str, Any]:
        return {
            "ip": self._bebop_ip.text().strip() or "192.168.42.1",
            "namespace": self._bebop_namespace.text().strip() or "bebop",
        }

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Set configuration values from dictionary.

        Parameters
        ----------
        config : Dict[str, Any]
            Configuration values to apply.
        """
        if self._drone_type == "mavros":
            self._set_mavros_config(config)
        else:
            self._set_bebop_config(config)

    def _set_mavros_config(self, config: Dict[str, Any]) -> None:
        from nectar.control import PoseSource

        if "pose_source" in config:
            pose_source = config["pose_source"]
            if pose_source == PoseSource.GPS:
                self._mavros_pose_source.setCurrentIndex(0)
            else:
                self._mavros_pose_source.setCurrentIndex(1)

        if "use_lidar" in config:
            self._mavros_use_lidar.setChecked(config["use_lidar"])

        if "lidar_topic" in config:
            self._mavros_lidar_topic.setText(config["lidar_topic"])

        if "connection_string" in config:
            self._mavros_connection.setText(config["connection_string"])

        if "pid_config_file" in config and config["pid_config_file"]:
            import os

            name = os.path.basename(config["pid_config_file"])
            idx = self._mavros_pid_file.findData(name)
            if idx >= 0:
                self._mavros_pid_file.setCurrentIndex(idx)

        if "setpoint_config_file" in config and config["setpoint_config_file"]:
            import os

            name = os.path.basename(config["setpoint_config_file"])
            idx = self._mavros_setpoint_file.findData(name)
            if idx >= 0:
                self._mavros_setpoint_file.setCurrentIndex(idx)

        if "apply_setpoint_params" in config:
            self._mavros_apply_setpoint.setChecked(config["apply_setpoint_params"])

    def _set_bebop_config(self, config: Dict[str, Any]) -> None:
        if "ip" in config:
            self._bebop_ip.setText(config["ip"])

        if "namespace" in config:
            self._bebop_namespace.setText(config["namespace"])

    def create_config_object(self):
        """
        Create a config dataclass instance from current settings.

        Returns
        -------
        MavrosConfig | BebopConfig
            Configuration object for current drone type.
        """
        config_dict = self.get_config()

        if self._drone_type == "mavros":
            from nectar.control import MavrosConfig

            return MavrosConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                expect_lidar=config_dict["use_lidar"],
                lidar_topic=config_dict["lidar_topic"],
                pid_config_file=config_dict["pid_config_file"],
                setpoint_config_file=config_dict["setpoint_config_file"],
                apply_setpoint_params=config_dict["apply_setpoint_params"],
                connection_string=config_dict["connection_string"],
            )
        else:
            from nectar.control import BebopConfig

            return BebopConfig(
                start_driver=False,
                ip=config_dict["ip"],
                namespace=config_dict["namespace"],
            )
