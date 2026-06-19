from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nectar.interface.theme import COLORS


class DroneConfigPanel(QWidget):
    """
    Compact configuration panel for drone settings.

    Signals
    -------
    config_changed : Signal
        Emitted when any configuration value changes.
    """

    config_changed = Signal()

    _MAVROS_CONN_DEFAULTS = {
        "ardupilot": "serial:///dev/ttyUSB0:921600",
        "px4": "udp://:14540@127.0.0.1:14580",
    }
    _MAVLINK_CONN_DEFAULTS = {
        "ardupilot": "tcp:127.0.0.1:5762",
        "px4": "udp:0.0.0.0:14540",
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._drone_type: str = "mavros"
        self._firmware: str = "ardupilot"
        self._config_widgets: Dict[str, QWidget] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._mavros_panel = self._create_mavros_panel()
        self._mavlink_panel = self._create_mavlink_panel()
        self._dds_panel = self._create_dds_panel()
        self._bebop_panel = self._create_bebop_panel()
        self._crazyflie_panel = self._create_crazyflie_panel()

        layout.addWidget(self._mavros_panel)
        layout.addWidget(self._mavlink_panel)
        layout.addWidget(self._dds_panel)
        layout.addWidget(self._bebop_panel)
        layout.addWidget(self._crazyflie_panel)

        self._mavlink_panel.setVisible(False)
        self._dds_panel.setVisible(False)
        self._bebop_panel.setVisible(False)
        self._crazyflie_panel.setVisible(False)

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

        # PID config file (repopulated for the active firmware in set_drone_type)
        self._mavros_pid_file = QComboBox()
        self._populate_config_combo(self._mavros_pid_file, "position_", "ardupilot")
        self._mavros_pid_file.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "PID:",
                self._mavros_pid_file,
                "PID parameters YAML (default = auto by mode)",
            )
        )

        # Setpoint config file (ArduPilot only; hidden for PX4)
        self._mavros_setpoint_file = QComboBox()
        self._populate_config_combo(self._mavros_setpoint_file, "setpoint_", "ardupilot")
        self._mavros_setpoint_file.currentIndexChanged.connect(self._on_config_changed)
        self._mavros_setpoint_container = QWidget()
        self._mavros_setpoint_container.setLayout(
            self._create_config_row(
                "Setpoint:",
                self._mavros_setpoint_file,
                "Setpoint nav YAML (default = auto by mode)",
            )
        )
        layout.addWidget(self._mavros_setpoint_container)

        # Apply setpoint params to FCU (ArduPilot only; hidden for PX4)
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
        self._mavros_apply_container = QWidget()
        self._mavros_apply_container.setLayout(apply_row)
        layout.addWidget(self._mavros_apply_container)

        return panel

    def _create_mavlink_panel(self) -> QFrame:
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

        header = QLabel("MAVLINK")
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
        self._mavlink_pose_source = QComboBox()
        self._mavlink_pose_source.addItems(["GPS (Outdoor)", "Vision (Indoor)"])
        self._mavlink_pose_source.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Pose:", self._mavlink_pose_source, "Position estimation source"
            )
        )

        # Vision pose topic (only used when Pose = Vision)
        self._mavlink_vision_topic = QComboBox()
        self._mavlink_vision_topic.setEditable(True)
        self._mavlink_vision_topic.addItems(
            ["/visual_slam/tracking/vo_pose_covariance", "/mavros/vision_pose/pose_cov"]
        )
        self._mavlink_vision_topic.currentTextChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Vision:",
                self._mavlink_vision_topic,
                "VSLAM pose topic relayed to the FCU (used when Pose = Vision)",
            )
        )

        # Connection endpoint (editable + auto-detected) with rescan button
        self._mavlink_connection = QComboBox()
        self._mavlink_connection.setEditable(True)
        self._mavlink_connection.currentTextChanged.connect(self._on_config_changed)

        conn_row = QHBoxLayout()
        conn_row.setContentsMargins(0, 0, 0, 0)
        conn_row.setSpacing(8)
        conn_lbl = QLabel("Connection:")
        conn_lbl.setProperty("secondary", True)
        conn_lbl.setFixedWidth(72)
        conn_tip = "pymavlink endpoint: tcp:host:port, udp:host:port, or serial device"
        conn_lbl.setToolTip(conn_tip)
        self._mavlink_connection.setToolTip(conn_tip)

        refresh_btn = QPushButton("\u21bb")
        refresh_btn.setFixedWidth(28)
        refresh_btn.setToolTip("Rescan available serial ports")
        refresh_btn.clicked.connect(self._refresh_mavlink_ports)

        conn_row.addWidget(conn_lbl)
        conn_row.addWidget(self._mavlink_connection, 1)
        conn_row.addWidget(refresh_btn)
        layout.addLayout(conn_row)
        self._refresh_mavlink_ports()

        # Baud (serial only)
        self._mavlink_baud = QComboBox()
        self._mavlink_baud.addItems(["921600", "115200", "57600", "1500000"])
        self._mavlink_baud.setCurrentIndex(0)
        self._mavlink_baud.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Baud:", self._mavlink_baud, "Serial baud rate (ignored for tcp/udp)"
            )
        )

        # Rangefinder checkbox
        lidar_row = QHBoxLayout()
        lidar_row.setContentsMargins(0, 0, 0, 0)
        lidar_row.setSpacing(8)
        self._mavlink_use_lidar = QCheckBox("Expect rangefinder")
        self._mavlink_use_lidar.setChecked(False)
        self._mavlink_use_lidar.setToolTip(
            "Wait for DISTANCE_SENSOR data on startup. Off = skip (default for SITL)."
        )
        self._mavlink_use_lidar.stateChanged.connect(self._on_config_changed)
        lidar_row.addWidget(self._mavlink_use_lidar)
        layout.addLayout(lidar_row)

        # PID config file (repopulated for the active firmware in set_drone_type)
        self._mavlink_pid_file = QComboBox()
        self._populate_config_combo(self._mavlink_pid_file, "position_", "ardupilot")
        self._mavlink_pid_file.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "PID:",
                self._mavlink_pid_file,
                "PID parameters YAML (default = auto by mode)",
            )
        )

        # Setpoint config file (ArduPilot only; hidden for PX4)
        self._mavlink_setpoint_file = QComboBox()
        self._populate_config_combo(self._mavlink_setpoint_file, "setpoint_", "ardupilot")
        self._mavlink_setpoint_file.currentIndexChanged.connect(self._on_config_changed)
        self._mavlink_setpoint_container = QWidget()
        self._mavlink_setpoint_container.setLayout(
            self._create_config_row(
                "Setpoint:",
                self._mavlink_setpoint_file,
                "Setpoint nav YAML (default = auto by mode)",
            )
        )
        layout.addWidget(self._mavlink_setpoint_container)

        # Apply setpoint params to FCU (ArduPilot only; hidden for PX4)
        apply_row = QHBoxLayout()
        apply_row.setContentsMargins(0, 0, 0, 0)
        apply_row.setSpacing(8)
        self._mavlink_apply_setpoint = QCheckBox("Apply setpoint params to FCU")
        self._mavlink_apply_setpoint.setChecked(False)
        self._mavlink_apply_setpoint.setToolTip(
            "Push WPNAV/GUID_OPTIONS from YAML to Pixhawk on arm. "
            "Off = use existing FCU values (default)."
        )
        self._mavlink_apply_setpoint.stateChanged.connect(self._on_config_changed)
        apply_row.addWidget(self._mavlink_apply_setpoint)
        self._mavlink_apply_container = QWidget()
        self._mavlink_apply_container.setLayout(apply_row)
        layout.addWidget(self._mavlink_apply_container)

        return panel

    @staticmethod
    def _detect_mavlink_endpoints() -> list:
        """Return SITL presets plus any detected serial ports."""
        presets = ["tcp:127.0.0.1:5762", "tcp:127.0.0.1:5760", "udp:127.0.0.1:14550"]
        try:
            from serial.tools import list_ports

            ports = [p.device for p in list_ports.comports()]
        except Exception:
            import glob

            ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        return presets + ports

    def _refresh_mavlink_ports(self) -> None:
        """Repopulate the connection list, preserving the current entry."""
        current = self._mavlink_connection.currentText().strip()
        self._mavlink_connection.blockSignals(True)
        self._mavlink_connection.clear()
        self._mavlink_connection.addItems(self._detect_mavlink_endpoints())
        self._mavlink_connection.setCurrentText(current or "tcp:127.0.0.1:5762")
        self._mavlink_connection.blockSignals(False)
        self._on_config_changed()

    def _create_dds_panel(self) -> QFrame:
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

        header = QLabel("UXRCE-DDS")
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
        self._dds_pose_source = QComboBox()
        self._dds_pose_source.addItems(["GPS (Outdoor)", "Vision (Indoor)"])
        self._dds_pose_source.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("Pose:", self._dds_pose_source, "Position estimation source")
        )

        # Micro XRCE-DDS Agent UDP port
        self._dds_agent_port = QSpinBox()
        self._dds_agent_port.setRange(1, 65535)
        self._dds_agent_port.setValue(8888)
        self._dds_agent_port.valueChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Agent port:",
                self._dds_agent_port,
                "UDP port of the MicroXRCEAgent (PX4 SITL default 8888)",
            )
        )

        # PX4 topic namespace (PX4 -n); blank = default /fmu
        self._dds_namespace = QLineEdit()
        self._dds_namespace.setPlaceholderText("(default /fmu)")
        self._dds_namespace.textChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "Namespace:",
                self._dds_namespace,
                "uXRCE-DDS topic namespace prefix (PX4 -n); blank = default",
            )
        )

        # PID config file (PX4 presets)
        self._dds_pid_file = QComboBox()
        self._populate_config_combo(self._dds_pid_file, "position_", "px4")
        self._dds_pid_file.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row(
                "PID:",
                self._dds_pid_file,
                "PID parameters YAML (default = auto by mode)",
            )
        )

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

    def _create_crazyflie_panel(self) -> QFrame:
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

        header = QLabel("CRAZYFLIE")
        header.setStyleSheet(
            f"""
            color: {COLORS.accent};
            font-weight: 600;
            font-size: 10px;
            letter-spacing: 1px;
        """
        )
        layout.addWidget(header)

        self._cf_name = QLineEdit()
        self._cf_name.setText("cf231")
        self._cf_name.setPlaceholderText("cf231")
        self._cf_name.textChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("CF Name:", self._cf_name, "Robot name in crazyflies.yaml")
        )

        self._cf_uri = QLineEdit()
        self._cf_uri.setText("radio://0/80/2M/E7E7E7E7E7")
        self._cf_uri.setPlaceholderText("radio://0/80/2M/E7E7E7E7E7")
        self._cf_uri.textChanged.connect(self._on_config_changed)
        layout.addLayout(self._create_config_row("URI:", self._cf_uri, "Crazyradio URI"))

        self._cf_backend = QComboBox()
        self._cf_backend.addItems(["cpp", "cflib", "sim"])
        self._cf_backend.setCurrentIndex(0)
        self._cf_backend.currentIndexChanged.connect(self._on_config_changed)
        layout.addLayout(
            self._create_config_row("Backend:", self._cf_backend, "Crazyswarm2 backend")
        )

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(12)

        ctrl_lbl = QLabel("Controller:")
        ctrl_lbl.setProperty("secondary", True)
        ctrl_lbl.setFixedWidth(72)
        self._cf_controller = QComboBox()
        self._cf_controller.addItems(["PID (1)", "Mellinger (2)"])
        self._cf_controller.setCurrentIndex(1)
        self._cf_controller.currentIndexChanged.connect(self._on_config_changed)

        est_lbl = QLabel("Estimator:")
        est_lbl.setProperty("secondary", True)
        self._cf_estimator = QComboBox()
        self._cf_estimator.addItems(["Complementary (1)", "Kalman (2)"])
        self._cf_estimator.setCurrentIndex(1)
        self._cf_estimator.currentIndexChanged.connect(self._on_config_changed)

        row1.addWidget(ctrl_lbl)
        row1.addWidget(self._cf_controller)
        row1.addWidget(est_lbl)
        row1.addWidget(self._cf_estimator)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(12)

        max_h_lbl = QLabel("Max H:")
        max_h_lbl.setProperty("secondary", True)
        max_h_lbl.setFixedWidth(72)
        self._cf_max_height = QLineEdit()
        self._cf_max_height.setText("3.0")
        self._cf_max_height.setPlaceholderText("3.0")
        self._cf_max_height.textChanged.connect(self._on_config_changed)

        vel_lbl = QLabel("Velocity:")
        vel_lbl.setProperty("secondary", True)
        self._cf_velocity = QLineEdit()
        self._cf_velocity.setText("0.3")
        self._cf_velocity.setPlaceholderText("0.3")
        self._cf_velocity.textChanged.connect(self._on_config_changed)

        row2.addWidget(max_h_lbl)
        row2.addWidget(self._cf_max_height)
        row2.addWidget(vel_lbl)
        row2.addWidget(self._cf_velocity)
        layout.addLayout(row2)

        mocap_row = QHBoxLayout()
        mocap_row.setContentsMargins(0, 0, 0, 0)
        mocap_row.setSpacing(8)
        self._cf_mocap = QCheckBox("Motion capture")
        self._cf_mocap.setChecked(False)
        self._cf_mocap.stateChanged.connect(self._on_config_changed)
        mocap_row.addWidget(self._cf_mocap)
        layout.addLayout(mocap_row)

        return panel

    @staticmethod
    def _config_dir(firmware: str) -> str:
        import os

        # widgets/ -> interface/ -> nectar/ -> control/<firmware>/config
        nectar_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sub = "px4" if firmware == "px4" else "ardupilot"
        return os.path.join(nectar_dir, "control", sub, "config")

    @classmethod
    def _list_config_files(cls, prefix: str, firmware: str) -> list:
        """List YAML filenames matching prefix in the firmware's config dir."""
        import glob
        import os

        files = sorted(glob.glob(os.path.join(cls._config_dir(firmware), f"{prefix}*.yaml")))
        return [os.path.basename(f) for f in files]

    @classmethod
    def _resolve_config_path(cls, filename: str, firmware: str) -> "Optional[str]":
        """Resolve a config filename to a full path, or None if empty."""
        import os

        if not filename:
            return None
        return os.path.join(cls._config_dir(firmware), filename)

    def _populate_config_combo(self, combo: QComboBox, prefix: str, firmware: str) -> None:
        """Fill a config-file combo from the firmware dir, preserving selection."""
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(default)", "")
        for name in self._list_config_files(prefix, firmware):
            combo.addItem(name, name)
        idx = combo.findData(current) if current else 0
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _on_config_changed(self) -> None:
        self.config_changed.emit()

    def set_drone_type(self, drone_type: str) -> None:
        """
        Set the active drone type and show the corresponding config panel.

        The MAVROS and MAVLink panels are shared by ArduPilot and PX4; the
        firmware is inferred from the drone type and applied to the panel
        (connection defaults, PID preset dir, firmware-specific fields).

        Parameters
        ----------
        drone_type : str
            Drone type: ``'mavros'``, ``'mavlink'``, ``'px4'``,
            ``'px4_mavlink'``, ``'px4_dds'``, ``'bebop'``, or ``'crazyflie'``.
        """
        self._drone_type = drone_type.lower()
        self._firmware = "px4" if self._drone_type.startswith("px4") else "ardupilot"

        is_mavros = self._drone_type in ("mavros", "px4")
        is_mavlink = self._drone_type in ("mavlink", "px4_mavlink")

        self._mavros_panel.setVisible(is_mavros)
        self._mavlink_panel.setVisible(is_mavlink)
        self._dds_panel.setVisible(self._drone_type == "px4_dds")
        self._bebop_panel.setVisible(self._drone_type == "bebop")
        self._crazyflie_panel.setVisible(self._drone_type == "crazyflie")

        if is_mavros:
            self._apply_mavros_firmware(self._firmware)
        elif is_mavlink:
            self._apply_mavlink_firmware(self._firmware)

    def _apply_mavros_firmware(self, firmware: str) -> None:
        """Adapt the shared MAVROS panel to ArduPilot or PX4."""
        defaults = self._MAVROS_CONN_DEFAULTS
        current = self._mavros_connection.text().strip()
        if not current or current in defaults.values():
            self._mavros_connection.setText(defaults[firmware])
        self._mavros_connection.setPlaceholderText(defaults[firmware])

        self._populate_config_combo(self._mavros_pid_file, "position_", firmware)

        is_ardupilot = firmware == "ardupilot"
        self._mavros_setpoint_container.setVisible(is_ardupilot)
        self._mavros_apply_container.setVisible(is_ardupilot)

    def _apply_mavlink_firmware(self, firmware: str) -> None:
        """Adapt the shared MAVLink panel to ArduPilot or PX4."""
        defaults = self._MAVLINK_CONN_DEFAULTS
        current = self._mavlink_connection.currentText().strip()
        if not current or current in defaults.values():
            self._mavlink_connection.setCurrentText(defaults[firmware])

        self._populate_config_combo(self._mavlink_pid_file, "position_", firmware)

        is_ardupilot = firmware == "ardupilot"
        self._mavlink_setpoint_container.setVisible(is_ardupilot)
        self._mavlink_apply_container.setVisible(is_ardupilot)

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration as dictionary.

        Returns
        -------
        Dict[str, Any]
            Configuration values for current drone type.
        """
        if self._drone_type in ("mavros", "px4"):
            return self._get_mavros_config()
        if self._drone_type in ("mavlink", "px4_mavlink"):
            return self._get_mavlink_config()
        if self._drone_type == "px4_dds":
            return self._get_dds_config()
        if self._drone_type == "crazyflie":
            return self._get_crazyflie_config()
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
            or self._MAVROS_CONN_DEFAULTS[self._firmware],
            "pid_config_file": self._resolve_config_path(
                self._mavros_pid_file.currentData(), self._firmware
            ),
            "setpoint_config_file": self._resolve_config_path(
                self._mavros_setpoint_file.currentData(), self._firmware
            ),
            "apply_setpoint_params": self._mavros_apply_setpoint.isChecked(),
        }

    def _get_mavlink_config(self) -> Dict[str, Any]:
        from nectar.control import PoseSource

        pose_source_map = {
            0: PoseSource.GPS,
            1: PoseSource.VISION,
        }

        def _int_or(text: str, default: int) -> int:
            try:
                return int(text.strip())
            except (ValueError, AttributeError):
                return default

        return {
            "pose_source": pose_source_map.get(
                self._mavlink_pose_source.currentIndex(), PoseSource.GPS
            ),
            "use_lidar": self._mavlink_use_lidar.isChecked(),
            "vision_pose_topic": self._mavlink_vision_topic.currentText().strip()
            or "/visual_slam/tracking/vo_pose_covariance",
            "connection_string": self._mavlink_connection.currentText().strip()
            or self._MAVLINK_CONN_DEFAULTS[self._firmware],
            "baud": _int_or(self._mavlink_baud.currentText(), 921600),
            "pid_config_file": self._resolve_config_path(
                self._mavlink_pid_file.currentData(), self._firmware
            ),
            "setpoint_config_file": self._resolve_config_path(
                self._mavlink_setpoint_file.currentData(), self._firmware
            ),
            "apply_setpoint_params": self._mavlink_apply_setpoint.isChecked(),
        }

    def _get_dds_config(self) -> Dict[str, Any]:
        from nectar.control import PoseSource

        pose_source_map = {
            0: PoseSource.GPS,
            1: PoseSource.VISION,
        }

        return {
            "pose_source": pose_source_map.get(
                self._dds_pose_source.currentIndex(), PoseSource.GPS
            ),
            "agent_port": self._dds_agent_port.value(),
            "px4_namespace": self._dds_namespace.text().strip(),
            "pid_config_file": self._resolve_config_path(self._dds_pid_file.currentData(), "px4"),
        }

    def _get_bebop_config(self) -> Dict[str, Any]:
        return {
            "ip": self._bebop_ip.text().strip() or "192.168.42.1",
            "namespace": self._bebop_namespace.text().strip() or "bebop",
        }

    def _get_crazyflie_config(self) -> Dict[str, Any]:
        def _float_or(text: str, default: float) -> float:
            try:
                return float(text.strip())
            except (ValueError, AttributeError):
                return default

        return {
            "cf_name": self._cf_name.text().strip() or "cf231",
            "uri": self._cf_uri.text().strip() or "radio://0/80/2M/E7E7E7E7E7",
            "backend": self._cf_backend.currentText(),
            "controller": self._cf_controller.currentIndex() + 1,
            "estimator": self._cf_estimator.currentIndex() + 1,
            "max_height": _float_or(self._cf_max_height.text(), 3.0),
            "default_velocity": _float_or(self._cf_velocity.text(), 0.3),
            "mocap": self._cf_mocap.isChecked(),
        }

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Set configuration values from dictionary.

        Parameters
        ----------
        config : Dict[str, Any]
            Configuration values to apply.
        """
        if self._drone_type in ("mavros", "px4"):
            self._set_mavros_config(config)
        elif self._drone_type in ("mavlink", "px4_mavlink"):
            self._set_mavlink_config(config)
        elif self._drone_type == "px4_dds":
            self._set_dds_config(config)
        elif self._drone_type == "crazyflie":
            self._set_crazyflie_config(config)
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

    def _set_mavlink_config(self, config: Dict[str, Any]) -> None:
        from nectar.control import PoseSource

        if "pose_source" in config:
            idx = 0 if config["pose_source"] == PoseSource.GPS else 1
            self._mavlink_pose_source.setCurrentIndex(idx)

        if "use_lidar" in config:
            self._mavlink_use_lidar.setChecked(config["use_lidar"])

        if "vision_pose_topic" in config:
            self._mavlink_vision_topic.setCurrentText(config["vision_pose_topic"])

        if "connection_string" in config:
            self._mavlink_connection.setCurrentText(config["connection_string"])

        if "baud" in config:
            idx = self._mavlink_baud.findText(str(config["baud"]))
            if idx >= 0:
                self._mavlink_baud.setCurrentIndex(idx)

        if "pid_config_file" in config and config["pid_config_file"]:
            import os

            name = os.path.basename(config["pid_config_file"])
            idx = self._mavlink_pid_file.findData(name)
            if idx >= 0:
                self._mavlink_pid_file.setCurrentIndex(idx)

        if "setpoint_config_file" in config and config["setpoint_config_file"]:
            import os

            name = os.path.basename(config["setpoint_config_file"])
            idx = self._mavlink_setpoint_file.findData(name)
            if idx >= 0:
                self._mavlink_setpoint_file.setCurrentIndex(idx)

        if "apply_setpoint_params" in config:
            self._mavlink_apply_setpoint.setChecked(config["apply_setpoint_params"])

    def _set_dds_config(self, config: Dict[str, Any]) -> None:
        from nectar.control import PoseSource

        if "pose_source" in config:
            idx = 0 if config["pose_source"] == PoseSource.GPS else 1
            self._dds_pose_source.setCurrentIndex(idx)
        if "agent_port" in config:
            self._dds_agent_port.setValue(int(config["agent_port"]))
        if "px4_namespace" in config:
            self._dds_namespace.setText(config["px4_namespace"])
        if "pid_config_file" in config and config["pid_config_file"]:
            import os

            name = os.path.basename(config["pid_config_file"])
            idx = self._dds_pid_file.findData(name)
            if idx >= 0:
                self._dds_pid_file.setCurrentIndex(idx)

    def _set_bebop_config(self, config: Dict[str, Any]) -> None:
        if "ip" in config:
            self._bebop_ip.setText(config["ip"])

        if "namespace" in config:
            self._bebop_namespace.setText(config["namespace"])

    def _set_crazyflie_config(self, config: Dict[str, Any]) -> None:
        if "cf_name" in config:
            self._cf_name.setText(config["cf_name"])
        if "uri" in config:
            self._cf_uri.setText(config["uri"])
        if "backend" in config:
            idx = self._cf_backend.findText(config["backend"])
            if idx >= 0:
                self._cf_backend.setCurrentIndex(idx)
        if "controller" in config:
            self._cf_controller.setCurrentIndex(max(0, config["controller"] - 1))
        if "estimator" in config:
            self._cf_estimator.setCurrentIndex(max(0, config["estimator"] - 1))
        if "max_height" in config:
            self._cf_max_height.setText(str(config["max_height"]))
        if "default_velocity" in config:
            self._cf_velocity.setText(str(config["default_velocity"]))
        if "mocap" in config:
            self._cf_mocap.setChecked(config["mocap"])

    def create_config_object(self):
        """
        Create a config dataclass instance from current settings.

        Returns
        -------
        DroneConfig
            A config dataclass for the current drone type: ``MavrosConfig``,
            ``Px4MavrosConfig``, ``MavlinkConfig``, ``Px4MavlinkConfig``,
            ``Px4DdsConfig``, ``BebopConfig``, or ``CrazyflieConfig``.
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
        elif self._drone_type == "px4":
            from nectar.control import Px4MavrosConfig

            # PX4 has no WPNAV/setpoint params; the panel defaults the connection
            # to the PX4 offboard endpoint, so it can be passed through directly.
            return Px4MavrosConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                expect_lidar=config_dict["use_lidar"],
                lidar_topic=config_dict["lidar_topic"],
                pid_config_file=config_dict["pid_config_file"],
                connection_string=config_dict["connection_string"],
            )
        elif self._drone_type == "mavlink":
            from nectar.control import MavlinkConfig

            return MavlinkConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                expect_lidar=config_dict["use_lidar"],
                vision_pose_topic=config_dict["vision_pose_topic"],
                connection_string=config_dict["connection_string"],
                baud=config_dict["baud"],
                pid_config_file=config_dict["pid_config_file"],
                setpoint_config_file=config_dict["setpoint_config_file"],
                apply_setpoint_params=config_dict["apply_setpoint_params"],
            )
        elif self._drone_type == "px4_mavlink":
            from nectar.control import Px4MavlinkConfig

            return Px4MavlinkConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                expect_lidar=config_dict["use_lidar"],
                vision_pose_topic=config_dict["vision_pose_topic"],
                connection_string=config_dict["connection_string"],
                baud=config_dict["baud"],
                pid_config_file=config_dict["pid_config_file"],
            )
        elif self._drone_type == "px4_dds":
            from nectar.control import Px4DdsConfig

            return Px4DdsConfig(
                start_driver=False,
                pose_source=config_dict["pose_source"],
                pid_config_file=config_dict["pid_config_file"],
                agent_port=config_dict["agent_port"],
                px4_namespace=config_dict["px4_namespace"],
            )
        elif self._drone_type == "crazyflie":
            from nectar.control import CrazyflieConfig

            return CrazyflieConfig(
                start_driver=False,
                cf_name=config_dict["cf_name"],
                uri=config_dict["uri"],
                backend=config_dict["backend"],
                controller=config_dict["controller"],
                estimator=config_dict["estimator"],
                max_height=config_dict["max_height"],
                default_velocity=config_dict["default_velocity"],
                mocap=config_dict["mocap"],
            )
        else:
            from nectar.control import BebopConfig

            return BebopConfig(
                start_driver=False,
                ip=config_dict["ip"],
                namespace=config_dict["namespace"],
            )
