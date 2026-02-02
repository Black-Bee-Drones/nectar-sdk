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
    ) -> None:
        self._drone = drone
        self._x = x
        self._y = y
        self._z = z
        self._yaw = yaw
        self._reference = reference
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
            self.progress.emit("Moving to position...")
            success = self._drone.move_to(
                x=self._x,
                y=self._y,
                z=self._z,
                yaw=self._yaw,
                reference=self._reference,
                timeout=self._timeout,
                precision=self._precision,
            )
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
            elif success:
                self.finished.emit(True, "Position reached")
            else:
                self.finished.emit(False, "Timeout")
        except Exception as e:
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
            else:
                self.finished.emit(False, str(e))


class ControlTab(QWidget):
    """
    Drone control tab with keyboard controls and velocity management.

    Separates driver connection from drone instance initialization:
    - Driver: Start/stop the ROS2 driver process (mavros or bebop)
    - Instance: Create/destroy drone object with configuration
    - Controls: Only enabled when both driver running AND instance initialized
    """

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
        self._moveto_thread: Optional[QThread] = None
        self._moveto_worker: Optional[MoveToWorker] = None
        self._moveto_running: bool = False

        self._setup_ui()
        self._setup_timers()
        self._setup_status_checker()
        self._update_ui_state()
        self._update_capability_panels()
        self._update_status_indicators()
        self.setFocusPolicy(Qt.StrongFocus)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._create_left_panel())
        splitter.addWidget(self._create_right_panel())
        splitter.setSizes([360, 640])

        layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(420)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(8)

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
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._create_velocity_control_panel())
        layout.addWidget(self._create_position_control_panel())
        layout.addWidget(self._create_telemetry_panel())

        return container

    def _create_connection_panel(self) -> QGroupBox:
        group = QGroupBox("Connection")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Drone type selector
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        lbl = QLabel("Drone:")
        lbl.setProperty("secondary", True)
        lbl.setFixedWidth(50)
        self._drone_combo = QComboBox()
        self._drone_combo.addItems(["Mavros", "Bebop"])
        self._drone_combo.currentTextChanged.connect(self._on_drone_type_changed)
        type_row.addWidget(lbl)
        type_row.addWidget(self._drone_combo, 1)
        layout.addLayout(type_row)

        # Config panel
        self._config_panel = DroneConfigPanel()
        self._config_panel.set_drone_type("mavros")
        layout.addWidget(self._config_panel)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {COLORS.border};")
        layout.addWidget(sep)

        # Buttons row
        btn_layout = QGridLayout()
        btn_layout.setSpacing(6)

        self._driver_btn = QPushButton("Connect Driver")
        self._driver_btn.setProperty("accent", True)
        self._driver_btn.clicked.connect(self._toggle_driver)
        btn_layout.addWidget(self._driver_btn, 0, 0)

        self._instance_btn = QPushButton("Initialize")
        self._instance_btn.setEnabled(False)
        self._instance_btn.clicked.connect(self._toggle_instance)
        btn_layout.addWidget(self._instance_btn, 0, 1)

        layout.addLayout(btn_layout)

        # Progress label
        self._progress_label = QLabel("")
        self._progress_label.setProperty("secondary", True)
        self._progress_label.setWordWrap(True)
        layout.addWidget(self._progress_label)

        return group

    def _create_status_panel(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QGridLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 12, 8, 8)

        self._status_driver = StatusIndicator("Driver", "inactive")
        self._status_instance = StatusIndicator("Instance", "inactive")
        self._status_fcu = StatusIndicator("FCU", "inactive")
        self._status_armed = StatusIndicator("Armed", "inactive")

        layout.addWidget(self._status_driver, 0, 0)
        layout.addWidget(self._status_instance, 0, 1)
        layout.addWidget(self._status_fcu, 1, 0)
        layout.addWidget(self._status_armed, 1, 1)

        return group

    def _update_status_indicators(self) -> None:
        """Update status indicators based on drone capabilities."""
        has_fcu = self._drone_type == "mavros"
        self._status_fcu.setVisible(has_fcu)
        self._status_armed.setVisible(has_fcu)

    def _create_flight_controls(self) -> QGroupBox:
        group = QGroupBox("Flight")
        layout = QHBoxLayout(group)
        layout.setSpacing(6)

        self._enable_btn = QPushButton("Enable Controls")
        self._enable_btn.setCheckable(True)
        self._enable_btn.setEnabled(False)
        self._enable_btn.clicked.connect(self._toggle_controls)

        self._emergency_btn = QPushButton("STOP")
        self._emergency_btn.setProperty("danger", True)
        self._emergency_btn.setEnabled(False)
        self._emergency_btn.clicked.connect(self._emergency_stop)

        layout.addWidget(self._enable_btn, 1)
        layout.addWidget(self._emergency_btn)

        return group

    def _create_drone_specific_controls(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._mavros_group = self._create_mavros_controls()
        self._bebop_group = self._create_bebop_controls()

        layout.addWidget(self._mavros_group)
        layout.addWidget(self._bebop_group)

        self._bebop_group.setVisible(False)
        return container

    def _create_mavros_controls(self) -> QGroupBox:
        group = QGroupBox("Mavros Actions")
        layout = QGridLayout(group)
        layout.setSpacing(4)

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

        layout.addWidget(self._arm_btn, 0, 0)
        layout.addWidget(self._disarm_btn, 0, 1)
        layout.addWidget(self._takeoff_btn, 1, 0)
        layout.addWidget(self._land_btn, 1, 1)

        # Arm + Takeoff
        self._arm_takeoff_btn = QPushButton("Arm + Takeoff")
        self._arm_takeoff_btn.setProperty("accent", True)
        self._arm_takeoff_btn.setEnabled(False)
        self._arm_takeoff_btn.clicked.connect(self._arm_takeoff)
        layout.addWidget(self._arm_takeoff_btn, 2, 0, 1, 2)

        # Altitude
        alt_row = QHBoxLayout()
        alt_row.setSpacing(6)
        alt_lbl = QLabel("Alt:")
        alt_lbl.setProperty("secondary", True)
        self._altitude_spin = QDoubleSpinBox()
        self._altitude_spin.setRange(0.5, 10.0)
        self._altitude_spin.setValue(1.5)
        self._altitude_spin.setSingleStep(0.1)
        self._altitude_spin.setSuffix(" m")
        alt_row.addWidget(alt_lbl)
        alt_row.addWidget(self._altitude_spin, 1)
        layout.addLayout(alt_row, 3, 0, 1, 2)

        return group

    def _create_bebop_controls(self) -> QGroupBox:
        group = QGroupBox("Bebop Actions")
        layout = QGridLayout(group)
        layout.setSpacing(4)

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

    def _create_velocity_control_panel(self) -> QGroupBox:
        self._velocity_group = QGroupBox("Velocity Control")
        main_layout = QVBoxLayout(self._velocity_group)
        main_layout.setSpacing(6)

        # Top: Keys + Sliders
        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        # Keys section
        keys_widget = QWidget()
        keys_layout = QHBoxLayout(keys_widget)
        keys_layout.setSpacing(16)
        keys_layout.setContentsMargins(0, 0, 0, 0)

        # WASD
        wasd_layout = QVBoxLayout()
        wasd_layout.setSpacing(2)
        wasd_grid = QGridLayout()
        wasd_grid.setSpacing(2)

        self._key_w = KeyButton("W", Qt.Key_W)
        self._key_a = KeyButton("A", Qt.Key_A)
        self._key_s = KeyButton("S", Qt.Key_S)
        self._key_d = KeyButton("D", Qt.Key_D)

        wasd_grid.addWidget(self._key_w, 0, 1)
        wasd_grid.addWidget(self._key_a, 1, 0)
        wasd_grid.addWidget(self._key_s, 1, 1)
        wasd_grid.addWidget(self._key_d, 1, 2)

        wasd_label = QLabel("Z/Yaw")
        wasd_label.setProperty("muted", True)
        wasd_label.setAlignment(Qt.AlignCenter)

        wasd_layout.addLayout(wasd_grid)
        wasd_layout.addWidget(wasd_label)

        # Arrows
        arrows_layout = QVBoxLayout()
        arrows_layout.setSpacing(2)
        arrows_grid = QGridLayout()
        arrows_grid.setSpacing(2)

        self._key_up = KeyButton("↑", Qt.Key_Up)
        self._key_left = KeyButton("←", Qt.Key_Left)
        self._key_down = KeyButton("↓", Qt.Key_Down)
        self._key_right = KeyButton("→", Qt.Key_Right)

        arrows_grid.addWidget(self._key_up, 0, 1)
        arrows_grid.addWidget(self._key_left, 1, 0)
        arrows_grid.addWidget(self._key_down, 1, 1)
        arrows_grid.addWidget(self._key_right, 1, 2)

        arrows_label = QLabel("X/Y")
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

        # Sliders section
        sliders_widget = QWidget()
        sliders_layout = QHBoxLayout(sliders_widget)
        sliders_layout.setSpacing(8)
        sliders_layout.setContentsMargins(0, 0, 0, 0)

        self._vx_slider = LabeledSlider("Vx", 0.0, 1.0, 0.2)
        self._vy_slider = LabeledSlider("Vy", 0.0, 1.0, 0.2)
        self._vz_slider = LabeledSlider("Vz", 0.0, 1.0, 0.2)
        self._vyaw_slider = LabeledSlider("Vψ", 0.0, 1.0, 0.2)

        self._velocity_sliders = [
            self._vx_slider,
            self._vy_slider,
            self._vz_slider,
            self._vyaw_slider,
        ]

        for slider in self._velocity_sliders:
            slider.setEnabled(False)
            sliders_layout.addWidget(slider)

        top_layout.addWidget(keys_widget)
        top_layout.addWidget(sliders_widget, 1)

        main_layout.addLayout(top_layout)

        # Options row
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)

        ref_lbl = QLabel("Ref:")
        ref_lbl.setProperty("secondary", True)
        self._vel_reference_combo = QComboBox()
        self._vel_reference_combo.addItems(["Body", "World"])
        self._vel_reference_combo.setCurrentIndex(0)
        self._vel_reference_combo.setMaximumWidth(80)

        options_layout.addWidget(ref_lbl)
        options_layout.addWidget(self._vel_reference_combo)
        options_layout.addStretch()

        help_label = QLabel("WASD: Z/Yaw  |  Arrows: X/Y")
        help_label.setProperty("muted", True)
        options_layout.addWidget(help_label)

        main_layout.addLayout(options_layout)

        return self._velocity_group

    def _create_position_control_panel(self) -> QGroupBox:
        self._position_group = QGroupBox("Position Control")
        layout = QVBoxLayout(self._position_group)
        layout.setSpacing(6)

        # Position inputs grid
        grid = QGridLayout()
        grid.setSpacing(4)

        self._pos_x_check = QCheckBox("X")
        self._pos_x_check.setChecked(False)
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
        self._pos_y_check.setChecked(False)
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
        self._pos_z_check.setChecked(False)
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
        self._pos_yaw_check.setChecked(False)
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

        # Options row
        options_layout = QHBoxLayout()
        options_layout.setSpacing(6)

        ref_lbl = QLabel("Ref:")
        ref_lbl.setProperty("secondary", True)
        self._pos_reference_combo = QComboBox()
        self._pos_reference_combo.addItems(["Body", "World", "Takeoff"])
        self._pos_reference_combo.setCurrentIndex(0)
        self._pos_reference_combo.setMaximumWidth(80)

        prec_lbl = QLabel("Prec:")
        prec_lbl.setProperty("secondary", True)
        self._pos_precision_spin = QDoubleSpinBox()
        self._pos_precision_spin.setRange(0.05, 2.0)
        self._pos_precision_spin.setValue(0.2)
        self._pos_precision_spin.setSingleStep(0.1)
        self._pos_precision_spin.setDecimals(2)
        self._pos_precision_spin.setSuffix(" m")
        self._pos_precision_spin.setMaximumWidth(80)

        timeout_lbl = QLabel("T/O:")
        timeout_lbl.setProperty("secondary", True)
        self._pos_timeout_spin = QDoubleSpinBox()
        self._pos_timeout_spin.setRange(5.0, 300.0)
        self._pos_timeout_spin.setValue(60.0)
        self._pos_timeout_spin.setSingleStep(10.0)
        self._pos_timeout_spin.setDecimals(0)
        self._pos_timeout_spin.setSuffix(" s")
        self._pos_timeout_spin.setMaximumWidth(80)

        options_layout.addWidget(ref_lbl)
        options_layout.addWidget(self._pos_reference_combo)
        options_layout.addWidget(prec_lbl)
        options_layout.addWidget(self._pos_precision_spin)
        options_layout.addWidget(timeout_lbl)
        options_layout.addWidget(self._pos_timeout_spin)
        options_layout.addStretch()

        layout.addLayout(options_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self._pos_go_btn = QPushButton("Go")
        self._pos_go_btn.setProperty("accent", True)
        self._pos_go_btn.setEnabled(False)
        self._pos_go_btn.clicked.connect(self._execute_move_to)
        btn_layout.addWidget(self._pos_go_btn, 1)

        self._pos_cancel_btn = QPushButton("Cancel")
        self._pos_cancel_btn.setEnabled(False)
        self._pos_cancel_btn.clicked.connect(self._cancel_move_to)
        btn_layout.addWidget(self._pos_cancel_btn)

        layout.addLayout(btn_layout)

        # Status
        self._pos_status_label = QLabel("")
        self._pos_status_label.setProperty("secondary", True)
        layout.addWidget(self._pos_status_label)

        self._position_control_widgets = [
            self._pos_x_check,
            self._pos_y_check,
            self._pos_z_check,
            self._pos_yaw_check,
            self._pos_reference_combo,
            self._pos_precision_spin,
            self._pos_timeout_spin,
            self._pos_go_btn,
        ]

        return self._position_group

    def _create_telemetry_panel(self) -> QGroupBox:
        self._telemetry_group = QGroupBox("Telemetry")
        layout = QGridLayout(self._telemetry_group)
        layout.setSpacing(4)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)

        # Row 0: Mode
        self._mode_label = QLabel("Mode: --")
        self._mode_label.setProperty("secondary", True)
        layout.addWidget(self._mode_label, 0, 0, 1, 3)

        # Row 1: Position
        self._pos_x_label = QLabel("X: --")
        self._pos_y_label = QLabel("Y: --")
        self._pos_z_label = QLabel("Z: --")
        layout.addWidget(self._pos_x_label, 1, 0)
        layout.addWidget(self._pos_y_label, 1, 1)
        layout.addWidget(self._pos_z_label, 1, 2)

        # Row 2: Altitude sources
        self._alt_height_label = QLabel("Height: --")
        self._alt_lidar_label = QLabel("LiDAR: --")
        self._alt_rel_label = QLabel("RelAlt: --")
        layout.addWidget(self._alt_height_label, 2, 0)
        layout.addWidget(self._alt_lidar_label, 2, 1)
        layout.addWidget(self._alt_rel_label, 2, 2)

        # Row 3: Orientation
        self._yaw_label = QLabel("Yaw: --")
        self._heading_label = QLabel("Heading: --")
        self._no_telemetry_label = QLabel("")
        self._no_telemetry_label.setProperty("muted", True)
        layout.addWidget(self._yaw_label, 3, 0)
        layout.addWidget(self._heading_label, 3, 1)
        layout.addWidget(self._no_telemetry_label, 3, 2)

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
        self._set_position_control_enabled(can_control and self._drone_type == "mavros")

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

        self._update_capability_panels()
        self._update_status_indicators()

        if self._status_checker:
            self._status_checker.set_drone_type(self._drone_type)

    def _update_capability_panels(self) -> None:
        has_position_control = self._drone_type == "mavros"
        has_telemetry = self._drone_type == "mavros"

        self._position_group.setVisible(has_position_control)
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
                if not self._drone.arm():
                    self._show_progress("Arm command failed")
            except TimeoutError as e:
                self._show_progress("Arm timeout: service unavailable")
                self._log_error(f"Arm failed: {e}")
            except Exception as e:
                self._show_progress(f"Arm failed: {e}")
                self._log_error(f"Arm failed: {e}")

    @Slot()
    def _disarm(self) -> None:
        if self._drone:
            try:
                if not self._drone.disarm():
                    self._show_progress("Disarm command failed")
            except TimeoutError as e:
                self._show_progress("Disarm timeout: service unavailable")
                self._log_error(f"Disarm failed: {e}")
            except Exception as e:
                self._show_progress(f"Disarm failed: {e}")
                self._log_error(f"Disarm failed: {e}")

    @Slot()
    def _takeoff(self) -> None:
        if self._drone:
            try:
                if not self._drone.takeoff(self._altitude_spin.value()):
                    self._show_progress("Takeoff failed")
            except TimeoutError as e:
                self._show_progress("Takeoff timeout: service unavailable")
                self._log_error(f"Takeoff failed: {e}")
            except Exception as e:
                self._show_progress(f"Takeoff failed: {e}")
                self._log_error(f"Takeoff failed: {e}")

    @Slot()
    def _land(self) -> None:
        if self._drone:
            try:
                if not self._drone.land():
                    self._show_progress("Land failed")
            except TimeoutError as e:
                self._show_progress("Land timeout: service unavailable")
                self._log_error(f"Land failed: {e}")
            except Exception as e:
                self._show_progress(f"Land failed: {e}")
                self._log_error(f"Land failed: {e}")

    @Slot()
    def _arm_takeoff(self) -> None:
        if self._drone:
            try:
                if not self._drone.arm():
                    self._show_progress("Arm failed")
                    return
                if not self._drone.takeoff(self._altitude_spin.value()):
                    self._show_progress("Takeoff failed")
            except TimeoutError as e:
                self._show_progress("Timeout: service unavailable")
                self._log_error(f"Arm+Takeoff failed: {e}")
            except Exception as e:
                self._show_progress(f"Arm+Takeoff failed: {e}")
                self._log_error(f"Arm+Takeoff failed: {e}")

    @Slot()
    def _execute_move_to(self) -> None:
        if not self._drone or self._moveto_running:
            return

        from mirela_sdk.control.types import MoveReference

        reference_map = {
            "Body": MoveReference.BODY,
            "World": MoveReference.WORLD,
            "Takeoff": MoveReference.TAKEOFF,
        }
        reference = reference_map.get(
            self._pos_reference_combo.currentText(), MoveReference.BODY
        )

        x = self._pos_x_spin.value() if self._pos_x_check.isChecked() else None
        y = self._pos_y_spin.value() if self._pos_y_check.isChecked() else None
        z = self._pos_z_spin.value() if self._pos_z_check.isChecked() else None
        yaw = self._pos_yaw_spin.value() if self._pos_yaw_check.isChecked() else None
        precision = self._pos_precision_spin.value()
        timeout = self._pos_timeout_spin.value()

        if x is None and y is None and z is None:
            self._pos_status_label.setText("Enable at least one axis (X, Y, or Z)")
            return

        self._moveto_running = True
        self._pos_status_label.setText("Moving...")
        self._set_position_control_enabled(False)

        self._moveto_thread = QThread()
        self._moveto_worker = MoveToWorker()
        self._moveto_worker.setup(
            self._drone, x, y, z, yaw, reference, timeout, precision
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
        else:
            self._pos_status_label.setText(f"Failed: {message}")
        self._set_position_control_enabled(
            self._driver_connected
            and self._instance_initialized
            and self._drone_type == "mavros"
        )

    @Slot()
    def _bebop_takeoff(self) -> None:
        if self._drone:
            try:
                self._drone.takeoff(1.0)
            except TimeoutError as e:
                self._show_progress("Takeoff timeout: service unavailable")
                self._log_error(f"Takeoff failed: {e}")
            except Exception as e:
                self._show_progress(f"Takeoff failed: {e}")
                self._log_error(f"Takeoff failed: {e}")

    @Slot()
    def _bebop_land(self) -> None:
        if self._drone:
            try:
                self._drone.land()
            except TimeoutError as e:
                self._show_progress("Land timeout: service unavailable")
                self._log_error(f"Land failed: {e}")
            except Exception as e:
                self._show_progress(f"Land failed: {e}")
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
                self._log_error(f"Flip failed: {e}")

    @Slot()
    def _update_telemetry(self) -> None:
        if not self._drone:
            self._clear_telemetry()
            return

        try:
            self._update_mavros_telemetry()
        except Exception:
            pass

        try:
            self._update_bebop_telemetry()
        except Exception:
            pass

    def _update_mavros_telemetry(self) -> None:
        """Update telemetry for MavrosDrone."""
        if self._drone_type != "mavros":
            return

        # Use generic properties from BaseDrone
        fcu_connected = self._drone.is_fcu_connected
        if fcu_connected is not None:
            self._status_fcu.set_status("active" if fcu_connected else "inactive")

        armed = self._drone.is_armed
        if armed is not None:
            self._status_armed.set_status("active" if armed else "inactive")

        mode = self._drone.flight_mode
        self._mode_label.setText(f"Mode: {mode or '--'}")

        if hasattr(self._drone, "height"):
            self._alt_height_label.setText(f"Height: {self._drone.height:.2f}m")

        if hasattr(self._drone, "lidar_alt"):
            lidar = self._drone.lidar_alt
            if lidar is not None:
                self._alt_lidar_label.setText(f"LiDAR: {lidar:.2f}m")
            else:
                self._alt_lidar_label.setText("LiDAR: N/A")

        is_indoor = getattr(self._drone, "is_indoor", False)

        if is_indoor:
            vision_pos = getattr(self._drone, "vision_pos", None)
            if vision_pos:
                pos = vision_pos.pose.pose.position
                self._pos_x_label.setText(f"X: {pos.x:.2f}m")
                self._pos_y_label.setText(f"Y: {pos.y:.2f}m")
                self._pos_z_label.setText(f"Z: {pos.z:.2f}m")

                from mirela_sdk.utils.position_utils import PositionUtils
                import numpy as np

                yaw_rad = PositionUtils.get_yaw_from_pose(vision_pos)
                self._yaw_label.setText(f"Yaw: {np.degrees(yaw_rad):.1f}°")

            self._heading_label.setText("Heading: N/A")
            self._alt_rel_label.setText("RelAlt: N/A")
        else:
            try:
                gps = self._drone._gps
                if gps:
                    self._pos_x_label.setText(f"Lat: {gps.latitude:.6f}°")
                    self._pos_y_label.setText(f"Lon: {gps.longitude:.6f}°")
                    self._pos_z_label.setText(f"Alt: {gps.altitude:.1f}m")
                else:
                    self._pos_x_label.setText("Lat: --")
                    self._pos_y_label.setText("Lon: --")
                    self._pos_z_label.setText("Alt: --")
            except Exception:
                self._pos_x_label.setText("Lat: --")
                self._pos_y_label.setText("Lon: --")
                self._pos_z_label.setText("Alt: --")

            try:
                heading = self._drone._heading
                if heading:
                    self._heading_label.setText(f"Heading: {heading.data:.1f}°")
                    self._yaw_label.setText(f"Yaw: {heading.data:.1f}°")
                else:
                    self._heading_label.setText("Heading: --")
                    self._yaw_label.setText("Yaw: --")
            except Exception:
                self._heading_label.setText("Heading: --")
                self._yaw_label.setText("Yaw: --")

            try:
                rel_alt = self._drone._rel_alt
                if rel_alt:
                    self._alt_rel_label.setText(f"RelAlt: {rel_alt.data:.2f}m")
                else:
                    self._alt_rel_label.setText("RelAlt: --")
            except Exception:
                self._alt_rel_label.setText("RelAlt: --")

    def _update_bebop_telemetry(self) -> None:
        """Update telemetry for BebopDrone (limited telemetry available)."""
        if self._drone_type != "bebop":
            return

        # Bebop has no telemetry feedback via SDK
        self._mode_label.setText("Mode: --")
        self._no_telemetry_label.setText("Telemetry N/A")

        self._pos_x_label.setText("X: --")
        self._pos_y_label.setText("Y: --")
        self._pos_z_label.setText("Z: --")
        self._alt_height_label.setText("Height: --")
        self._alt_lidar_label.setText("LiDAR: --")
        self._alt_rel_label.setText("RelAlt: --")
        self._yaw_label.setText("Yaw: --")
        self._heading_label.setText("Heading: --")

    def _clear_telemetry(self) -> None:
        """Clear all telemetry displays."""
        if self._status_fcu.isVisible():
            self._status_fcu.set_status("inactive")
        if self._status_armed.isVisible():
            self._status_armed.set_status("inactive")
        self._mode_label.setText("Mode: --")

        self._pos_x_label.setText("X: --")
        self._pos_y_label.setText("Y: --")
        self._pos_z_label.setText("Z: --")
        self._alt_height_label.setText("Height: --")
        self._alt_lidar_label.setText("LiDAR: --")
        self._alt_rel_label.setText("RelAlt: --")
        self._yaw_label.setText("Yaw: --")
        self._heading_label.setText("Heading: --")
        self._no_telemetry_label.setText("")

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

        try:
            from mirela_sdk.control import MoveReference

            reference_map = {"Body": MoveReference.BODY, "World": MoveReference.WORLD}
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

        if self._moveto_thread and self._moveto_thread.isRunning():
            self._cancel_move_to()
            self._moveto_thread.quit()
            self._moveto_thread.wait(1000)

        self._cleanup_instance()
