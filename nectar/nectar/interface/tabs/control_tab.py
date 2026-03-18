from typing import Dict, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from rclpy.node import Node

from nectar.interface.theme import COLORS
from nectar.interface.widgets import (
    DroneConfigPanel,
    KeyButton,
    LabeledSlider,
    StatusIndicator,
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

    def setup_connect(self, drone_type: str, connection_string: str = "", ip: str = "") -> None:
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
            from nectar.utils.process import ProcessUtils

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
            from nectar.control import DroneFactory

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
            from nectar.utils.process import ProcessUtils

            pattern = "mavros_node" if self._drone_type == "mavros" else "bebop_driver"
            is_running = ProcessUtils.is_node_running(pattern, timeout=2.0)
            self.status_checked.emit(is_running)
        except Exception:
            self.status_checked.emit(False)


class FlightActionWorker(QObject):
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._drone = None
        self._action: str = ""
        self._altitude: float = 1.5

    def setup(self, drone, action: str, altitude: float = 1.5) -> None:
        self._drone = drone
        self._action = action
        self._altitude = altitude

    @Slot()
    def run(self) -> None:
        try:
            if self._action == "arm":
                self.progress.emit("Arming (set GUIDED, arm)...")
                success = self._drone.arm()
                self.finished.emit(success, "" if success else "Arm rejected by FCU")
            elif self._action == "disarm":
                self.progress.emit("Disarming (force)...")
                success = self._drone.disarm()
                self.finished.emit(success, "" if success else "Disarm rejected")
            elif self._action == "takeoff":
                self.progress.emit(f"Takeoff to {self._altitude:.1f}m...")
                success = self._drone.takeoff(self._altitude)
                self.finished.emit(success, "" if success else "Takeoff failed")
            elif self._action == "land":
                self.progress.emit("Landing...")
                success = self._drone.land()
                self.finished.emit(success, "" if success else "Land failed")
            else:
                self.finished.emit(False, f"Unknown action: {self._action}")
        except TimeoutError as e:
            self.finished.emit(False, f"Service timeout: {e}")
        except Exception as e:
            self.finished.emit(False, str(e))


class MoveToWorker(QObject):
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._drone = None
        self._x: Optional[float] = None
        self._y: Optional[float] = None
        self._z: Optional[float] = None
        self._yaw: Optional[float] = None
        self._reference = None
        self._strategy = None
        self._altitude_source = None
        self._timeout: float = 60.0
        self._precision: float = 0.2
        self._cancelled: bool = False

    def setup(
        self,
        drone,
        x: Optional[float],
        y: Optional[float],
        z: Optional[float],
        yaw: Optional[float],
        reference,
        timeout: float,
        precision: float,
        strategy=None,
        altitude_source=None,
    ) -> None:
        self._drone = drone
        self._x = x
        self._y = y
        self._z = z
        self._yaw = yaw
        self._reference = reference
        self._strategy = strategy
        self._altitude_source = altitude_source
        self._timeout = timeout
        self._precision = precision
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        if self._drone:
            try:
                self._drone.move_velocity(0, 0, 0, 0)
            except Exception:
                pass

    @Slot()
    def run(self) -> None:
        try:
            parts = []
            if self._x is not None:
                parts.append(f"x={self._x:.1f}")
            if self._y is not None:
                parts.append(f"y={self._y:.1f}")
            if self._z is not None:
                parts.append(f"z={self._z:.1f}")
            if self._yaw is not None:
                parts.append(f"yaw={self._yaw:.0f}")
            target_str = ", ".join(parts) if parts else "none"
            self.progress.emit(f"Moving: {target_str}")

            kwargs = dict(
                x=self._x,
                y=self._y,
                z=self._z,
                yaw=self._yaw,
                reference=self._reference,
                timeout=self._timeout,
                precision=self._precision,
            )
            if self._strategy is not None:
                kwargs["strategy"] = self._strategy
            if self._altitude_source is not None:
                kwargs["altitude_source"] = self._altitude_source
            success = self._drone.move_to(**kwargs)
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
            elif success:
                self.finished.emit(True, f"Reached: {target_str}")
            else:
                self.finished.emit(False, f"Timeout ({self._timeout:.0f}s)")
        except Exception as e:
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
            else:
                self.finished.emit(False, str(e))


class ControlTab(QWidget):
    KEY_MAP = {
        Qt.Key_W: ("vz", 1),
        Qt.Key_S: ("vz", -1),
        Qt.Key_A: ("vyaw", 1),
        Qt.Key_D: ("vyaw", -1),
        Qt.Key_Up: ("vx", 1),
        Qt.Key_Down: ("vx", -1),
        Qt.Key_Left: ("vy", 1),
        Qt.Key_Right: ("vy", -1),
    }

    def __init__(self, node: Optional[Node] = None, parent: Optional[QWidget] = None) -> None:
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
        self._moveto_thread: Optional[QThread] = None
        self._moveto_worker: Optional[MoveToWorker] = None
        self._moveto_running: bool = False
        self._flight_thread: Optional[QThread] = None
        self._flight_worker: Optional[FlightActionWorker] = None
        self._flight_action_running: bool = False
        self._last_velocity_cmd: tuple = (0.0, 0.0, 0.0, 0.0)
        self._velocity_log_counter: int = 0

        self._setup_ui()
        self._setup_timers()
        self._setup_status_checker()
        self._update_ui_state()
        self._update_capability_panels()
        self._update_status_indicators()
        self.setFocusPolicy(Qt.StrongFocus)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._create_connection_panel())
        layout.addWidget(self._create_control_area(), 1)
        layout.addWidget(self._create_flight_actions_bar())
        layout.addWidget(self._create_telemetry_panel())

    def _create_connection_panel(self) -> QGroupBox:
        group = QGroupBox("Connection")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        type_layout = QHBoxLayout()
        type_layout.setSpacing(6)
        lbl = QLabel("Drone:")
        lbl.setProperty("secondary", True)
        self._drone_combo = QComboBox()
        self._drone_combo.addItems(["Mavros", "Bebop"])
        self._drone_combo.setFixedWidth(100)
        self._drone_combo.currentTextChanged.connect(self._on_drone_type_changed)
        type_layout.addWidget(lbl)
        type_layout.addWidget(self._drone_combo)
        top_layout.addLayout(type_layout)

        self._config_panel = DroneConfigPanel()
        self._config_panel.set_drone_type("mavros")
        self._config_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_layout.addWidget(self._config_panel, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._driver_btn = QPushButton("Connect Driver")
        self._driver_btn.setProperty("accent", True)
        self._driver_btn.setMinimumWidth(140)
        self._driver_btn.clicked.connect(self._toggle_driver)
        btn_layout.addWidget(self._driver_btn)

        self._instance_btn = QPushButton("Initialize")
        self._instance_btn.setEnabled(False)
        self._instance_btn.setMinimumWidth(100)
        self._instance_btn.clicked.connect(self._toggle_instance)
        btn_layout.addWidget(self._instance_btn)

        top_layout.addLayout(btn_layout)
        main_layout.addLayout(top_layout)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS.border};")
        main_layout.addWidget(sep)

        status_layout = QHBoxLayout()
        status_layout.setSpacing(12)

        status_header = QLabel("Status")
        status_header.setProperty("secondary", True)
        status_header.setStyleSheet(f"color: {COLORS.text_muted}; font-size: 10px;")
        status_header.setFixedWidth(40)
        status_layout.addWidget(status_header)

        self._status_driver = StatusIndicator("Driver", "inactive")
        self._status_instance = StatusIndicator("Instance", "inactive")
        self._status_fcu = StatusIndicator("FCU", "inactive")
        self._status_armed = StatusIndicator("Armed", "inactive")

        status_layout.addWidget(self._status_driver)
        status_layout.addWidget(self._status_instance)
        status_layout.addWidget(self._status_fcu)
        status_layout.addWidget(self._status_armed)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedWidth(1)
        sep2.setStyleSheet(f"background-color: {COLORS.border};")
        status_layout.addWidget(sep2)

        self._mode_label = QLabel("Mode: --")
        self._mode_label.setProperty("secondary", True)
        status_layout.addWidget(self._mode_label)

        status_layout.addStretch()

        self._progress_label = QLabel("")
        self._progress_label.setProperty("secondary", True)
        status_layout.addWidget(self._progress_label)

        main_layout.addLayout(status_layout)

        return group

    def _create_control_area(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._create_velocity_control_panel())
        self._position_panel = self._create_position_control_panel()
        layout.addWidget(self._position_panel)

        return container

    def _create_velocity_control_panel(self) -> QGroupBox:
        self._velocity_group = QGroupBox("Velocity Control")
        self._velocity_group.setMinimumWidth(360)
        self._velocity_group.setMaximumWidth(440)
        main_layout = QHBoxLayout(self._velocity_group)
        main_layout.setSpacing(16)

        keys_container = QWidget()
        keys_layout = QVBoxLayout(keys_container)
        keys_layout.setContentsMargins(0, 0, 0, 0)
        keys_layout.setSpacing(12)

        wasd_container = QWidget()
        wasd_layout = QVBoxLayout(wasd_container)
        wasd_layout.setContentsMargins(0, 0, 0, 0)
        wasd_layout.setSpacing(2)

        wasd_grid = QGridLayout()
        wasd_grid.setSpacing(3)

        self._key_w = KeyButton("W", Qt.Key_W)
        self._key_a = KeyButton("A", Qt.Key_A)
        self._key_s = KeyButton("S", Qt.Key_S)
        self._key_d = KeyButton("D", Qt.Key_D)

        wasd_grid.addWidget(self._key_w, 0, 1)
        wasd_grid.addWidget(self._key_a, 1, 0)
        wasd_grid.addWidget(self._key_s, 1, 1)
        wasd_grid.addWidget(self._key_d, 1, 2)

        wasd_label = QLabel("Z / Yaw")
        wasd_label.setProperty("muted", True)
        wasd_label.setAlignment(Qt.AlignCenter)

        wasd_layout.addLayout(wasd_grid)
        wasd_layout.addWidget(wasd_label)

        arrows_container = QWidget()
        arrows_layout = QVBoxLayout(arrows_container)
        arrows_layout.setContentsMargins(0, 0, 0, 0)
        arrows_layout.setSpacing(2)

        arrows_grid = QGridLayout()
        arrows_grid.setSpacing(3)

        self._key_up = KeyButton("↑", Qt.Key_Up)
        self._key_left = KeyButton("←", Qt.Key_Left)
        self._key_down = KeyButton("↓", Qt.Key_Down)
        self._key_right = KeyButton("→", Qt.Key_Right)

        arrows_grid.addWidget(self._key_up, 0, 1)
        arrows_grid.addWidget(self._key_left, 1, 0)
        arrows_grid.addWidget(self._key_down, 1, 1)
        arrows_grid.addWidget(self._key_right, 1, 2)

        arrows_label = QLabel("X / Y")
        arrows_label.setProperty("muted", True)
        arrows_label.setAlignment(Qt.AlignCenter)

        arrows_layout.addLayout(arrows_grid)
        arrows_layout.addWidget(arrows_label)

        keys_layout.addWidget(wasd_container)
        keys_layout.addWidget(arrows_container)

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

        sliders_container = QWidget()
        sliders_layout = QVBoxLayout(sliders_container)
        sliders_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout.setSpacing(6)

        self._vx_slider = LabeledSlider("Vx", 0.0, 1.0, 0.2, orientation=Qt.Horizontal)
        self._vy_slider = LabeledSlider("Vy", 0.0, 1.0, 0.2, orientation=Qt.Horizontal)
        self._vz_slider = LabeledSlider("Vz", 0.0, 1.0, 0.2, orientation=Qt.Horizontal)
        self._vyaw_slider = LabeledSlider("Vψ", 0.0, 1.0, 0.2, orientation=Qt.Horizontal)

        self._velocity_sliders = [
            self._vx_slider,
            self._vy_slider,
            self._vz_slider,
            self._vyaw_slider,
        ]

        for slider in self._velocity_sliders:
            slider.setEnabled(False)
            sliders_layout.addWidget(slider)

        ref_layout = QHBoxLayout()
        ref_layout.setSpacing(6)
        ref_lbl = QLabel("Ref:")
        ref_lbl.setProperty("secondary", True)
        self._vel_reference_combo = QComboBox()
        self._vel_reference_combo.addItems(["Body", "World", "Takeoff"])
        self._vel_reference_combo.setCurrentIndex(0)
        self._vel_reference_combo.setFixedWidth(80)
        ref_layout.addWidget(ref_lbl)
        ref_layout.addWidget(self._vel_reference_combo)
        ref_layout.addStretch()

        sliders_layout.addLayout(ref_layout)

        self._velocity_status_label = QLabel("Cmd: vx=0.00 vy=0.00 vz=0.00 vyaw=0.00")
        self._velocity_status_label.setProperty("secondary", True)
        self._velocity_status_label.setStyleSheet(f"color: {COLORS.text_muted}; font-size: 10px;")
        sliders_layout.addWidget(self._velocity_status_label)

        main_layout.addWidget(keys_container)
        main_layout.addWidget(sliders_container, 1)

        return self._velocity_group

    def _create_position_control_panel(self) -> QGroupBox:
        self._position_group = QGroupBox("Position Control")
        self._position_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        layout = QVBoxLayout(self._position_group)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 12, 12, 12)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self._pos_x_check = QCheckBox("X")
        self._pos_x_spin = QDoubleSpinBox()
        self._pos_x_spin.setRange(-20.0, 20.0)
        self._pos_x_spin.setValue(0.0)
        self._pos_x_spin.setSingleStep(0.5)
        self._pos_x_spin.setDecimals(1)
        self._pos_x_spin.setSuffix(" m")
        self._pos_x_spin.setEnabled(False)
        self._pos_x_check.toggled.connect(self._pos_x_spin.setEnabled)
        grid.addWidget(self._pos_x_check, 0, 0)
        grid.addWidget(self._pos_x_spin, 0, 1)

        self._pos_y_check = QCheckBox("Y")
        self._pos_y_spin = QDoubleSpinBox()
        self._pos_y_spin.setRange(-20.0, 20.0)
        self._pos_y_spin.setValue(0.0)
        self._pos_y_spin.setSingleStep(0.5)
        self._pos_y_spin.setDecimals(1)
        self._pos_y_spin.setSuffix(" m")
        self._pos_y_spin.setEnabled(False)
        self._pos_y_check.toggled.connect(self._pos_y_spin.setEnabled)
        grid.addWidget(self._pos_y_check, 0, 2)
        grid.addWidget(self._pos_y_spin, 0, 3)

        self._pos_z_check = QCheckBox("Z")
        self._pos_z_spin = QDoubleSpinBox()
        self._pos_z_spin.setRange(-20.0, 20.0)
        self._pos_z_spin.setValue(0.0)
        self._pos_z_spin.setSingleStep(0.5)
        self._pos_z_spin.setDecimals(1)
        self._pos_z_spin.setSuffix(" m")
        self._pos_z_spin.setEnabled(False)
        self._pos_z_check.toggled.connect(self._pos_z_spin.setEnabled)
        grid.addWidget(self._pos_z_check, 1, 0)
        grid.addWidget(self._pos_z_spin, 1, 1)

        self._pos_yaw_check = QCheckBox("Yaw")
        self._pos_yaw_spin = QDoubleSpinBox()
        self._pos_yaw_spin.setRange(-180.0, 180.0)
        self._pos_yaw_spin.setValue(0.0)
        self._pos_yaw_spin.setSingleStep(15.0)
        self._pos_yaw_spin.setDecimals(0)
        self._pos_yaw_spin.setSuffix("°")
        self._pos_yaw_spin.setEnabled(False)
        self._pos_yaw_check.toggled.connect(self._pos_yaw_spin.setEnabled)
        grid.addWidget(self._pos_yaw_check, 1, 2)
        grid.addWidget(self._pos_yaw_spin, 1, 3)

        layout.addLayout(grid)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        ref_lbl = QLabel("Ref:")
        ref_lbl.setProperty("secondary", True)
        self._pos_reference_combo = QComboBox()
        self._pos_reference_combo.addItems(["Body", "Takeoff"])
        self._pos_reference_combo.setCurrentIndex(0)
        self._pos_reference_combo.setFixedWidth(90)

        strat_lbl = QLabel("Strategy:")
        strat_lbl.setProperty("secondary", True)
        self._pos_strategy_combo = QComboBox()
        self._pos_strategy_combo.addItems(["PID", "PID Local", "Setpoint", "Setpoint Global"])
        self._pos_strategy_combo.setCurrentIndex(0)
        self._pos_strategy_combo.setFixedWidth(120)

        alt_src_lbl = QLabel("Alt:")
        alt_src_lbl.setProperty("secondary", True)
        self._pos_alt_source_combo = QComboBox()
        self._pos_alt_source_combo.addItems(["Auto", "Lidar", "Vision", "Rel Alt"])
        self._pos_alt_source_combo.setCurrentIndex(0)
        self._pos_alt_source_combo.setFixedWidth(80)

        row1.addWidget(ref_lbl)
        row1.addWidget(self._pos_reference_combo)
        row1.addWidget(strat_lbl)
        row1.addWidget(self._pos_strategy_combo)
        row1.addWidget(alt_src_lbl)
        row1.addWidget(self._pos_alt_source_combo)
        row1.addStretch()

        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(12)

        prec_lbl = QLabel("Prec:")
        prec_lbl.setProperty("secondary", True)
        self._pos_precision_spin = QDoubleSpinBox()
        self._pos_precision_spin.setRange(0.05, 2.0)
        self._pos_precision_spin.setValue(0.2)
        self._pos_precision_spin.setSingleStep(0.1)
        self._pos_precision_spin.setDecimals(2)
        self._pos_precision_spin.setSuffix(" m")
        self._pos_precision_spin.setFixedWidth(80)

        timeout_lbl = QLabel("T/O:")
        timeout_lbl.setProperty("secondary", True)
        self._pos_timeout_spin = QDoubleSpinBox()
        self._pos_timeout_spin.setRange(5.0, 300.0)
        self._pos_timeout_spin.setValue(60.0)
        self._pos_timeout_spin.setSingleStep(10.0)
        self._pos_timeout_spin.setDecimals(0)
        self._pos_timeout_spin.setSuffix(" s")
        self._pos_timeout_spin.setFixedWidth(80)

        row2.addWidget(prec_lbl)
        row2.addWidget(self._pos_precision_spin)
        row2.addWidget(timeout_lbl)
        row2.addWidget(self._pos_timeout_spin)
        row2.addStretch()

        layout.addLayout(row2)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._pos_go_btn = QPushButton("Go")
        self._pos_go_btn.setProperty("accent", True)
        self._pos_go_btn.setEnabled(False)
        self._pos_go_btn.clicked.connect(self._execute_move_to)
        btn_layout.addWidget(self._pos_go_btn, 1)

        self._pos_cancel_btn = QPushButton("Cancel")
        self._pos_cancel_btn.setEnabled(False)
        self._pos_cancel_btn.setMinimumWidth(75)
        self._pos_cancel_btn.clicked.connect(self._cancel_move_to)
        btn_layout.addWidget(self._pos_cancel_btn)

        layout.addLayout(btn_layout)

        self._pos_status_label = QLabel("")
        self._pos_status_label.setProperty("secondary", True)
        layout.addWidget(self._pos_status_label)

        self._position_control_widgets = [
            self._pos_x_check,
            self._pos_y_check,
            self._pos_z_check,
            self._pos_yaw_check,
            self._pos_reference_combo,
            self._pos_strategy_combo,
            self._pos_alt_source_combo,
            self._pos_precision_spin,
            self._pos_timeout_spin,
            self._pos_go_btn,
        ]

        return self._position_group

    def _create_flight_actions_bar(self) -> QGroupBox:
        group = QGroupBox("Flight Actions")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)

        self._enable_btn = QPushButton("Enable Controls")
        self._enable_btn.setCheckable(True)
        self._enable_btn.setEnabled(False)
        self._enable_btn.setMinimumWidth(120)
        self._enable_btn.clicked.connect(self._toggle_controls)
        layout.addWidget(self._enable_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFixedWidth(1)
        sep1.setStyleSheet(f"background-color: {COLORS.border};")
        layout.addWidget(sep1)

        self._mavros_actions = QWidget()
        mavros_layout = QHBoxLayout(self._mavros_actions)
        mavros_layout.setContentsMargins(0, 0, 0, 0)
        mavros_layout.setSpacing(6)

        self._arm_btn = QPushButton("Arm")
        self._arm_btn.setEnabled(False)
        self._arm_btn.setMinimumWidth(60)
        self._arm_btn.clicked.connect(self._arm)

        self._disarm_btn = QPushButton("Disarm")
        self._disarm_btn.setEnabled(False)
        self._disarm_btn.setMinimumWidth(70)
        self._disarm_btn.clicked.connect(self._disarm)

        alt_lbl = QLabel("Alt:")
        alt_lbl.setProperty("secondary", True)
        self._altitude_spin = QDoubleSpinBox()
        self._altitude_spin.setRange(0.5, 10.0)
        self._altitude_spin.setValue(1.5)
        self._altitude_spin.setSingleStep(0.1)
        self._altitude_spin.setSuffix(" m")
        self._altitude_spin.setMinimumWidth(75)

        self._takeoff_btn = QPushButton("Takeoff")
        self._takeoff_btn.setProperty("success", True)
        self._takeoff_btn.setEnabled(False)
        self._takeoff_btn.setMinimumWidth(80)
        self._takeoff_btn.clicked.connect(self._takeoff)

        self._land_btn = QPushButton("Land")
        self._land_btn.setEnabled(False)
        self._land_btn.setMinimumWidth(60)
        self._land_btn.clicked.connect(self._land)

        mavros_layout.addWidget(self._arm_btn)
        mavros_layout.addWidget(self._disarm_btn)
        mavros_layout.addWidget(alt_lbl)
        mavros_layout.addWidget(self._altitude_spin)
        mavros_layout.addWidget(self._takeoff_btn)
        mavros_layout.addWidget(self._land_btn)

        layout.addWidget(self._mavros_actions)

        self._bebop_actions = QWidget()
        bebop_layout = QHBoxLayout(self._bebop_actions)
        bebop_layout.setContentsMargins(0, 0, 0, 0)
        bebop_layout.setSpacing(6)

        self._bebop_takeoff_btn = QPushButton("Takeoff")
        self._bebop_takeoff_btn.setProperty("success", True)
        self._bebop_takeoff_btn.setEnabled(False)
        self._bebop_takeoff_btn.setMinimumWidth(80)
        self._bebop_takeoff_btn.clicked.connect(self._bebop_takeoff)

        self._bebop_land_btn = QPushButton("Land")
        self._bebop_land_btn.setEnabled(False)
        self._bebop_land_btn.setMinimumWidth(70)
        self._bebop_land_btn.clicked.connect(self._bebop_land)

        self._flip_btn = QPushButton("Flip...")
        self._flip_btn.setEnabled(False)
        self._flip_btn.setMinimumWidth(80)
        self._flip_btn.clicked.connect(self._show_flip_menu)

        bebop_layout.addWidget(self._bebop_takeoff_btn)
        bebop_layout.addWidget(self._bebop_land_btn)
        bebop_layout.addWidget(self._flip_btn)

        layout.addWidget(self._bebop_actions)
        self._bebop_actions.setVisible(False)

        layout.addStretch()

        self._emergency_btn = QPushButton("STOP")
        self._emergency_btn.setProperty("danger", True)
        self._emergency_btn.setEnabled(False)
        self._emergency_btn.setMinimumWidth(70)
        self._emergency_btn.clicked.connect(self._emergency_stop)
        layout.addWidget(self._emergency_btn)

        return group

    def _create_telemetry_panel(self) -> QGroupBox:
        self._telemetry_group = QGroupBox("Telemetry")
        grid = QGridLayout(self._telemetry_group)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)

        # Row 0: Local EKF pose | Yaw | Height | LiDAR
        self._telem_local_x = QLabel("X: --")
        self._telem_local_y = QLabel("Y: --")
        self._telem_local_z = QLabel("Z: --")
        self._telem_yaw = QLabel("Yaw: --")
        self._telem_height = QLabel("Height: --")
        self._telem_lidar = QLabel("LiDAR: --")

        col = 0
        for w in [
            self._telem_local_x,
            self._telem_local_y,
            self._telem_local_z,
            self._telem_yaw,
            self._telem_height,
            self._telem_lidar,
        ]:
            grid.addWidget(w, 0, col)
            col += 1

        # Row 1: GPS lat/lon/alt | Heading | RelAlt
        self._telem_lat = QLabel("Lat: --")
        self._telem_lon = QLabel("Lon: --")
        self._telem_gps_alt = QLabel("GpsAlt: --")
        self._telem_heading = QLabel("Hdg: --")
        self._telem_rel_alt = QLabel("RelAlt: --")
        self._telem_mode = QLabel("Mode: --")

        col = 0
        for w in [
            self._telem_lat,
            self._telem_lon,
            self._telem_gps_alt,
            self._telem_heading,
            self._telem_rel_alt,
            self._telem_mode,
        ]:
            grid.addWidget(w, 1, col)
            col += 1

        return self._telemetry_group

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

        self._driver_btn.setText(
            "Disconnect Driver" if self._driver_connected else "Connect Driver"
        )
        self._driver_btn.setProperty("accent", not self._driver_connected)
        self._driver_btn.setProperty("danger", self._driver_connected)
        self._driver_btn.style().unpolish(self._driver_btn)
        self._driver_btn.style().polish(self._driver_btn)

        self._instance_btn.setEnabled(self._driver_connected)
        self._instance_btn.setText("Cleanup" if self._instance_initialized else "Initialize")

        self._drone_combo.setEnabled(not self._driver_connected)
        self._config_panel.setEnabled(not self._instance_initialized)

        self._status_driver.set_status("active" if self._driver_connected else "inactive")
        self._status_instance.set_status("active" if self._instance_initialized else "inactive")

        self._enable_btn.setEnabled(can_control)
        self._emergency_btn.setEnabled(can_control and self._controls_enabled)

        if not can_control and self._controls_enabled:
            self._disable_controls()

        controls_active = can_control and self._controls_enabled
        self._set_velocity_control_enabled(controls_active)
        self._set_mavros_controls_enabled(controls_active and self._drone_type == "mavros")
        self._set_bebop_controls_enabled(controls_active and self._drone_type == "bebop")
        self._set_position_control_enabled(controls_active and self._drone_type == "mavros")

    def _update_status_indicators(self) -> None:
        has_fcu = self._drone_type == "mavros"
        self._status_fcu.setVisible(has_fcu)
        self._status_armed.setVisible(has_fcu)

    def _set_mavros_controls_enabled(self, enabled: bool) -> None:
        self._arm_btn.setEnabled(enabled)
        self._disarm_btn.setEnabled(enabled)
        self._altitude_spin.setEnabled(enabled)
        self._takeoff_btn.setEnabled(enabled)
        self._land_btn.setEnabled(enabled)

    def _set_bebop_controls_enabled(self, enabled: bool) -> None:
        self._bebop_takeoff_btn.setEnabled(enabled)
        self._bebop_land_btn.setEnabled(enabled)
        self._flip_btn.setEnabled(enabled)

    def _set_velocity_control_enabled(self, enabled: bool) -> None:
        for slider in self._velocity_sliders:
            slider.setEnabled(enabled)
        self._vel_reference_combo.setEnabled(enabled)
        for btn in self._key_buttons.values():
            btn.setEnabled(enabled)

    def _set_position_control_enabled(self, enabled: bool) -> None:
        if not self._moveto_running:
            for widget in self._position_control_widgets:
                widget.setEnabled(enabled)
            if enabled:
                self._pos_x_spin.setEnabled(self._pos_x_check.isChecked())
                self._pos_y_spin.setEnabled(self._pos_y_check.isChecked())
                self._pos_z_spin.setEnabled(self._pos_z_check.isChecked())
                self._pos_yaw_spin.setEnabled(self._pos_yaw_check.isChecked())
            else:
                self._pos_x_spin.setEnabled(False)
                self._pos_y_spin.setEnabled(False)
                self._pos_z_spin.setEnabled(False)
                self._pos_yaw_spin.setEnabled(False)
        self._pos_cancel_btn.setEnabled(self._moveto_running)

    def _disable_controls(self) -> None:
        self._controls_enabled = False
        self._enable_btn.setChecked(False)
        self._enable_btn.setText("Enable Controls")
        self._enable_btn.setProperty("danger", False)
        self._enable_btn.style().unpolish(self._enable_btn)
        self._enable_btn.style().polish(self._enable_btn)
        self._command_timer.stop()
        self._stop_movement()

    def _stop_movement(self) -> None:
        self._key_states.clear()
        for btn in self._key_buttons.values():
            btn.set_pressed(False)
        if self._drone:
            try:
                self._drone.move_velocity(0, 0, 0, 0)
            except Exception:
                # Best-effort stop; connection may be lost
                pass

    @Slot(str)
    def _on_drone_type_changed(self, drone_type: str) -> None:
        self._drone_type = drone_type.lower()
        is_mavros = self._drone_type == "mavros"

        self._mavros_actions.setVisible(is_mavros)
        self._bebop_actions.setVisible(not is_mavros)
        self._config_panel.set_drone_type(self._drone_type)

        self._update_capability_panels()
        self._update_status_indicators()

        if self._status_checker:
            self._status_checker.set_drone_type(self._drone_type)

    def _update_capability_panels(self) -> None:
        has_position_control = self._drone_type == "mavros"
        has_telemetry = self._drone_type == "mavros"

        self._position_panel.setVisible(has_position_control)
        self._telemetry_group.setVisible(has_telemetry)

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
        self._show_progress("Connecting...")

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
        self._show_progress("Disconnecting...")

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
            if self._node:
                self._node.get_logger().info(f"Driver connected ({self._drone_type})")
        else:
            self._driver_connected = False
            self._show_progress(f"Error: {error}")
            if self._node:
                self._node.get_logger().error(f"Driver connection failed: {error}")

        self._update_ui_state()

    @Slot(bool, str)
    def _on_driver_disconnect_finished(self, success: bool, error: str) -> None:
        self._driver_btn.setEnabled(True)
        self._show_progress("")
        self._driver_connected = False
        if self._node:
            self._node.get_logger().info("Driver disconnected")
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
            self._show_progress("No ROS2 node")
            return

        self._instance_btn.setEnabled(False)
        self._instance_btn.setText("Initializing...")
        self._show_progress("Initializing...")

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
                if self._node:
                    self._node.get_logger().info("Drone instance cleaned up")
            except Exception:
                pass
            self._drone = None

        self._instance_initialized = False
        self._disable_controls()
        self._clear_telemetry()

    @Slot(object)
    def _on_drone_ready(self, drone) -> None:
        self._drone = drone

    @Slot(bool, str)
    def _on_instance_finished(self, success: bool, error: str) -> None:
        self._instance_btn.setEnabled(True)
        self._show_progress("")

        if success and self._drone:
            self._instance_initialized = True
            if self._node:
                self._node.get_logger().info(f"Drone instance initialized ({self._drone_type})")
        else:
            self._instance_initialized = False
            self._drone = None
            self._show_progress(f"Error: {error}")
            if self._node:
                self._node.get_logger().error(f"Drone initialization failed: {error}")

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
            if self._node:
                self._node.get_logger().info("Controls enabled")
        else:
            self._enable_btn.setText("Enable Controls")
            self._enable_btn.setProperty("danger", False)
            self._command_timer.stop()
            self._stop_movement()
            self._velocity_status_label.setText("Cmd: vx=0.00 vy=0.00 vz=0.00 vyaw=0.00")
            if self._node:
                self._node.get_logger().info("Controls disabled")

        self._enable_btn.style().unpolish(self._enable_btn)
        self._enable_btn.style().polish(self._enable_btn)
        self._update_ui_state()

    @Slot()
    def _emergency_stop(self) -> None:
        if self._node:
            self._node.get_logger().warn("EMERGENCY STOP triggered")
        self._controls_enabled = False
        self._enable_btn.setChecked(False)
        self._toggle_controls()

        if self._drone:
            try:
                self._drone.emergency_stop()
            except Exception:
                pass

    def _execute_flight_action(self, action: str, altitude: float = 1.5) -> None:
        if not self._drone or self._flight_action_running:
            return

        if self._node:
            if action == "takeoff":
                self._node.get_logger().info(f"Flight action: {action} (alt={altitude:.1f}m)")
            else:
                self._node.get_logger().info(f"Flight action: {action}")

        self._flight_action_running = True
        self._set_flight_buttons_enabled(False)

        self._flight_thread = QThread()
        self._flight_worker = FlightActionWorker()
        self._flight_worker.setup(self._drone, action, altitude)
        self._flight_worker.moveToThread(self._flight_thread)

        self._flight_thread.started.connect(self._flight_worker.run)
        self._flight_worker.progress.connect(self._show_progress)
        self._flight_worker.finished.connect(self._on_flight_action_finished)
        self._flight_worker.finished.connect(self._flight_thread.quit)

        self._flight_thread.start()

    def _set_flight_buttons_enabled(self, enabled: bool) -> None:
        controls_should_be_active = (
            self._driver_connected and self._instance_initialized and self._controls_enabled
        )
        actual_enabled = enabled and controls_should_be_active
        if self._drone_type == "mavros":
            self._arm_btn.setEnabled(actual_enabled)
            self._disarm_btn.setEnabled(actual_enabled)
            self._takeoff_btn.setEnabled(actual_enabled)
            self._land_btn.setEnabled(actual_enabled)
        else:
            self._bebop_takeoff_btn.setEnabled(actual_enabled)
            self._bebop_land_btn.setEnabled(actual_enabled)
            self._flip_btn.setEnabled(actual_enabled)

    @Slot(bool, str)
    def _on_flight_action_finished(self, success: bool, error: str) -> None:
        self._flight_action_running = False
        if error:
            self._show_progress(f"Error: {error}")
            if self._node:
                self._node.get_logger().error(f"Flight action failed: {error}")
        else:
            self._show_progress("Done")
            if self._node:
                self._node.get_logger().info("Flight action completed")
        self._set_flight_buttons_enabled(True)

    @Slot()
    def _arm(self) -> None:
        self._execute_flight_action("arm")

    @Slot()
    def _disarm(self) -> None:
        self._execute_flight_action("disarm")

    @Slot()
    def _takeoff(self) -> None:
        self._execute_flight_action("takeoff", self._altitude_spin.value())

    @Slot()
    def _land(self) -> None:
        self._execute_flight_action("land")

    @Slot()
    def _execute_move_to(self) -> None:
        if not self._drone or self._moveto_running:
            return

        from nectar.control.types import (
            AltitudeSource,
            MoveReference,
            NavigationStrategy,
        )

        reference_map = {
            "Body": MoveReference.BODY,
            "Takeoff": MoveReference.TAKEOFF,
        }
        strategy_map = {
            "PID": NavigationStrategy.PID,
            "PID Local": NavigationStrategy.PID_LOCAL,
            "Setpoint": NavigationStrategy.SETPOINT,
            "Setpoint Global": NavigationStrategy.SETPOINT_GLOBAL,
        }
        alt_source_map = {
            "Auto": AltitudeSource.AUTO,
            "Lidar": AltitudeSource.LIDAR,
            "Vision": AltitudeSource.VISION,
            "Rel Alt": AltitudeSource.REL_ALT,
        }

        ref_name = self._pos_reference_combo.currentText()
        reference = reference_map.get(ref_name, MoveReference.BODY)
        strat_name = self._pos_strategy_combo.currentText()
        strategy = strategy_map.get(strat_name, NavigationStrategy.PID)
        alt_name = self._pos_alt_source_combo.currentText()
        altitude_source = alt_source_map.get(alt_name, AltitudeSource.AUTO)

        x = self._pos_x_spin.value() if self._pos_x_check.isChecked() else None
        y = self._pos_y_spin.value() if self._pos_y_check.isChecked() else None
        z = self._pos_z_spin.value() if self._pos_z_check.isChecked() else None
        yaw = self._pos_yaw_spin.value() if self._pos_yaw_check.isChecked() else None
        precision = self._pos_precision_spin.value()
        timeout = self._pos_timeout_spin.value()

        if x is None and y is None and z is None and yaw is None:
            self._pos_status_label.setText("Enable at least one axis or yaw")
            return

        if self._node:
            parts = []
            if x is not None:
                parts.append(f"x={x:.1f}")
            if y is not None:
                parts.append(f"y={y:.1f}")
            if z is not None:
                parts.append(f"z={z:.1f}")
            if yaw is not None:
                parts.append(f"yaw={yaw:.0f}")
            self._node.get_logger().info(
                f"Position control: {', '.join(parts)} ref={ref_name} "
                f"strategy={strat_name} alt={alt_name} prec={precision:.2f}m"
            )

        self._moveto_running = True
        self._pos_status_label.setText("Moving...")
        self._set_position_control_enabled(False)

        self._moveto_thread = QThread()
        self._moveto_worker = MoveToWorker()
        self._moveto_worker.setup(
            self._drone,
            x,
            y,
            z,
            yaw,
            reference,
            timeout,
            precision,
            strategy,
            altitude_source,
        )
        self._moveto_worker.moveToThread(self._moveto_thread)

        self._moveto_thread.started.connect(self._moveto_worker.run)
        self._moveto_worker.progress.connect(self._on_moveto_progress)
        self._moveto_worker.finished.connect(self._on_moveto_finished)
        self._moveto_worker.finished.connect(self._moveto_thread.quit)

        self._moveto_thread.start()

    @Slot()
    def _cancel_move_to(self) -> None:
        if self._moveto_worker and self._moveto_running:
            self._moveto_worker.cancel()
            self._pos_status_label.setText("Cancelling...")

    @Slot(str)
    def _on_moveto_progress(self, message: str) -> None:
        self._pos_status_label.setText(message)

    @Slot(bool, str)
    def _on_moveto_finished(self, success: bool, message: str) -> None:
        self._moveto_running = False
        if success:
            self._pos_status_label.setText(message)
            if self._node:
                self._node.get_logger().info(f"Position control: {message}")
        else:
            self._pos_status_label.setText(f"Failed: {message}")
            if self._node:
                self._node.get_logger().warn(f"Position control failed: {message}")
        self._set_position_control_enabled(
            self._driver_connected
            and self._instance_initialized
            and self._controls_enabled
            and self._drone_type == "mavros"
        )

    @Slot()
    def _bebop_takeoff(self) -> None:
        self._execute_flight_action("takeoff", 1.0)

    @Slot()
    def _bebop_land(self) -> None:
        self._execute_flight_action("land")

    @Slot()
    def _show_flip_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS.surface_elevated};
                border: 1px solid {COLORS.border};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
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
                self._show_progress(f"Flip: {e}")

    @Slot()
    def _update_telemetry(self) -> None:
        if not self._drone:
            self._clear_telemetry()
            return

        import rclpy

        if self._node:
            rclpy.spin_once(self._node, timeout_sec=0)

        try:
            if self._drone_type == "mavros":
                self._update_mavros_telemetry()
        except Exception:
            pass

    def _update_mavros_telemetry(self) -> None:
        import numpy as np

        from nectar.control.types import AltitudeSource
        from nectar.utils.position_utils import PositionUtils

        d = self._drone

        # Status indicators
        fcu = d.is_fcu_connected
        if fcu is not None:
            self._status_fcu.set_status("active" if fcu else "inactive")
        armed = d.is_armed
        if armed is not None:
            self._status_armed.set_status("active" if armed else "inactive")

        # Local EKF pose (always available in both indoor/outdoor)
        local = d.local_pos
        if local:
            p = local.pose.position
            self._telem_local_x.setText(f"X: {p.x:.2f}")
            self._telem_local_y.setText(f"Y: {p.y:.2f}")
            self._telem_local_z.setText(f"Z: {p.z:.2f}")
            yaw_deg = np.degrees(PositionUtils.get_yaw_from_pose(local))
            self._telem_yaw.setText(f"Yaw: {yaw_deg:.1f}°")

        # GPS (outdoor only, safe — gps property raises for indoor)
        if not d.is_indoor:
            try:
                gps = d.gps
                if gps:
                    self._telem_lat.setText(f"Lat: {gps.latitude:.6f}")
                    self._telem_lon.setText(f"Lon: {gps.longitude:.6f}")
                    self._telem_gps_alt.setText(f"GpsAlt: {gps.altitude:.1f}")
                self._telem_heading.setText(f"Hdg: {d.heading:.1f}°")
                self._telem_rel_alt.setText(f"RelAlt: {d.rel_alt:.2f}")
            except Exception:
                pass
        else:
            self._telem_lat.setText("Lat: N/A")
            self._telem_lon.setText("Lon: N/A")
            self._telem_gps_alt.setText("GpsAlt: N/A")
            self._telem_heading.setText("Hdg: N/A")
            self._telem_rel_alt.setText("RelAlt: N/A")

        # Altitude sources
        alt = d.get_altitude()
        self._telem_height.setText(f"Height: {alt:.2f}" if alt is not None else "Height: --")

        lidar = d.get_altitude(AltitudeSource.LIDAR)
        self._telem_lidar.setText(f"LiDAR: {lidar:.2f}" if lidar is not None else "LiDAR: --")

        self._telem_mode.setText(f"Mode: {d.flight_mode or '--'}")

    def _clear_telemetry(self) -> None:
        if self._status_fcu.isVisible():
            self._status_fcu.set_status("inactive")
        if self._status_armed.isVisible():
            self._status_armed.set_status("inactive")
        for w in [
            self._telem_local_x,
            self._telem_local_y,
            self._telem_local_z,
            self._telem_yaw,
            self._telem_height,
            self._telem_lidar,
            self._telem_lat,
            self._telem_lon,
            self._telem_gps_alt,
            self._telem_heading,
            self._telem_rel_alt,
        ]:
            w.setText(w.text().split(":")[0] + ": --")
        self._telem_mode.setText("Mode: --")

    @Slot()
    def _send_velocity_command(self) -> None:
        if not self._controls_enabled or not self._drone:
            return

        vx, vy, vz, vyaw = 0.0, 0.0, 0.0, 0.0

        for key, (axis, direction) in self.KEY_MAP.items():
            if self._key_states.get(key, False):
                if axis == "vx":
                    vx = direction
                elif axis == "vy":
                    vy = direction
                elif axis == "vz":
                    vz = direction
                elif axis == "vyaw":
                    vyaw = direction

        vx *= self._vx_slider.value()
        vy *= self._vy_slider.value()
        vz *= self._vz_slider.value()
        vyaw *= self._vyaw_slider.value()

        current_cmd = (vx, vy, vz, vyaw)
        self._velocity_status_label.setText(
            f"Cmd: vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} vyaw={vyaw:.2f}"
        )

        cmd_changed = current_cmd != self._last_velocity_cmd
        has_movement = any(v != 0.0 for v in current_cmd)

        if cmd_changed and self._node:
            if has_movement:
                self._node.get_logger().debug(
                    f"Velocity: vx={vx:.2f} vy={vy:.2f} vz={vz:.2f} vyaw={vyaw:.2f}"
                )
            elif any(v != 0.0 for v in self._last_velocity_cmd):
                self._node.get_logger().debug("Velocity: stopped")

        should_send = has_movement or (cmd_changed and not has_movement)

        self._last_velocity_cmd = current_cmd

        if not should_send:
            return

        try:
            from nectar.control import MoveReference

            reference_map = {
                "Body": MoveReference.BODY,
                "World": MoveReference.WORLD,
                "Takeoff": MoveReference.TAKEOFF,
            }
            reference = reference_map.get(
                self._vel_reference_combo.currentText(), MoveReference.BODY
            )
            self._drone.move_velocity(vx, vy, vz, vyaw, reference=reference)
        except Exception:
            pass

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()
        if key in self._key_buttons:
            if self._controls_enabled:
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

        if self._moveto_thread and self._moveto_thread.isRunning():
            self._cancel_move_to()
            self._moveto_thread.quit()
            self._moveto_thread.wait(1000)

        if self._flight_thread and self._flight_thread.isRunning():
            self._flight_thread.quit()
            self._flight_thread.wait(1000)

        self._cleanup_instance()
