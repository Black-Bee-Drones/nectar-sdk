from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QFormLayout,
)
from PySide6.QtCore import Signal


class DroneConfigPanel(QWidget):
    """
    Configuration panel for drone settings.

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
        layout.setSpacing(8)

        self._mavros_panel = self._create_mavros_panel()
        self._bebop_panel = self._create_bebop_panel()

        layout.addWidget(self._mavros_panel)
        layout.addWidget(self._bebop_panel)

        self._bebop_panel.setVisible(False)

    def _create_mavros_panel(self) -> QGroupBox:
        group = QGroupBox("Mavros Configuration")
        layout = QFormLayout(group)
        layout.setSpacing(8)

        self._mavros_pose_source = QComboBox()
        self._mavros_pose_source.addItems(["GPS (Outdoor)", "Vision (Indoor)"])
        self._mavros_pose_source.currentIndexChanged.connect(self._on_config_changed)
        layout.addRow("Pose Source:", self._mavros_pose_source)

        self._mavros_nav_strategy = QComboBox()
        self._mavros_nav_strategy.addItems(["PID", "Setpoint"])
        self._mavros_nav_strategy.currentIndexChanged.connect(self._on_config_changed)
        layout.addRow("Navigation:", self._mavros_nav_strategy)

        self._mavros_use_lidar = QCheckBox()
        self._mavros_use_lidar.setChecked(True)
        self._mavros_use_lidar.stateChanged.connect(self._on_config_changed)
        layout.addRow("Use LiDAR:", self._mavros_use_lidar)

        self._mavros_connection = QLineEdit()
        self._mavros_connection.setText("serial:///dev/ttyUSB0:921600")
        self._mavros_connection.setPlaceholderText("serial:///dev/ttyUSB0:921600")
        self._mavros_connection.textChanged.connect(self._on_config_changed)
        layout.addRow("Connection:", self._mavros_connection)

        return group

    def _create_bebop_panel(self) -> QGroupBox:
        group = QGroupBox("Bebop Configuration")
        layout = QFormLayout(group)
        layout.setSpacing(8)

        self._bebop_ip = QLineEdit()
        self._bebop_ip.setText("192.168.42.1")
        self._bebop_ip.setPlaceholderText("192.168.42.1")
        self._bebop_ip.textChanged.connect(self._on_config_changed)
        layout.addRow("IP Address:", self._bebop_ip)

        self._bebop_namespace = QLineEdit()
        self._bebop_namespace.setText("bebop")
        self._bebop_namespace.setPlaceholderText("bebop")
        self._bebop_namespace.textChanged.connect(self._on_config_changed)
        layout.addRow("Namespace:", self._bebop_namespace)

        return group

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
        from mirela_sdk.control import PoseSource, NavigationStrategy

        pose_source_map = {
            0: PoseSource.GPS,
            1: PoseSource.VISION,
        }
        nav_strategy_map = {
            0: NavigationStrategy.PID,
            1: NavigationStrategy.SETPOINT,
        }

        return {
            "pose_source": pose_source_map.get(
                self._mavros_pose_source.currentIndex(), PoseSource.GPS
            ),
            "default_nav_strategy": nav_strategy_map.get(
                self._mavros_nav_strategy.currentIndex(), NavigationStrategy.PID
            ),
            "use_lidar": self._mavros_use_lidar.isChecked(),
            "connection_string": self._mavros_connection.text().strip()
            or "serial:///dev/ttyUSB0:921600",
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
        from mirela_sdk.control import PoseSource, NavigationStrategy

        if "pose_source" in config:
            pose_source = config["pose_source"]
            if pose_source == PoseSource.GPS:
                self._mavros_pose_source.setCurrentIndex(0)
            else:
                self._mavros_pose_source.setCurrentIndex(1)

        if "default_nav_strategy" in config:
            strategy = config["default_nav_strategy"]
            if strategy == NavigationStrategy.PID:
                self._mavros_nav_strategy.setCurrentIndex(0)
            else:
                self._mavros_nav_strategy.setCurrentIndex(1)

        if "use_lidar" in config:
            self._mavros_use_lidar.setChecked(config["use_lidar"])

        if "connection_string" in config:
            self._mavros_connection.setText(config["connection_string"])

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
            from mirela_sdk.control import MavrosConfig

            return MavrosConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                default_nav_strategy=config_dict["default_nav_strategy"],
                use_lidar=config_dict["use_lidar"],
                connection_string=config_dict["connection_string"],
            )
        else:
            from mirela_sdk.control import BebopConfig

            return BebopConfig(
                start_driver=False,
                ip=config_dict["ip"],
                namespace=config_dict["namespace"],
            )
