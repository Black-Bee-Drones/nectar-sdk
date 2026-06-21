# Interface Module

Qt6/PySide6-based graphical user interface for drone control, computer vision, and ROS2 system tools.

<div align="center">

![Nectar SDK Interface](../../../assets/ui_app.png)

*Nectar SDK GUI - Control, Vision, and ROS2 tools in one interface*

</div>

## Quick Start

```python
from nectar.interface import main

# Launch the GUI
main()
```

Or from command line:

```bash
ros2 run nectar gui
```

## Features

### Control Tab

Drone control interface with keyboard-based velocity control and position navigation.

**Connection Flow**:
1. **Select Firmware + Link**: Pick the firmware (ArduPilot, PX4, Bebop, Crazyflie) and, for ArduPilot/PX4, the transport (MAVROS, MAVLink, or DDS). The config panel adapts to the selection.
2. **Connect Driver**: Starts the background driver process — MAVROS (`apm.launch` / `px4.launch`), the Crazyflie server, the Bebop driver, or `MicroXRCEAgent` for PX4 DDS. Direct-MAVLink links (ArduPilot/PX4) open the FCU link inside the instance, so this step is skipped.
3. **Initialize Instance**: Creates the drone object with the configuration selected in the panel.
4. **Ready**: Flight controls enabled.

**Status Indicators**:
- **Driver**: ROS2 driver / agent process running
- **Instance**: Drone object initialized
- **FCU**: Flight controller connected (FCU vehicles)
- **Armed**: Motors armed state (FCU vehicles / Crazyflie)

**Velocity Control**:
- **Keyboard**: W/S (up/down), A/D (yaw), Arrow keys (forward/back/left/right)
- **Sliders**: Adjust max velocity per axis (Vx, Vy, Vz, Vyaw)
- **Reference Frame**: Body, World, or Takeoff

**Position Control** (FCU vehicles and Crazyflie):
- Navigate to target position with X, Y, Z, Yaw offsets
- Reference frames: Body or Takeoff
- Configurable precision and timeout

**Backends** (Firmware + Link):
- **ArduPilot / MAVROS** (`mavros`): Full ArduPilot control (arm, takeoff, land, velocity, position, telemetry) over the MAVROS bridge
- **ArduPilot / MAVLink** (`mavlink`): Same control over a direct pymavlink link (no MAVROS); set the connection string and, for indoor flight, the vision-pose topic preset (`/visual_slam/tracking/vo_pose_covariance`)
- **PX4 / MAVROS** (`px4`): PX4 over MAVROS with OFFBOARD setpoint streaming; the connection defaults to the PX4 offboard endpoint (`udp://:14540@127.0.0.1:14580` for SITL)
- **PX4 / MAVLink** (`px4_mavlink`): PX4 over a direct pymavlink link (no MAVROS); defaults to `udp:0.0.0.0:14540`
- **PX4 / DDS** (`px4_dds`): PX4 over native uXRCE-DDS. **Connect Driver** launches `MicroXRCEAgent` on the configured UDP port (default 8888); an agent already started elsewhere (e.g. `make sim-bridge FIRMWARE=px4 PROTOCOL=dds`) is detected automatically. Readiness is the appearance of PX4's `/fmu/*` topics (agent + FCU client connected), not a process or session name, so detection works regardless of how the agent was started
- **Bebop**: Basic control (takeoff, land, velocity, flips)
- **Crazyflie**: Takeoff, land, velocity, and onboard position (`goTo`)

The MAVROS and MAVLink panels are shared by ArduPilot and PX4 and adapt to the firmware: the connection default switches to the PX4 offboard endpoint, and the PID and setpoint preset lists are loaded from [`control/px4/config`](../control/px4/config) instead of [`control/ardupilot/config`](../control/ardupilot/config) (both include the `*_sim_*` SITL presets). The setpoint config exposes each firmware's speed/accel limits — ArduPilot `WPNAV`/`GUID_OPTIONS` or PX4 `MPC_*` — with **Apply setpoint params to FCU** pushing them on arm. The uXRCE-DDS panel (`px4_dds`) shows only the PID preset, since PX4 parameters are not bridged over uXRCE-DDS.

### Vision Tab

Real-time computer vision processing with multiple camera sources and filters.

**Camera Sources**: Webcam, RealSense, OAK-D, ROS topic, File

**Filter Categories**:
- **Color**: HSV color filtering with calibration
- **Edge**: Canny edge detection, contours
- **Blur/Transform**: Gaussian blur, sharpen, rotate, resize
- **Morphology**: Erode, dilate, adaptive threshold, histogram equalization
- **Effects**: Pencil sketch, stylization, cartoonify, Hough lines/circles, optical flow
- **AI**: Hand tracking (MediaPipe), face mesh (MediaPipe)
- **Markers**: ArUco detection (17 dictionary types)

**Depth Estimation** (depth cameras):
- Real-time distance measurement
- Colorized depth visualization
- Click-to-measure distance

### ROS Tab

ROS2 system introspection and interaction tools.

**Topics**:
- Browse, subscribe, and publish messages
- Real-time message viewing
- Auto-detect QoS settings

**Services**:
- Browse and call services
- Custom request/response handling

**Parameters**:
- View and modify node parameters
- Real-time updates

**Plot**:
- Real-time plotting of numeric fields
- Multiple plots, pause/resume
- Export to CSV

## Architecture

### High-Level Structure

```mermaid
classDiagram
    class NectarApp {
        +main()$
    }

    class ROSExecutor {
        +node Node
        +start(node_name) bool
        +shutdown()
    }

    class ControlTab {
        +set_node(node)
        +cleanup()
    }

    class VisionTab {
        +set_node(node)
        +cleanup()
    }

    class ROSTab {
        +set_node(node)
        +cleanup()
    }

    NectarApp *-- ROSExecutor
    NectarApp *-- ControlTab
    NectarApp *-- VisionTab
    NectarApp *-- ROSTab
```

### Thread Model

```mermaid
flowchart TB
    subgraph MainThread["Main Thread (Qt Event Loop)"]
        UI[UI Updates]
        Timers[QTimers]
    end

    subgraph ROSThread["ROS2 Thread"]
        Executor[MultiThreadedExecutor]
        Callbacks[ROS Callbacks]
    end

    subgraph WorkerThreads["Worker Threads"]
        Workers[DriverWorker, MoveToWorker, etc.]
    end

    UI --> |"QTimer"| ROSThread
    UI --> |"Start"| WorkerThreads
    WorkerThreads --> |"Signals"| UI
    ROSThread --> |"Signals"| UI
```

**Key Points**:
- ROS2 executor runs in separate thread
- Blocking operations (driver start, navigation) use worker threads
- Velocity commands sent via QTimer (50ms interval)
- All UI updates happen in main thread

## For Developers

### Widgets

Reusable UI components available in `nectar.interface.widgets`:

| Widget | Purpose |
|--------|---------|
| `Card` | Elevated container with rounded corners |
| `StatusIndicator` | Status dot with label (active/inactive/warning/error) |
| `LabeledSlider` | Vertical slider with label and value display |
| `CollapsibleSection` | Expandable/collapsible section |
| `VideoDisplay` | OpenCV frame display with click support |
| `ImageViewer` | Video display with info label |
| `DualVideoDisplay` | RGB and depth display |
| `DroneConfigPanel` | Drone configuration UI |
| `DetectionConfigPanel` | Object detection model configuration |
| `MessageFieldEditor` | ROS message field editor |
| `ParameterReconfigureWidget` | ROS2 parameter editor |

**Example**:

```python
from nectar.interface import Card, StatusIndicator, LabeledSlider

card = Card()
card.add_widget(StatusIndicator("Status", "active"))
card.add_widget(LabeledSlider("Speed", 0.0, 1.0, 0.5))
```

### ROSExecutor

Manages ROS2 node and executor in background thread:

```python
from nectar.interface import ROSExecutor

executor = ROSExecutor()
executor.start("my_node")
node = executor.node  # Access ROS2 node
executor.shutdown()
```

**Signals**:
- `status_changed(bool)`: ROS2 connection status
- `error_occurred(str)`: ROS2 errors

### Worker Threads

Long-running operations use QThread workers to avoid UI freezes:

- **DriverWorker**: Start/stop ROS2 driver processes
- **DroneInstanceWorker**: Initialize drone objects
- **MoveToWorker**: Position navigation (blocking PID loop)
- **FlightActionWorker**: Service calls (arm, takeoff, land)
- **CameraInitWorker**: Camera initialization

**Pattern**:

```python
worker = MyWorker()
worker_thread = QThread()
worker.moveToThread(worker_thread)
worker.finished.connect(worker_thread.quit)
worker_thread.started.connect(worker.run)
worker_thread.start()
```

### Service Calls

ROS2 services use async pattern to avoid deadlocks. The SDK's `BaseDrone._wait` is the cooperative tick — it spins when the SDK owns ROS, sleeps when the user's executor (e.g. `ROSExecutor`) is already running. Either way, `node.executor` is preserved so later subscriptions still wake the right executor:

```python
future = service.call_async(request)
while not future.done():
    self._wait(0.05)  # spin (SDK-owned) or sleep (user-owned executor)
result = future.result()
```

### Module Structure

```
interface/
├── app.py                # NectarApp (main window)
├── ros_executor.py       # ROS2-Qt integration
├── theme.py              # Styling and colors
│
├── tabs/
│   ├── control_tab.py    # Drone control
│   ├── vision_tab.py     # Camera and filters
│   └── ros_tab.py        # ROS2 tools
│
└── widgets/
    ├── components.py     # Basic widgets
    ├── drone_config.py   # Drone configuration
    ├── detection_panel.py # Detection configuration
    ├── message_editor.py # Message editor
    └── param_reconfigure.py # Parameter editor
```

### Theming

Colors defined in `theme.py`:

```python
from nectar.interface import COLORS

COLORS.background      # #0D1117
COLORS.surface         # #161B22
COLORS.accent          # #FDCE01 (yellow)
COLORS.success         # #3FB950 (green)
COLORS.error           # #F85149 (red)
# ... see theme.py for full list
```

## Troubleshooting

**UI Freezes**: Ensure blocking operations use worker threads (not main thread)

**Service Timeouts**: Check driver is running and FCU is connected

**No Telemetry**: Verify driver connection and sensor configuration matches FCU setup

**Camera Not Working**: Check device permissions and ROS topic names

## References

- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [ROS2 Executors](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Executors.html)
