from typing import Optional, Dict
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QCheckBox,
    QDoubleSpinBox,
    QSplitter,
    QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject

from rclpy.node import Node

from mirela_sdk.interface.theme import COLORS
from mirela_sdk.interface.widgets import (
    StatusIndicator,
    LabeledSlider,
    KeyButton,
    DroneConfigPanel,
)


class DriverWorker(QObject):
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._action: str = ""
        self._drone_type: str = ""
        self._connection_string: str = ""
        self._ip: str = ""

    def setup_connect(
        self, drone_type: str, connection_string: str = "", ip: str = ""
    ) -> None:
        self._action = "connect"
        self._drone_type = drone_type
        self._connection_string = connection_string
        self._ip = ip

    def setup_disconnect(self, drone_type: str) -> None:
        self._action = "disconnect"
        self._drone_type = drone_type

    @Slot()
    def run(self) -> None:
        try:
            from mirela_sdk.utils.process import ProcessUtils

            if self._action == "connect":
                self._run_connect(ProcessUtils)
            else:
                self._run_disconnect(ProcessUtils)
        except Exception as e:
            self.finished.emit(False, str(e))

    def _run_connect(self, ProcessUtils) -> None:
        session_name = self._get_session_name()
        node_pattern = self._get_node_pattern()

        if ProcessUtils.is_node_running(node_pattern, timeout=2.0):
            self.finished.emit(True, "")
            return

        self.progress.emit("Starting driver...")
        driver_cmd = self._get_driver_command()

        ProcessUtils.kill_process(session_name)

        if not ProcessUtils.start_process(driver_cmd, session_name):
            self.finished.emit(False, "Failed to start driver process")
            return

        self.progress.emit("Waiting for driver...")
        if not ProcessUtils.wait_for_node(node_pattern, timeout=20.0):
            self.finished.emit(False, "Driver did not start in time")
            return

        self.finished.emit(True, "")

    def _run_disconnect(self, ProcessUtils) -> None:
        self.progress.emit("Stopping driver...")
        session_name = self._get_session_name()
        ProcessUtils.kill_process(session_name)
        self.finished.emit(True, "")

    def _get_driver_command(self) -> str:
        if self._drone_type == "mavros":
            conn = self._connection_string or "serial:///dev/ttyUSB0:921600"
            return f"ros2 launch mavros apm.launch fcu_url:={conn}"
        ip = self._ip or "192.168.42.1"
        return f"ros2 launch ros2_bebop_driver bebop_node_launch.xml ip:={ip}"

    def _get_session_name(self) -> str:
        return "mavros_node" if self._drone_type == "mavros" else "bebop_driver"

    def _get_node_pattern(self) -> str:
        return "mavros_node" if self._drone_type == "mavros" else "bebop_driver"


class DroneInstanceWorker(QObject):
    finished = Signal(bool, str)
    drone_ready = Signal(object)
    progress = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._node: Optional[Node] = None
        self._drone_type: str = ""
        self._config = None

    def setup(self, node: Node, drone_type: str, config) -> None:
        self._node = node
        self._drone_type = drone_type
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            from mirela_sdk.control import DroneFactory

            self.progress.emit("Creating drone instance...")
            drone = DroneFactory.create(self._drone_type, self._config, self._node)

            self.progress.emit("Initializing...")
            drone.connect()

            self.drone_ready.emit(drone)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class DriverStatusChecker(QObject):
    status_checked = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._drone_type: str = "mavros"
        self._enabled: bool = True

    def set_drone_type(self, drone_type: str) -> None:
        self._drone_type = drone_type

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @Slot()
    def check(self) -> None:
        if not self._enabled:
            return
        try:
            from mirela_sdk.utils.process import ProcessUtils

            pattern = "mavros_node" if self._drone_type == "mavros" else "bebop_driver"
            is_running = ProcessUtils.is_node_running(pattern, timeout=2.0)
            self.status_checked.emit(is_running)
        except Exception:
            self.status_checked.emit(False)


class ControlTab(QWidget):
    """
    Drone control tab with keyboard controls and velocity management.

    Separates driver connection from drone instance initialization:
    - Driver: Start/stop the ROS2 driver process (mavros or bebop)
    - Instance: Create/destroy drone object with configuration
    - Controls: Only enabled when both driver running AND instance initialized
    """

    KEY_MAP = {
        Qt.Key_W: ("thrust", 1),
        Qt.Key_S: ("thrust", -1),
        Qt.Key_A: ("yaw", 1),
        Qt.Key_D: ("yaw", -1),
        Qt.Key_Up: ("pitch", 1),
        Qt.Key_Down: ("pitch", -1),
        Qt.Key_Left: ("roll", 1),
        Qt.Key_Right: ("roll", -1),
    }

    def __init__(
        self, node: Optional[Node] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._node = node
        self._drone = None
        self._drone_type: str = "mavros"
        self._driver_connected: bool = False
        self._instance_initialized: bool = False
        self._controls_enabled: bool = False
        self._key_states: Dict[int, bool] = {}

        self._driver_thread: Optional[QThread] = None
        self._driver_worker: Optional[DriverWorker] = None
        self._instance_thread: Optional[QThread] = None
        self._instance_worker: Optional[DroneInstanceWorker] = None
        self._checker_thread: Optional[QThread] = None
        self._status_checker: Optional[DriverStatusChecker] = None

        self._setup_ui()
        self._setup_timers()
        self._setup_status_checker()
        self._update_ui_state()
        self.setFocusPolicy(Qt.StrongFocus)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_right_panel())
        splitter.setSizes([420, 580])

        layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)
        scroll.setMaximumWidth(480)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_connection_panel())
        layout.addWidget(self._create_status_panel())
        layout.addWidget(self._create_flight_controls())
        layout.addWidget(self._create_drone_specific_controls())
        layout.addStretch()

        scroll.setWidget(container)
        return scroll

    def _create_right_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._create_keyboard_panel(), 1)
        layout.addWidget(self._create_velocity_panel())
        layout.addWidget(self._create_telemetry_panel())

        return container

    def _create_connection_panel(self) -> QGroupBox:
        group = QGroupBox("Connection")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Drone:"))
        self._drone_combo = QComboBox()
        self._drone_combo.addItems(["Mavros", "Bebop"])
        self._drone_combo.currentTextChanged.connect(self._on_drone_type_changed)
        type_layout.addWidget(self._drone_combo, 1)
        layout.addLayout(type_layout)

        self._config_panel = DroneConfigPanel()
        self._config_panel.set_drone_type("mavros")
        layout.addWidget(self._config_panel)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background-color: {COLORS.border};")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        driver_layout = QHBoxLayout()
        driver_layout.addWidget(QLabel("Driver:"))
        self._driver_btn = QPushButton("Connect")
        self._driver_btn.setProperty("accent", True)
        self._driver_btn.setMinimumHeight(36)
        self._driver_btn.clicked.connect(self._toggle_driver)
        driver_layout.addWidget(self._driver_btn, 1)
        layout.addLayout(driver_layout)

        instance_layout = QHBoxLayout()
        instance_layout.addWidget(QLabel("Instance:"))
        self._instance_btn = QPushButton("Initialize")
        self._instance_btn.setMinimumHeight(36)
        self._instance_btn.setEnabled(False)
        self._instance_btn.clicked.connect(self._toggle_instance)
        instance_layout.addWidget(self._instance_btn, 1)
        layout.addLayout(instance_layout)

        self._progress_label = QLabel("")
        self._progress_label.setProperty("secondary", True)
        self._progress_label.setWordWrap(True)
        self._progress_label.setMinimumHeight(20)
        layout.addWidget(self._progress_label)

        return group

    def _create_status_panel(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QGridLayout(group)
        layout.setSpacing(10)

        self._status_driver = StatusIndicator("Driver", "inactive")
        self._status_instance = StatusIndicator("Instance", "inactive")
        self._status_armed = StatusIndicator("Armed", "inactive")
        self._status_mode = StatusIndicator("Mode", "inactive")

        layout.addWidget(self._status_driver, 0, 0)
        layout.addWidget(self._status_instance, 0, 1)
        layout.addWidget(self._status_armed, 1, 0)
        layout.addWidget(self._status_mode, 1, 1)

        return group

    def _create_flight_controls(self) -> QGroupBox:
        group = QGroupBox("Flight Controls")
        layout = QVBoxLayout(group)

        btn_layout = QGridLayout()
        btn_layout.setSpacing(8)

        self._enable_btn = QPushButton("Enable Controls")
        self._enable_btn.setCheckable(True)
        self._enable_btn.setEnabled(False)
        self._enable_btn.setMinimumHeight(40)
        self._enable_btn.clicked.connect(self._toggle_controls)

        self._emergency_btn = QPushButton("EMERGENCY STOP")
        self._emergency_btn.setProperty("danger", True)
        self._emergency_btn.setMinimumHeight(40)
        self._emergency_btn.setEnabled(False)
        self._emergency_btn.clicked.connect(self._emergency_stop)

        btn_layout.addWidget(self._enable_btn, 0, 0)
        btn_layout.addWidget(self._emergency_btn, 0, 1)

        layout.addLayout(btn_layout)
        return group

    def _create_drone_specific_controls(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._mavros_group = self._create_mavros_controls()
        self._bebop_group = self._create_bebop_controls()

        layout.addWidget(self._mavros_group)
        layout.addWidget(self._bebop_group)

        self._bebop_group.setVisible(False)
        return container

    def _create_mavros_controls(self) -> QGroupBox:
        group = QGroupBox("Mavros Controls")
        layout = QGridLayout(group)
        layout.setSpacing(8)

        self._arm_btn = QPushButton("Arm")
        self._arm_btn.setEnabled(False)
        self._arm_btn.clicked.connect(self._arm)

        self._disarm_btn = QPushButton("Disarm")
        self._disarm_btn.setEnabled(False)
        self._disarm_btn.clicked.connect(self._disarm)

        self._takeoff_btn = QPushButton("Takeoff")
        self._takeoff_btn.setProperty("success", True)
        self._takeoff_btn.setEnabled(False)
        self._takeoff_btn.clicked.connect(self._takeoff)

        self._land_btn = QPushButton("Land")
        self._land_btn.setEnabled(False)
        self._land_btn.clicked.connect(self._land)

        self._arm_takeoff_btn = QPushButton("Arm + Takeoff")
        self._arm_takeoff_btn.setProperty("accent", True)
        self._arm_takeoff_btn.setEnabled(False)
        self._arm_takeoff_btn.clicked.connect(self._arm_takeoff)

        alt_layout = QHBoxLayout()
        alt_layout.addWidget(QLabel("Altitude (m):"))
        self._altitude_spin = QDoubleSpinBox()
        self._altitude_spin.setRange(0.5, 10.0)
        self._altitude_spin.setValue(1.5)
        self._altitude_spin.setSingleStep(0.1)
        alt_layout.addWidget(self._altitude_spin)

        self._body_frame_check = QCheckBox("Body Frame")
        self._body_frame_check.setChecked(True)

        layout.addWidget(self._arm_btn, 0, 0)
        layout.addWidget(self._disarm_btn, 0, 1)
        layout.addWidget(self._takeoff_btn, 1, 0)
        layout.addWidget(self._land_btn, 1, 1)
        layout.addWidget(self._arm_takeoff_btn, 2, 0, 1, 2)
        layout.addLayout(alt_layout, 3, 0, 1, 2)
        layout.addWidget(self._body_frame_check, 4, 0, 1, 2)

        return group

    def _create_bebop_controls(self) -> QGroupBox:
        group = QGroupBox("Bebop Controls")
        layout = QGridLayout(group)
        layout.setSpacing(8)

        self._bebop_takeoff_btn = QPushButton("Takeoff")
        self._bebop_takeoff_btn.setProperty("success", True)
        self._bebop_takeoff_btn.setEnabled(False)
        self._bebop_takeoff_btn.clicked.connect(self._bebop_takeoff)

        self._bebop_land_btn = QPushButton("Land")
        self._bebop_land_btn.setEnabled(False)
        self._bebop_land_btn.clicked.connect(self._bebop_land)

        self._flip_btn = QPushButton("Flip...")
        self._flip_btn.setEnabled(False)
        self._flip_btn.clicked.connect(self._show_flip_menu)

        layout.addWidget(self._bebop_takeoff_btn, 0, 0)
        layout.addWidget(self._bebop_land_btn, 0, 1)
        layout.addWidget(self._flip_btn, 1, 0, 1, 2)

        return group

    def _create_keyboard_panel(self) -> QGroupBox:
        group = QGroupBox("Keyboard Controls")
        layout = QVBoxLayout(group)
        layout.setAlignment(Qt.AlignCenter)

        help_label = QLabel("WASD: Thrust/Yaw | Arrows: Pitch/Roll")
        help_label.setProperty("secondary", True)
        help_label.setAlignment(Qt.AlignCenter)

        keys_widget = QWidget()
        keys_layout = QHBoxLayout(keys_widget)
        keys_layout.setSpacing(40)
        keys_layout.setAlignment(Qt.AlignCenter)

        wasd_layout = QVBoxLayout()
        wasd_grid = QGridLayout()
        wasd_grid.setSpacing(4)

        self._key_w = KeyButton("W", Qt.Key_W)
        self._key_a = KeyButton("A", Qt.Key_A)
        self._key_s = KeyButton("S", Qt.Key_S)
        self._key_d = KeyButton("D", Qt.Key_D)

        wasd_grid.addWidget(self._key_w, 0, 1)
        wasd_grid.addWidget(self._key_a, 1, 0)
        wasd_grid.addWidget(self._key_s, 1, 1)
        wasd_grid.addWidget(self._key_d, 1, 2)

        wasd_label = QLabel("Thrust / Yaw")
        wasd_label.setProperty("muted", True)
        wasd_label.setAlignment(Qt.AlignCenter)

        wasd_layout.addLayout(wasd_grid)
        wasd_layout.addWidget(wasd_label)

        arrows_layout = QVBoxLayout()
        arrows_grid = QGridLayout()
        arrows_grid.setSpacing(4)

        self._key_up = KeyButton("\u2191", Qt.Key_Up)
        self._key_left = KeyButton("\u2190", Qt.Key_Left)
        self._key_down = KeyButton("\u2193", Qt.Key_Down)
        self._key_right = KeyButton("\u2192", Qt.Key_Right)

        arrows_grid.addWidget(self._key_up, 0, 1)
        arrows_grid.addWidget(self._key_left, 1, 0)
        arrows_grid.addWidget(self._key_down, 1, 1)
        arrows_grid.addWidget(self._key_right, 1, 2)

        arrows_label = QLabel("Pitch / Roll")
        arrows_label.setProperty("muted", True)
        arrows_label.setAlignment(Qt.AlignCenter)

        arrows_layout.addLayout(arrows_grid)
        arrows_layout.addWidget(arrows_label)

        keys_layout.addLayout(wasd_layout)
        keys_layout.addLayout(arrows_layout)

        self._key_buttons = {
            Qt.Key_W: self._key_w,
            Qt.Key_A: self._key_a,
            Qt.Key_S: self._key_s,
            Qt.Key_D: self._key_d,
            Qt.Key_Up: self._key_up,
            Qt.Key_Left: self._key_left,
            Qt.Key_Down: self._key_down,
            Qt.Key_Right: self._key_right,
        }

        layout.addWidget(help_label)
        layout.addWidget(keys_widget)

        return group

    def _create_velocity_panel(self) -> QGroupBox:
        group = QGroupBox("Velocity Control")
        layout = QHBoxLayout(group)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        self._pitch_slider = LabeledSlider("Pitch", 0.0, 1.0, 0.1)
        self._roll_slider = LabeledSlider("Roll", 0.0, 1.0, 0.1)
        self._thrust_slider = LabeledSlider("Thrust", 0.0, 1.0, 0.2)
        self._yaw_slider = LabeledSlider("Yaw", 0.0, 1.0, 0.2)

        self._velocity_sliders = [
            self._pitch_slider,
            self._roll_slider,
            self._thrust_slider,
            self._yaw_slider,
        ]

        for slider in self._velocity_sliders:
            slider.setEnabled(False)
            layout.addWidget(slider)

        return group

    def _create_telemetry_panel(self) -> QGroupBox:
        group = QGroupBox("Telemetry")
        layout = QGridLayout(group)
        layout.setSpacing(10)

        self._pos_x_label = QLabel("X: --")
        self._pos_y_label = QLabel("Y: --")
        self._pos_z_label = QLabel("Z: --")
        self._yaw_label = QLabel("Yaw: --")
        self._heading_label = QLabel("Heading: --")
        self._mode_label = QLabel("Mode: --")

        layout.addWidget(self._pos_x_label, 0, 0)
        layout.addWidget(self._pos_y_label, 0, 1)
        layout.addWidget(self._pos_z_label, 0, 2)
        layout.addWidget(self._yaw_label, 1, 0)
        layout.addWidget(self._heading_label, 1, 1)
        layout.addWidget(self._mode_label, 1, 2)

        return group

    def _setup_timers(self) -> None:
        self._command_timer = QTimer(self)
        self._command_timer.timeout.connect(self._send_velocity_command)
        self._command_timer.setInterval(50)

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._update_telemetry)
        self._telemetry_timer.setInterval(500)
        self._telemetry_timer.start()

        self._driver_check_timer = QTimer(self)
        self._driver_check_timer.timeout.connect(self._trigger_driver_check)
        self._driver_check_timer.setInterval(3000)
        self._driver_check_timer.start()

    def _setup_status_checker(self) -> None:
        self._checker_thread = QThread()
        self._status_checker = DriverStatusChecker()
        self._status_checker.moveToThread(self._checker_thread)
        self._status_checker.status_checked.connect(self._on_driver_status_checked)
        self._checker_thread.start()

    def _update_ui_state(self) -> None:
        can_control = self._driver_connected and self._instance_initialized

        self._driver_btn.setText("Disconnect" if self._driver_connected else "Connect")
        self._driver_btn.setProperty("accent", not self._driver_connected)
        self._driver_btn.setProperty("danger", self._driver_connected)
        self._driver_btn.style().unpolish(self._driver_btn)
        self._driver_btn.style().polish(self._driver_btn)

        self._instance_btn.setEnabled(self._driver_connected)
        self._instance_btn.setText(
            "Cleanup" if self._instance_initialized else "Initialize"
        )

        self._drone_combo.setEnabled(not self._driver_connected)
        self._config_panel.setEnabled(not self._instance_initialized)

        self._status_driver.set_status(
            "active" if self._driver_connected else "inactive"
        )
        self._status_instance.set_status(
            "active" if self._instance_initialized else "inactive"
        )

        self._enable_btn.setEnabled(can_control)
        self._emergency_btn.setEnabled(can_control)

        if not can_control and self._controls_enabled:
            self._disable_controls()

        self._set_mavros_controls_enabled(can_control and self._drone_type == "mavros")
        self._set_bebop_controls_enabled(can_control and self._drone_type == "bebop")

    def _set_mavros_controls_enabled(self, enabled: bool) -> None:
        self._arm_btn.setEnabled(enabled)
        self._disarm_btn.setEnabled(enabled)
        self._takeoff_btn.setEnabled(enabled)
        self._land_btn.setEnabled(enabled)
        self._arm_takeoff_btn.setEnabled(enabled)

    def _set_bebop_controls_enabled(self, enabled: bool) -> None:
        self._bebop_takeoff_btn.setEnabled(enabled)
        self._bebop_land_btn.setEnabled(enabled)
        self._flip_btn.setEnabled(enabled)

    def _disable_controls(self) -> None:
        self._controls_enabled = False
        self._enable_btn.setChecked(False)
        self._enable_btn.setText("Enable Controls")
        self._enable_btn.setProperty("danger", False)
        self._enable_btn.style().unpolish(self._enable_btn)
        self._enable_btn.style().polish(self._enable_btn)
        self._command_timer.stop()

        for slider in self._velocity_sliders:
            slider.setEnabled(False)

        self._stop_movement()

    def _stop_movement(self) -> None:
        self._key_states.clear()
        for btn in self._key_buttons.values():
            btn.set_pressed(False)
        if self._drone:
            try:
                self._drone.move_velocity(0, 0, 0, 0)
            except Exception:
                pass

    @Slot(str)
    def _on_drone_type_changed(self, drone_type: str) -> None:
        self._drone_type = drone_type.lower()
        is_mavros = self._drone_type == "mavros"

        self._mavros_group.setVisible(is_mavros)
        self._bebop_group.setVisible(not is_mavros)
        self._config_panel.set_drone_type(self._drone_type)

        if self._status_checker:
            self._status_checker.set_drone_type(self._drone_type)

    @Slot()
    def _trigger_driver_check(self) -> None:
        if self._status_checker:
            self._status_checker.check()

    @Slot(bool)
    def _on_driver_status_checked(self, is_running: bool) -> None:
        if is_running != self._driver_connected:
            self._driver_connected = is_running
            if not is_running and self._instance_initialized:
                self._cleanup_instance()
            self._update_ui_state()

    @Slot()
    def _toggle_driver(self) -> None:
        if self._driver_connected:
            self._disconnect_driver()
        else:
            self._connect_driver()

    def _connect_driver(self) -> None:
        self._driver_btn.setEnabled(False)
        self._driver_btn.setText("Connecting...")
        self._show_progress("Connecting driver...")

        config = self._config_panel.get_config()
        conn_str = config.get("connection_string", "")
        ip = config.get("ip", "")

        self._driver_thread = QThread()
        self._driver_worker = DriverWorker()
        self._driver_worker.setup_connect(self._drone_type, conn_str, ip)
        self._driver_worker.moveToThread(self._driver_thread)

        self._driver_thread.started.connect(self._driver_worker.run)
        self._driver_worker.progress.connect(self._show_progress)
        self._driver_worker.finished.connect(self._on_driver_connect_finished)
        self._driver_worker.finished.connect(self._driver_thread.quit)

        self._driver_thread.start()

    def _disconnect_driver(self) -> None:
        if self._instance_initialized:
            self._cleanup_instance()

        self._driver_btn.setEnabled(False)
        self._driver_btn.setText("Disconnecting...")
        self._show_progress("Disconnecting driver...")

        self._driver_thread = QThread()
        self._driver_worker = DriverWorker()
        self._driver_worker.setup_disconnect(self._drone_type)
        self._driver_worker.moveToThread(self._driver_thread)

        self._driver_thread.started.connect(self._driver_worker.run)
        self._driver_worker.progress.connect(self._show_progress)
        self._driver_worker.finished.connect(self._on_driver_disconnect_finished)
        self._driver_worker.finished.connect(self._driver_thread.quit)

        self._driver_thread.start()

    @Slot(bool, str)
    def _on_driver_connect_finished(self, success: bool, error: str) -> None:
        self._driver_btn.setEnabled(True)
        self._show_progress("")

        if success:
            self._driver_connected = True
        else:
            self._driver_connected = False
            self._show_progress(f"Error: {error}")

        self._update_ui_state()

    @Slot(bool, str)
    def _on_driver_disconnect_finished(self, success: bool, error: str) -> None:
        self._driver_btn.setEnabled(True)
        self._show_progress("")
        self._driver_connected = False
        self._update_ui_state()

    @Slot()
    def _toggle_instance(self) -> None:
        if self._instance_initialized:
            self._cleanup_instance()
            self._update_ui_state()
        else:
            self._initialize_instance()

    def _initialize_instance(self) -> None:
        if not self._node:
            self._show_progress("No ROS2 node available")
            return

        self._instance_btn.setEnabled(False)
        self._instance_btn.setText("Initializing...")
        self._show_progress("Initializing drone instance...")

        config = self._config_panel.create_config_object()

        self._instance_thread = QThread()
        self._instance_worker = DroneInstanceWorker()
        self._instance_worker.setup(self._node, self._drone_type, config)
        self._instance_worker.moveToThread(self._instance_thread)

        self._instance_thread.started.connect(self._instance_worker.run)
        self._instance_worker.progress.connect(self._show_progress)
        self._instance_worker.drone_ready.connect(self._on_drone_ready)
        self._instance_worker.finished.connect(self._on_instance_finished)
        self._instance_worker.finished.connect(self._instance_thread.quit)

        self._instance_thread.start()

    def _cleanup_instance(self) -> None:
        if self._drone:
            try:
                self._drone.cleanup()
            except Exception:
                pass
            self._drone = None

        self._instance_initialized = False
        self._disable_controls()
        self._status_armed.set_status("inactive")
        self._status_mode.set_status("inactive")
        self._status_mode.set_label("Mode")

    @Slot(object)
    def _on_drone_ready(self, drone) -> None:
        self._drone = drone

    @Slot(bool, str)
    def _on_instance_finished(self, success: bool, error: str) -> None:
        self._instance_btn.setEnabled(True)
        self._show_progress("")

        if success and self._drone:
            self._instance_initialized = True
        else:
            self._instance_initialized = False
            self._drone = None
            self._show_progress(f"Error: {error}")

        self._update_ui_state()

    def _show_progress(self, message: str) -> None:
        self._progress_label.setText(message)

    @Slot()
    def _toggle_controls(self) -> None:
        self._controls_enabled = self._enable_btn.isChecked()

        if self._controls_enabled:
            self._enable_btn.setText("Disable Controls")
            self._enable_btn.setProperty("danger", True)
            self._command_timer.start()
            for slider in self._velocity_sliders:
                slider.setEnabled(True)
        else:
            self._enable_btn.setText("Enable Controls")
            self._enable_btn.setProperty("danger", False)
            self._command_timer.stop()
            for slider in self._velocity_sliders:
                slider.setEnabled(False)
            self._stop_movement()

        self._enable_btn.style().unpolish(self._enable_btn)
        self._enable_btn.style().polish(self._enable_btn)

    @Slot()
    def _emergency_stop(self) -> None:
        self._controls_enabled = False
        self._enable_btn.setChecked(False)
        self._toggle_controls()

        if self._drone:
            try:
                self._drone.emergency_stop()
            except Exception:
                pass

    @Slot()
    def _arm(self) -> None:
        if self._drone:
            try:
                self._drone.arm()
            except Exception as e:
                self._log_error(f"Arm failed: {e}")

    @Slot()
    def _disarm(self) -> None:
        if self._drone:
            try:
                self._drone.disarm()
            except Exception as e:
                self._log_error(f"Disarm failed: {e}")

    @Slot()
    def _takeoff(self) -> None:
        if self._drone:
            try:
                self._drone.takeoff(self._altitude_spin.value())
            except Exception as e:
                self._log_error(f"Takeoff failed: {e}")

    @Slot()
    def _land(self) -> None:
        if self._drone:
            try:
                self._drone.land()
            except Exception as e:
                self._log_error(f"Land failed: {e}")

    @Slot()
    def _arm_takeoff(self) -> None:
        if self._drone:
            try:
                self._drone.arm()
                self._drone.takeoff(self._altitude_spin.value())
            except Exception as e:
                self._log_error(f"Arm+Takeoff failed: {e}")

    @Slot()
    def _bebop_takeoff(self) -> None:
        if self._drone:
            try:
                self._drone.takeoff(1.0)
            except Exception as e:
                self._log_error(f"Takeoff failed: {e}")

    @Slot()
    def _bebop_land(self) -> None:
        if self._drone:
            try:
                self._drone.land()
            except Exception as e:
                self._log_error(f"Land failed: {e}")

    @Slot()
    def _show_flip_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS.surface_elevated};
                border: 1px solid {COLORS.border};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                color: {COLORS.text_primary};
            }}
            QMenu::item:selected {{
                background-color: {COLORS.accent};
                color: {COLORS.background};
            }}
        """
        )

        for name, value in [("Front", 0), ("Back", 1), ("Left", 2), ("Right", 3)]:
            action = menu.addAction(name)
            action.triggered.connect(lambda _, v=value: self._do_flip(v))

        menu.exec_(self._flip_btn.mapToGlobal(self._flip_btn.rect().bottomLeft()))

    def _do_flip(self, direction: int) -> None:
        if self._drone and hasattr(self._drone, "flip"):
            try:
                self._drone.flip(direction)
            except Exception as e:
                self._log_error(f"Flip failed: {e}")

    @Slot()
    def _update_telemetry(self) -> None:
        if not self._drone:
            return

        try:
            if hasattr(self._drone, "mavros_state"):
                state = self._drone.mavros_state
                self._status_armed.set_status("active" if state.armed else "inactive")
                self._mode_label.setText(f"Mode: {state.mode}")

                if state.mode:
                    self._status_mode.set_status("info")
                    self._status_mode.set_label(state.mode)
                else:
                    self._status_mode.set_status("inactive")
                    self._status_mode.set_label("Mode")

            if hasattr(self._drone, "height"):
                self._pos_z_label.setText(f"Z: {self._drone.height:.2f}m")

            if hasattr(self._drone, "heading"):
                try:
                    self._heading_label.setText(f"Heading: {self._drone.heading:.1f}")
                except Exception:
                    pass

        except Exception:
            pass

    @Slot()
    def _send_velocity_command(self) -> None:
        if not self._controls_enabled or not self._drone:
            return

        pitch, roll, thrust, yaw = 0.0, 0.0, 0.0, 0.0

        for key, (axis, direction) in self.KEY_MAP.items():
            if self._key_states.get(key, False):
                if axis == "pitch":
                    pitch = direction
                elif axis == "roll":
                    roll = direction
                elif axis == "thrust":
                    thrust = direction
                elif axis == "yaw":
                    yaw = direction

        pitch *= self._pitch_slider.value()
        roll *= self._roll_slider.value()
        thrust *= self._thrust_slider.value()
        yaw *= self._yaw_slider.value()

        try:
            from mirela_sdk.control import MoveReference

            reference = (
                MoveReference.BODY
                if self._body_frame_check.isChecked()
                else MoveReference.WORLD
            )
            self._drone.move_velocity(pitch, roll, thrust, yaw, reference=reference)
        except Exception:
            pass

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()
        if key in self._key_buttons:
            self._key_states[key] = True
            self._key_buttons[key].set_pressed(True)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()
        if key in self._key_buttons:
            self._key_states[key] = False
            self._key_buttons[key].set_pressed(False)
        else:
            super().keyReleaseEvent(event)

    def _log_error(self, message: str) -> None:
        if self._node:
            self._node.get_logger().error(message)

    def set_node(self, node: Node) -> None:
        self._node = node

    def cleanup(self) -> None:
        self._command_timer.stop()
        self._telemetry_timer.stop()
        self._driver_check_timer.stop()

        if self._status_checker:
            self._status_checker.set_enabled(False)

        if self._checker_thread and self._checker_thread.isRunning():
            self._checker_thread.quit()
            self._checker_thread.wait(1000)

        if self._driver_thread and self._driver_thread.isRunning():
            self._driver_thread.quit()
            self._driver_thread.wait(1000)

        if self._instance_thread and self._instance_thread.isRunning():
            self._instance_thread.quit()
            self._instance_thread.wait(1000)

        self._cleanup_instance()
