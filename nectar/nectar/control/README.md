# Drone Control Module

## Role

Protocol-based drone control for ROS 2. `DroneFactory` builds a drone by key behind the common `Drone` protocol; each platform implements the same interface (takeoff, land, move_to, move_to_gps, move_velocity, rtl, obstacle management).

## Documentation Index

| README | Scope |
|--------|-------|
| [vehicle/](vehicle/README.md) | Firmware-agnostic vehicle core: navigation, frames, takeoff/land, GPS/EGM96, PID, firmware hooks |
| [ardupilot/](ardupilot/README.md) | ArduPilot specialization: GUIDED arming, `GUID_OPTIONS`/WPNAV, native RTL, parameters |
| [px4/](px4/README.md) | PX4 specialization: OFFBOARD setpoint streaming, AUTO.LAND/RTL; MAVROS / direct-MAVLink / uXRCE-DDS backends |
| [mavros/](mavros/README.md) | MAVROS transport (`MavrosDrone`, `Px4MavrosDrone`) |
| [mavlink/](mavlink/README.md) | Firmware-neutral pymavlink transport (`MavlinkDrone`, `Px4MavlinkDrone`) |
| [localization/](localization/README.md) | Indoor VSLAM external-nav: Isaac producer + vision-pose bridge |
| [obstacles/](obstacles/README.md) | Obstacle detection + avoidance strategies |
| [pid/](pid/README.md) | PID controller and tuning |
| [bebop/](bebop/README.md) | Parrot Bebop 2 (`BebopDrone`) |
| [crazyflie/](crazyflie/README.md) | Bitcraze Crazyflie (`CrazyflieDrone`) |

## At a glance

```python
import nectar
from nectar.control import DroneFactory, MavrosConfig, PoseSource

nectar.init()
drone = DroneFactory.create("mavros", MavrosConfig(pose_source=PoseSource.GPS))

drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3)   # same calls on every backend
drone.land()
nectar.shutdown()
```

Pick a backend by key — `mavros`, `mavlink`, `px4`, `px4_mavlink`, `px4_dds`, `bebop`,
`crazyflie` — with its matching config; the flight calls stay the same.

## Concepts

ArduPilot and PX4 share one firmware-agnostic core (`VehicleDrone`) and reach the FCU
through interchangeable transports (MAVROS, direct MAVLink, PX4 uXRCE-DDS); Bebop and
Crazyflie implement the `Drone` protocol directly.

```mermaid
classDiagram
    class DroneFactory {
        <<singleton>>
        -_builders Dict~str,BuilderFunc~
        +create(type, config, executor) Drone
        +register(type, factory_func)
        +available_types() list~str~
        +is_registered(type) bool
    }

    class Drone {
        <<protocol>>
        +is_ready bool
        +connect() bool
        +disconnect()
        +arm() bool
        +disarm() bool
        +takeoff(altitude) bool
        +land(timeout) bool
        +move_velocity(vx, vy, vz, vyaw, duration, reference)
        +move_to(x, y, z, yaw, reference, timeout, precision, method) bool
        +move_to_gps(lat, lon, alt, heading, timeout, precision, method) bool
        +emergency_stop()
        +set_home() bool
        +rtl(altitude, precision, method, land) bool
    }

    class BaseDrone {
        <<abstract>>
        -_config DroneConfig
        -_node Node
        -_connected bool
        -_driver_running bool
        -_obstacle_manager ObstacleManager
        -_subscribers List~Subscription~
        -_publishers List~Publisher~
        -_clients List~Client~
        -_callback_group ReentrantCallbackGroup
        +config DroneConfig
        +node Node
        +is_ready bool
        +driver_running bool
        +is_armed Optional~bool~
        +flight_mode Optional~str~
        +is_fcu_connected Optional~bool~
        +driver_session_name str
        +obstacle_manager ObstacleManager
        +add_obstacle_detector(name, detector, strategy, config)
        +remove_obstacle_detector(name)
        +enable_obstacle_detector(name)
        +disable_obstacle_detector(name)
        +enable_all_obstacle_detectors()
        +disable_all_obstacle_detectors()
        +check_driver_status() bool
        +start_driver_process() bool
        +stop_driver_process() bool
        +delay(seconds)
        +cleanup()
        #_init_driver()
        #_wait_for_driver(timeout) bool
        #_create_subscriber(msg_type, topic, callback, qos) Subscription
        #_create_publisher(msg_type, topic, qos) Publisher
        #_create_client(srv_type, service_name) Client
        #_get_driver_name()* str
        #_start_driver()* bool
        #_get_driver_command()* str
    }

    class VehicleDrone {
        <<abstract>>
        -_transport VehicleTransport
        -_navigator VehicleNavigator
        -_sequencer FlightSequencer
        -_pid_config Optional~PositionPIDConfig~
        -_setpoint_config Optional~SetpointConfig~
        -_takeoff_position Optional
        -_pose_source PoseSource
        +is_indoor bool
        +is_armed flight_mode is_fcu_connected
        +gps heading rel_alt
        +local_pose vision_pose Optional~LocalPose~
        +lidar_available bool
        +position position_as_target
        +get_altitude(source) Optional~float~
        +distance_sensors get_distance(orientation)
        +takeoff() land() move_to() move_to_gps() move_velocity() rtl()
        +set_mode() set_param() set_speed() set_home()
        +set_actuator() set_gripper()
        +set_takeoff_position() set_pid_config() set_setpoint_config()
        +arm()* _rtl_native()* _change_speed()* capabilities*
    }

    class ArduPilotDrone {
        GUIDED arm, GUID_OPTIONS/WPNAV
        native RTL, do_servo, DO_CHANGE_SPEED
    }

    class Px4Drone {
        OFFBOARD + setpoint pump
        AUTO.LAND/RTL, MPC_* speed
    }

    class MavrosDrone {
        +from_config(config, executor)$ MavrosDrone
    }

    class MavlinkDrone {
        +connection MavlinkConnection
        +from_config(config, executor)$ MavlinkDrone
    }

    class Px4MavrosDrone {
        +from_config(config, executor)$ Px4MavrosDrone
    }

    class Px4MavlinkDrone {
        +connection MavlinkConnection
        +from_config(config, executor)$ Px4MavlinkDrone
    }

    class Px4DdsDrone {
        +from_config(config, executor)$ Px4DdsDrone
    }

    class CrazyflieDrone {
        +from_config(config, executor)$ CrazyflieDrone
    }

    class VehicleTransport {
        <<abstract>>
        +state local_pose vision_pose gps heading rel_alt rangefinder distance_sensors
        +arm() set_mode() command_takeoff() command_land() set_param()
        +send_velocity_target() send_local_target() send_global_target()
    }

    class MavrosTransport
    class PymavlinkTransport
    class Px4DdsTransport

    class BebopDrone {
        +from_config(config, executor)$ BebopDrone
        +flip(direction)
        +camera_control(tilt, pan)
        +snapshot()
        -_setup_publishers()
    }

    class DroneConfig {
        <<dataclass>>
        +name str
        +start_driver bool
    }

    class MavrosConfig {
        <<dataclass>>
        +pose_source PoseSource
        +expect_lidar bool
        +sensor_timeout float
        +connection_string str
        +pid_config_file setpoint_config_file Optional~str~
        +apply_setpoint_params bool
        +state_topic gps_topic vision_topic str
        +heading_topic rel_alt_topic lidar_topic str
        +local_position_topic str
    }

    class MavlinkConfig {
        <<dataclass>>
        +pose_source PoseSource
        +expect_lidar bool
        +connection_string str
        +baud source_system source_component int
        +rx_rate_hz heartbeat_hz vision_rate_hz float
        +stream_rates Optional~Dict~
        +vision_pose_topic str
        +pid_config_file setpoint_config_file Optional~str~
        +apply_setpoint_params bool
    }

    class BebopConfig {
        <<dataclass>>
        +name str
        +start_driver bool
        +ip str
        +namespace str
    }

    class Px4MavrosConfig {
        <<dataclass>>
        +pose_source PoseSource
        +offboard_rate_hz float
        +mavros_launch str
        +connection_string str
        +shares MavrosConfig telemetry topics
    }

    class Px4MavlinkConfig {
        <<dataclass>>
        +pose_source PoseSource
        +offboard_rate_hz float
        +connection_string str
        +shares MavlinkConfig link settings
    }

    class Px4DdsConfig {
        <<dataclass>>
        +pose_source PoseSource
        +offboard_rate_hz float
        +px4_namespace str
        +agent_port int
        +local_position_topic status_topic global_position_topic str
    }

    class ObstacleManager {
        -_handlers dict~str,ObstacleHandler~
        +add(name, handler) remove(name) get(name)
        +enable(name) disable(name) enable_all() disable_all()
        +should_continue_navigation(drone) bool
        +get_axis_control() tuple~bool,bool,bool~
        +reset_all() cleanup()
    }

    DroneFactory --> BaseDrone : creates
    Drone <|.. BaseDrone : implements
    BaseDrone <|-- VehicleDrone
    BaseDrone <|-- BebopDrone
    BaseDrone <|-- CrazyflieDrone
    VehicleDrone <|-- ArduPilotDrone
    VehicleDrone <|-- Px4Drone
    VehicleDrone o-- VehicleTransport
    ArduPilotDrone <|-- MavrosDrone
    ArduPilotDrone <|-- MavlinkDrone
    Px4Drone <|-- Px4MavrosDrone
    Px4Drone <|-- Px4MavlinkDrone
    Px4Drone <|-- Px4DdsDrone
    VehicleTransport <|.. MavrosTransport
    VehicleTransport <|.. PymavlinkTransport
    VehicleTransport <|.. Px4DdsTransport
    MavrosDrone ..> MavrosTransport : builds
    MavlinkDrone ..> PymavlinkTransport : builds
    Px4MavrosDrone ..> MavrosTransport : builds
    Px4MavlinkDrone ..> PymavlinkTransport : builds
    Px4DdsDrone ..> Px4DdsTransport : builds
    BaseDrone *-- ObstacleManager
    BaseDrone o-- DroneConfig
    MavrosDrone o-- MavrosConfig
    MavlinkDrone o-- MavlinkConfig
    Px4MavrosDrone o-- Px4MavrosConfig
    Px4MavlinkDrone o-- Px4MavlinkConfig
    Px4DdsDrone o-- Px4DdsConfig
    BebopDrone o-- BebopConfig
    DroneConfig <|-- MavrosConfig
    DroneConfig <|-- MavlinkConfig
    DroneConfig <|-- Px4MavrosConfig
    DroneConfig <|-- Px4MavlinkConfig
    DroneConfig <|-- Px4DdsConfig
    DroneConfig <|-- BebopConfig
```

## Runtime Model

Each drone owns its own ROS 2 `Node` (created internally with a UUID-suffixed name). All SDK subsystem nodes are added to a shared `MultiThreadedExecutor` managed by [`nectar.runtime`](../runtime.py), which spins on a background thread. Blocking calls (`takeoff`, `land`, `move_to`) sleep on the user's thread; the executor keeps firing callbacks (state, pose, GPS, lidar, IMU) without contention.

Three usage patterns share the same primitives:

- **Standalone script**: `nectar.init()` lazily creates the shared executor and starts the spin thread. `DroneFactory.create("mavros", config)` registers the drone's node with it. Call `nectar.shutdown()` on exit.
- **Yasmin mission**: call `nectar.use_executor(YasminNode.get_instance()._executor)` once at startup. SDK subsystems created afterwards register with the Yasmin executor instead of spawning a second spin thread.
- **GUI**: `ROSExecutor.start()` registers its `MultiThreadedExecutor` with `nectar.runtime`. Drones/handlers created from inside tabs share that executor automatically.

## Transport Architecture

Both firmwares are reached over interchangeable transports behind one core. All flight/navigation logic lives once in the transport-agnostic [`VehicleDrone`](vehicle/README.md); firmware specializations ([`ArduPilotDrone`](ardupilot/README.md), [`Px4Drone`](px4/README.md)) add only firmware semantics, reading telemetry and issuing commands/setpoints through a pluggable `VehicleTransport`:

- `MavrosTransport` — subscriptions → telemetry, service clients → commands, publishers → setpoints (requires a running `mavros_node`). Shared by `MavrosDrone` (ArduPilot) and `Px4MavrosDrone`.
- `PymavlinkTransport` — owns the FCU link directly (a ROS timer drains RX; commands/setpoints go out via `mav.*_send`). Firmware-neutral: an injected `MavlinkModeCodec` isolates the only firmware difference — flight-mode encode/decode. `ArduPilotModeCodec` (default, `SET_MODE`) backs `MavlinkDrone`; `Px4ModeCodec` (`MAV_CMD_DO_SET_MODE`) backs `Px4MavlinkDrone`. Indoor it auto-starts a `VisionPoseBridge` to feed the EKF. See [mavlink/README.md](mavlink/README.md).
- `Px4DdsTransport` — native PX4 uORB over the uXRCE-DDS bridge (`px4_msgs`), for `Px4DdsDrone`. See [px4/README.md](px4/README.md).

So PX4 offers three backends (`px4` = MAVROS, `px4_mavlink` = direct MAVLink, `px4_dds` = uXRCE-DDS) and ArduPilot two (`mavros`, `mavlink`) — all sharing the same `Px4Drone` / `ArduPilotDrone` flight logic, so missions are backend-agnostic.

The core operates on plain, ROS-free types; each transport converts its wire types (`mavros_msgs`/`geometry_msgs`, raw MAVLink, or `px4_msgs`) to/from these. ENU/FLU and radians throughout; transports handle NED/FRD conversion.

### Capabilities

Each drone declares a `frozenset[Capability]` (see `capabilities.py`); query with `drone.supports(Capability.GPS_NAV)`. New drones declare what they support by overriding the `capabilities` property. Unsupported operations raise `CapabilityNotSupportedError`.

Declared sets per drone:

- `ArduPilotDrone` (MAVROS/MAVLink): `PID_NAV`, `LOCAL_SETPOINT`, `VELOCITY_BODY`, `VELOCITY_WORLD`, `VELOCITY_TAKEOFF`, `SERVO`, `ACTUATOR`, `GRIPPER`, `PARAMS`, `NATIVE_RTL`, `OBSTACLE_AVOIDANCE`, `RANGEFINDER`, `DISTANCE_SENSORS`, plus `GPS_NAV`/`GLOBAL_SETPOINT` (outdoor) or `VISION_POSE` (indoor) from `pose_source`.
- `Px4Drone` (`px4`, `px4_mavlink`, `px4_dds`): same as ArduPilot minus `SERVO` — PX4 has no per-channel PWM `do_servo`, but keeps `ACTUATOR` (`DO_SET_ACTUATOR`) and `GRIPPER` (`DO_GRIPPER`) for payloads; `GPS_NAV`/`GLOBAL_SETPOINT` (outdoor) or `VISION_POSE` (indoor) from `pose_source`. Capabilities are identical across the three PX4 backends.
- `CrazyflieDrone`: `LOCAL_SETPOINT`, `VELOCITY_BODY`, `VELOCITY_WORLD`, `VELOCITY_TAKEOFF`, `PARAMS`.
- `BebopDrone`: `VELOCITY_BODY`, `NATIVE_RTL`.

## Core Components

### DroneFactory

Centralized drone instantiation with type registration.

**API**:
```python
DroneFactory.create(drone_type: str, config: DroneConfig,
                    executor: Optional[Executor] = None) -> BaseDrone
DroneFactory.register(drone_type: str, factory_func: Callable)
```

**Supported Types**:
- `mavros`: ArduPilot via MAVROS
- `mavlink`: ArduPilot via direct pymavlink (no MAVROS)
- `px4`: PX4 via MAVROS (OFFBOARD setpoint streaming)
- `px4_mavlink`: PX4 via direct pymavlink (no MAVROS)
- `px4_dds`: PX4 via native uXRCE-DDS (`px4_msgs`)
- `bebop`: Parrot Bebop 2
- `crazyflie`: Bitcraze Crazyflie

**Example**:
```python
import nectar
from nectar.control import DroneFactory, MavrosConfig, PoseSource

nectar.init()
config = MavrosConfig(pose_source=PoseSource.VISION)
drone = DroneFactory.create("mavros", config)   # optional: executor=<your Executor>
```

### Drone Protocol

Duck-typed interface defining drone contract. All drones must implement:

**Core Operations**:
- `connect()`, `disconnect()`: Connection management
- `arm()`, `disarm()`: Motor control
- `takeoff()`, `land()`: Vertical maneuvers
- `emergency_stop()`: Force shutdown

**Movement**:
- `move_velocity()`: Direct velocity control
- `move_to()`: Position navigation
- `move_to_gps()`: GPS waypoint navigation
- `rtl()`: Return-to-launch

**State**:
- `is_ready`: connection and driver status (all drones)
- FCU drones (ArduPilot/PX4) additionally expose `is_armed`, `flight_mode`, `is_fcu_connected` (see [vehicle/README.md](vehicle/README.md)); other platforms expose their own readiness fields

### BaseDrone

Abstract base providing common functionality.

**Responsibilities**:
- Driver lifecycle (start, monitor)
- ROS2 resource management (subscribers, publishers, clients)
- Obstacle manager integration
- Delay utility with ROS spinning

**Protected Methods**:
- `_create_subscriber()`, `_create_publisher()`, `_create_client()`
- `_init_driver()`, `_check_driver_running()`, `_wait_for_driver()`
- `delay(seconds)`: Non-blocking delay

### Configuration System

Type-safe dataclass hierarchy.

**MavrosConfig**:
```python
MavrosConfig(
    pose_source: PoseSource = PoseSource.GPS,     # GPS or VISION
    expect_lidar: bool = True,
    connection_string: str = "serial:///dev/ttyUSB0:921600",
    pid_config_file: Optional[str] = None,
    local_position_topic: str = "/mavros/local_position/pose",
    # ... topic configurations with sensible defaults
)
```

**BebopConfig**:
```python
BebopConfig(
    ip: str = "192.168.42.1",
    namespace: str = "bebop"
)
```

## Movement, Navigation, RTL

`MoveReference` selects the frame: `BODY` (relative to current heading), `WORLD` (ENU world frame), `TAKEOFF` (relative to the takeoff pose). The public movement API — `move_velocity`, `move_to`, `move_to_gps`, `rtl` — plus the navigation methods (`POSITION`, `POSITION_GLOBAL`, `PID`, `PID_EKF`), altitude sources, GPS/EGM96 handling, and RTL modes are defined once in the shared core: see **[vehicle/README.md](vehicle/README.md)**. Bebop and Crazyflie support a subset (see their READMEs and the capability matrix above).

## Obstacle Detection

Detector + strategy + handler/manager, integrated into navigation via `drone.add_obstacle_detector(...)`. Full design, detectors, and strategies are documented in **[obstacles/README.md](obstacles/README.md)**.

```python
from nectar.control import DepthObstacleDetector, strategies

drone.add_obstacle_detector("depth", DepthObstacleDetector(), strategies.PauseStrategy())
drone.enable_all_obstacle_detectors()
```

## PID Control

Per-axis position PID (x/y/z/yaw), loaded from each firmware's `config/*.yaml` by `is_indoor` and overridable at runtime via `drone.set_pid_config(...)`. The loading lifecycle lives in **[vehicle/README.md](vehicle/README.md#pid-configuration)**; tuning and the config schema are in **[pid/README.md](pid/README.md)**.

## Exception Hierarchy

```python
DroneError
├── DriverNotFoundError
├── TakeoffPositionNotSetError
├── SensorNotAvailableError
└── CapabilityNotSupportedError
```

## Usage Examples

### GPS Waypoint Mission

```python
config = MavrosConfig(pose_source=PoseSource.GPS)
drone = DroneFactory.create("mavros", config)

waypoints = [
    (-27.1234, -48.4567, 15.0),
    (-27.1245, -48.4578, 15.0),
    (-27.1256, -48.4589, 15.0)
]

drone.takeoff(altitude=15.0)

for lat, lon, alt in waypoints:
    drone.move_to_gps(lat, lon, alt, precision=1.0)

drone.land()
```

### Multiple Reference Frames

```python
from nectar.control.types import MoveReference

drone.takeoff(1.5)

# Body-relative: 1m forward and 0.5m left from current position
drone.move_to(x=1.0, y=0.5, z=0.0, reference=MoveReference.BODY)

# Takeoff-relative: go to position 2m forward of takeoff point
drone.move_to(x=2.0, y=0.0, z=0.0, reference=MoveReference.TAKEOFF)

# Return to takeoff position
drone.move_to(x=0.0, y=0.0, z=0.0, reference=MoveReference.TAKEOFF)

# World-frame velocity
drone.move_velocity(vx=0.5, vy=0.0, vz=0.0, reference=MoveReference.WORLD)
```

### Obstacle-Aware Navigation

```python
from nectar.control import DepthObstacleDetector, strategies

detector = DepthObstacleDetector()
drone.add_obstacle_detector("depth", detector, strategies.PauseStrategy())
drone.enable_obstacle_detector("depth")

drone.takeoff(1.5)
drone.move_to(x=10.0, y=0.0, z=0.0)  # Pauses when obstacles detected
drone.land()
```

## Implementation Modules

- **vehicle/**: Firmware-agnostic vehicle core (VehicleDrone, VehicleNavigator, target computer, GPS utils, sequencer, VehicleTransport ABC, plain types)
- **ardupilot/**: ArduPilot specialization (ArduPilotDrone: GUIDED, WPNAV/GUID_OPTIONS setpoint config, native RTL)
- **px4/**: PX4 specialization (Px4Drone: OFFBOARD setpoint pump, AUTO.LAND/RTL; backends Px4MavrosDrone, Px4MavlinkDrone, Px4DdsDrone; shared PX4 mode map `modes.py`)
- **mavros/**: MAVROS transport (MavrosTransport, MavrosDrone, Px4MavrosDrone)
- **mavlink/**: Firmware-neutral pymavlink transport (PymavlinkTransport + mode codecs, MavlinkDrone, connection, streams, vision bridge)
- **bebop/**: Parrot Bebop 2 implementation (BebopDrone, velocity control, acrobatic maneuvers)
- **crazyflie/**: Bitcraze Crazyflie implementation
- **localization/**: Indoor VSLAM external-nav (MavrosVisionRelay, vision_pose_node, Isaac launches, RViz)
- **obstacles/**: Obstacle detection system (detectors, strategies, handlers)
- **pid/**: PID controller implementation and configuration

See individual module READMEs for detailed documentation.

## Type System

**Enums**:
- `PoseSource`: GPS, VISION
- `MoveReference`: BODY, WORLD, TAKEOFF
- `NavigationMethod`: POSITION, POSITION_GLOBAL, PID, PID_EKF
- `RTLMethod`: NAVIGATE, NATIVE
- `AltitudeSource`: AUTO, LIDAR, VISION, REL_ALT
- `ObstacleDirection`: FRONT, BACK, LEFT, RIGHT, UP, DOWN
- `ObstacleInfo`: Detection result
