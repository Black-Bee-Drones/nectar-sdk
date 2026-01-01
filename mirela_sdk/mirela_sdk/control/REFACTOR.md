# Control Module Refactor

Technical documentation for the Mirela SDK control module redesign.

## Overview

The control module has been refactored from a tightly coupled, inheritance-based design to a modular, protocol-based architecture using factory and strategy patterns. All previous functionality is maintained while improving extensibility, testability, and separation of concerns.

## Architecture

### Design Patterns

**Factory Pattern**: Centralized drone instantiation via `DroneFactory`  
**Protocol Pattern**: Duck-typed interfaces without rigid inheritance  
**Strategy Pattern**: Pluggable navigation and obstacle avoidance strategies  
**Command Pattern**: Direct method execution for obstacle responses

### Module Structure

```
control/
├── base.py              # BaseDrone abstract implementation
├── protocols.py         # Protocol definitions (Drone, ObstacleDetector)
├── types.py             # Data types and enums
├── config.py            # Configuration dataclasses
├── factory.py           # DroneFactory
├── exceptions.py        # Custom exceptions
├── mavros/
│   ├── drone.py         # MavrosDrone implementation
│   └── gps_utils.py     # GPS utilities
├── bebop/
│   └── drone.py         # BebopDrone implementation
├── obstacles/
│   ├── base.py          # BaseObstacleDetector
│   ├── depth_camera.py  # DepthObstacleDetector (RealSense)
│   ├── strategies.py    # Avoidance strategy implementations
│   ├── handler.py       # ObstacleHandler, ObstacleManager
│   └── types.py         # Obstacle-specific types
└── pid/
    ├── pid_controller.py
    └── config.py
```

## Core Components

### DroneFactory

**Purpose**: Create drone instances with type-safe configuration.

**Signature**:
```python
DroneFactory.create(drone_type: str, config: DroneConfig, node: Node) -> BaseDrone
```

**Supported Types**:
- `"mavros"`: ArduPilot/PX4 via MAVROS
- `"bebop"`: Parrot Bebop 2

**Registration**: Implementations self-register via decorator pattern:
```python
DroneFactory.register("mavros", MavrosDrone.from_config)
```

### BaseDrone

**Purpose**: Abstract base class providing common functionality.

**Responsibilities**:
- Driver lifecycle management (start, check, wait)
- ROS2 resource management (subscribers, publishers, clients)
- Obstacle manager initialization
- Common utilities (delay, cleanup)

**Abstract Methods**:
- `connect()`, `disconnect()`
- `arm()`, `disarm()`
- `takeoff()`, `land()`
- `move_velocity()`, `move_to()`
- `emergency_stop()`

**Default Implementations**:
- `move_to_gps()`: Raises `CapabilityNotSupportedError`
- `set_home()`, `rtl()`: Return `False`

### Configuration System

**Hierarchy**:
```
DroneConfig (base)
├── MavrosConfig
├── BebopConfig
├── TelloConfig
└── CrazyflieConfig
```

**MavrosConfig Fields**:
- `pose_source`: `PoseSource.GPS` | `PoseSource.VISION`
- `navigation`: `NavigationStrategy.PID` | `NavigationStrategy.SETPOINT`
- `connection_string`: FCU connection (default: `/dev/ttyUSB0:921600`)
- `pid_config_file`: Optional PID configuration path
- Topic configurations (state, GPS, vision, lidar, IMU)

**BebopConfig Fields**:
- `ip`: Bebop IP address (default: `192.168.42.1`)
- `namespace`: ROS namespace (default: `bebop`)

### Movement API

**Unified Interface**:

```python
move_velocity(
    vx: float = 0.0,
    vy: float = 0.0,
    vz: float = 0.0,
    vyaw: float = 0.0,
    duration: Optional[float] = None,
    reference: MoveReference = MoveReference.BODY
) -> None
```

```python
move_to(
    x: Optional[float] = None,
    y: Optional[float] = None,
    z: Optional[float] = None,
    yaw: Optional[float] = None,
    reference: MoveReference = MoveReference.BODY,
    timeout: Optional[float] = 60.0,
    precision: float = 0.2,
    strategy: NavigationStrategy = NavigationStrategy.PID
) -> bool
```

```python
move_to_gps(
    latitude: float,
    longitude: float,
    altitude: Optional[float] = None,
    heading: Optional[float] = None,
    timeout: Optional[float] = 60.0,
    precision: float = 0.5,
    strategy: NavigationStrategy = NavigationStrategy.PID
) -> bool
```

**Reference Frames** (`MoveReference`):
- `BODY`: Relative to current orientation
- `WORLD`: Relative to world frame (NED for vision, GPS for outdoor)
- `TAKEOFF`: Relative to takeoff position

**Navigation Strategies** (`NavigationStrategy`):
- `PID`: Velocity-based control with feedback loop
- `SETPOINT`: Direct position setpoint publishing (MAVROS only)

### Return-to-Launch

```python
rtl(
    altitude: Optional[float] = None,
    precision: float = 0.2,
    strategy: RTLStrategy = RTLStrategy.PID,
    land: bool = True
) -> bool
```

**RTL Strategies** (`RTLStrategy`):
- `PID`: Navigate to takeoff position using PID control
- `ARDUPILOT`: Trigger ArduPilot's native RTL mode

**Behavior**:
- PID strategy requires `_takeoff_position` to be set (via `takeoff()` or `set_takeoff_position()`)
- ArduPilot strategy optionally sets `RTL_ALT` parameter
- `land` parameter controls whether to land after reaching home

## Obstacle Detection System

### Architecture

Event-based detection with strategy pattern for avoidance behaviors.

**Components**:

1. **ObstacleDetector** (Protocol): Defines detection interface
2. **AvoidanceStrategy** (ABC): Defines response behavior
3. **ObstacleHandler**: Combines detector + strategy + timing
4. **ObstacleManager**: Manages multiple handlers on a drone

### ObstacleDetector Protocol

```python
class ObstacleDetector(Protocol):
    @property
    def is_enabled(self) -> bool: ...
    
    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def update(self) -> ObstacleInfo: ...
    def reset(self) -> None: ...
```

**ObstacleInfo**:
```python
@dataclass
class ObstacleInfo:
    detected: bool
    direction: Optional[ObstacleDirection] = None  # FRONT, BACK, LEFT, RIGHT, UP, DOWN
    distance: Optional[float] = None  # meters
```

### AvoidanceStrategy

```python
class AvoidanceStrategy(ABC):
    @abstractmethod
    def execute(self, drone: BaseDrone, info: ObstacleInfo) -> bool:
        pass  # Returns True if navigation should continue
    
    @abstractmethod
    def reset(self) -> None:
        pass
```

**Built-in Strategies**:

**PauseStrategy**: Stops drone when obstacle detected
```python
strategy = strategies.PauseStrategy()
```

**DisableAxisStrategy**: Disables specific axis control
```python
strategy = strategies.DisableAxisStrategy(disable_x=False, disable_y=False, disable_z=True)
```

**SequenceStrategy**: Executes callable sequence when obstacle detected
```python
strategy = strategies.SequenceStrategy(sequence_func)
```

### Pre-built Sequences

All sequences directly call `drone.move_to()`:

```python
strategies.lateral_pass_return_sequence(drone, info, lateral_distance=1.0, forward_distance=2.5)
strategies.lateral_pass_sequence(drone, info, lateral_distance=1.0, forward_distance=2.5)
strategies.simple_lateral_sequence(drone, info, lateral_distance=1.0)
strategies.climb_over_sequence(drone, info, climb_height=1.0, forward_distance=2.5)
```

Use with `functools.partial` for parameter binding:

```python
from functools import partial

strategy = strategies.SequenceStrategy(
    partial(strategies.lateral_pass_return_sequence, lateral_distance=1.5)
)
```

### Integration

**Handler Creation**:
```python
handler = ObstacleHandler(
    detector=DepthObstacleDetector(node),
    strategy=strategies.PauseStrategy(),
    node=node,
    config=ObstacleHandlerConfig(
        enabled=True,
        update_rate=0.1  # 10 Hz timer
    )
)
```

**Drone Integration**:
```python
drone.add_obstacle_detector(name, detector, strategy, config=None)
drone.enable_obstacle_detector(name)
drone.disable_obstacle_detector(name)
drone.remove_obstacle_detector(name)
```

**Navigation Loop Integration**:
```python
# In _navigate_pid()
if not self._obstacle_manager.should_continue_navigation(self):
    continue  # Strategy is handling obstacle
    
disable_x, disable_y, disable_z = self._obstacle_manager.get_axis_control()
control_x = x is not None and not disable_x
# ... continue with PID control
```

## Migration Guide

### Old API → New API

#### Drone Initialization

**Old**:
```python
from mirela_sdk.control.mavros import MavDrone

drone = MavDrone(node=node, mavros=True, indoor=False)
```

**New**:
```python
from mirela_sdk.control import DroneFactory, MavrosConfig, PoseSource

config = MavrosConfig(pose_source=PoseSource.GPS)
drone = DroneFactory.create("mavros", config, node)
```

#### Basic Flight

**Old**:
```python
drone.arm_takeoff(takeoff_alt=10.0)
drone.offboard_position(x=5.0, y=0.0, z=0.0, strategy="PID")
drone.land()
```

**New** (same methods available):
```python
drone.takeoff(altitude=10.0)
drone.move_to(x=5.0, y=0.0, z=0.0, strategy=NavigationStrategy.PID)
drone.land()
```

**Legacy Compatibility**: Old `MavDrone` API still works via `control.compat.legacy` module.

#### GPS Navigation

**Old**:
```python
drone.offboard_position_gps_coords(
    lat=-27.123, lon=-48.456, alt=10.0, heading=90.0, strategy="PID"
)
```

**New**:
```python
drone.move_to_gps(
    latitude=-27.123, longitude=-48.456, altitude=10.0, heading=90.0,
    strategy=NavigationStrategy.PID
)
```

#### Return to Launch

**Old**:
```python
drone.rtl(rtl_alt=15.0, rtl_strategy="PID", land=True)
```

**New**:
```python
drone.rtl(altitude=15.0, strategy=RTLStrategy.PID, land=True)
```

#### Velocity Control

**Old**:
```python
drone.offboard_velocity(linear_x=0.5, linear_y=0.0, linear_z=0.0, angular_z=0.0, ground_reference=True)
```

**New**:
```python
drone.move_velocity(vx=0.5, vy=0.0, vz=0.0, vyaw=0.0, reference=MoveReference.WORLD)
```

#### PID Configuration

**Old**:
```python
drone.set_pid_config({
    "x": {"kp": 0.8, "output_min": -1.0, "output_max": 1.0},
    "y": {"kp": 0.8, "output_min": -1.0, "output_max": 1.0},
    "z": {"kp": 0.5, "output_min": -0.8, "output_max": 0.8}
})
```

**New** (same interface, enhanced types):
```python
from mirela_sdk.control.pid import PositionPIDConfig, PIDConfig

config = PositionPIDConfig(
    x=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
    y=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
    z=PIDConfig(kp=0.5, output_min=-0.8, output_max=0.8),
    yaw=PIDConfig(kp=0.5, ki=0.1, output_min=-0.3, output_max=0.3)
)
drone.set_pid_config(config)
```

### Obstacle Detection Migration

#### Old RealsenseObstacleDetector

**Old** (tightly coupled, hardcoded behavior):
```python
from mirela_sdk.control.mavros.obstacle_detector import RealsenseObstacleDetector

rs_detector = RealsenseObstacleDetector(drone=drone)
# Detector automatically runs on timer and executes evasion sequence
# No configuration, hardcoded 3-move pattern
```

**New** (modular, configurable):
```python
from mirela_sdk.control import DepthObstacleDetector, strategies
from functools import partial

detector = DepthObstacleDetector(node)

strategy = strategies.SequenceStrategy(
    partial(
        strategies.lateral_pass_return_sequence,
        lateral_distance=1.0,
        forward_distance=2.5
    )
)

config = ObstacleHandlerConfig(update_rate=0.15)
drone.add_obstacle_detector("depth", detector, strategy, config)
drone.enable_obstacle_detector("depth")
```

#### Old LidarObstacleDetector

**Old** (embedded in PositionController):
```python
# Automatically used in navigate_PID() when lidar_target_alt specified
drone.offboard_position(x=5.0, y=0.0, z=0.0, lidar_target_alt=1.5)
```

**New** (explicit strategy):
```python
from mirela_sdk.control import strategies

lidar_detector = LidarObstacleDetector(node)  # Custom implementation
strategy = strategies.DisableAxisStrategy(disable_z=True)

drone.add_obstacle_detector("lidar", lidar_detector, strategy)
drone.enable_obstacle_detector("lidar")

# Navigation proceeds normally, Z control disabled when obstacle detected
drone.move_to(x=5.0, y=0.0, z=0.0)
```

#### Old PositionController with Obstacle Avoidance

**Old**:
```python
from mirela_sdk.control.mavros.position_controller import PositionController

pos_ctrl = PositionController(drone)
pos_ctrl.navigate_PID(
    target_position=target,
    nav_config=NavigationConfig(
        obstacle_avoidance=True,
        use_lidar=True,
        lidar_target_alt=1.5
    )
)
```

**New**:
```python
# Configure obstacle detection
drone.add_obstacle_detector("depth", depth_detector, pause_strategy)
drone.add_obstacle_detector("lidar", lidar_detector, disable_z_strategy)
drone.enable_all_obstacle_detectors()

# Navigation handles obstacles automatically
drone.move_to(x=5.0, y=0.0, z=1.5, strategy=NavigationStrategy.PID)
```

## Maintained Functionality

### All Previous Capabilities

1. **Indoor Flight** (vision-based pose)
   - Position control via T265/VICON/OptiTrack
   - PID navigation with configurable gains
   - Takeoff/landing/RTL

2. **Outdoor Flight** (GPS-based)
   - GPS waypoint navigation
   - EGM96 geoid height correction
   - Compass heading integration

3. **Dual Navigation Strategies**
   - PID velocity control (default)
   - Direct setpoint publishing (MAVROS)

4. **Reference Frames**
   - Body-relative movement
   - World-frame movement
   - Takeoff-relative movement (ground reference)

5. **Sensor Integration**
   - GPS (NavSatFix)
   - Vision pose (PoseWithCovarianceStamped)
   - Lidar rangefinder (Range)
   - IMU (Imu)
   - Compass heading (Float64)

6. **Obstacle Detection**
   - Lidar-based altitude variation detection
   - RealSense depth-based obstacle detection
   - Configurable avoidance behaviors
   - Multi-detector support

7. **ArduPilot Integration**
   - Flight mode control (GUIDED, STABILIZE, etc.)
   - Arming/disarming
   - MAVLink command execution
   - Parameter setting
   - Servo control

8. **Parrot Bebop Support**
   - Velocity-only control
   - Camera gimbal control
   - Photo capture
   - Flip maneuvers

### New Capabilities

1. **Type Safety**: Configuration dataclasses with validation
2. **Extensibility**: Easy to add new drone types via factory registration
3. **Testability**: Protocol-based design enables mocking
4. **Flexibility**: Obstacle strategies are composable and reusable
5. **Modularity**: Clean separation of detection, strategy, and execution
6. **Event-based**: Detectors run on independent timers
7. **Yaw Control**: PID configuration now includes yaw axis

## Configuration Files

### PID Configuration

**Location**: `config/mavros/position_indoor.yaml`, `position_outdoor.yaml`

**Format**:
```yaml
x:
  kp: 0.5
  ki: 0.0
  kd: 0.0
  output_min: -0.42
  output_max: 0.42
  integral_min: -0.5
  integral_max: 0.5

y:
  kp: 0.5
  ki: 0.0
  kd: 0.0
  output_min: -0.42
  output_max: 0.42
  integral_min: -0.5
  integral_max: 0.5

z:
  kp: 0.22
  ki: 0.0
  kd: 0.0
  output_min: -0.15
  output_max: 0.1
  integral_min: -0.5
  integral_max: 0.5

yaw:
  kp: 0.5
  ki: 0.1
  kd: 0.0
  output_min: -0.2
  output_max: 0.2
  integral_min: -0.05
  integral_max: 0.05
```

**Loading**:
```python
# Automatic based on pose_source
config = MavrosConfig(pose_source=PoseSource.VISION)  # Loads position_indoor.yaml

# Explicit file
config = MavrosConfig(pid_config_file="/path/to/custom.yaml")

# Runtime update
drone.set_pid_config("/path/to/config.yaml")
drone.set_pid_config(config_dict)
drone.set_pid_config(PositionPIDConfig(...))
```

## Exception Hierarchy

```
DroneError (base)
├── ConnectionError
├── DriverNotFoundError
├── TakeoffError
├── LandingError
├── NavigationError
│   ├── TakeoffPositionNotSetError
│   ├── InvalidModeError
│   └── InvalidStrategyError
├── SensorNotAvailableError
├── CapabilityNotSupportedError
├── GPSError
└── TimeoutError
```

## Testing

### Unit Testing

Protocols enable easy mocking:

```python
from mirela_sdk.control.protocols import Drone

class MockDrone:
    def takeoff(self, altitude, timeout=30.0):
        self.altitude = altitude
        return True
    
    def move_to(self, x, y, z, **kwargs):
        self.position = (x, y, z)
        return True

assert isinstance(MockDrone(), Drone)  # Protocol check
```

### Integration Testing

Factory pattern enables test configurations:

```python
test_config = MavrosConfig(
    connection_string="tcp://localhost:14550",
    pose_source=PoseSource.VISION,
    start_driver=False
)

drone = DroneFactory.create("mavros", test_config, test_node)
```

## Performance Characteristics

### Navigation Loop

- PID update rate: 100 Hz (10ms loop)
- Obstacle check: Per-iteration (cost: O(n) where n = number of handlers)
- Strategy execution: Blocking (evasion sequences block navigation loop)

### Obstacle Detection

- Detector update rate: Configurable per handler (default: 10 Hz)
- Detection overhead: Independent of navigation loop
- Thread safety: Handlers use locks for state access

### Memory

- BaseDrone: ~1-2 KB per instance
- ObstacleHandler: ~500 bytes per instance
- PID controllers: ~200 bytes per controller (4 per drone)

## Backward Compatibility

### Legacy Module

Location: `control.compat.legacy`

Provides `MavDrone` class with original API:

```python
from mirela_sdk.control.compat.legacy import MavDrone

drone = MavDrone(node=node, mavros=True, indoor=False)
drone.arm_takeoff(10.0)
drone.offboard_position(x=5.0, y=0.0, z=0.0, strategy="PID")
```

Implementation wraps new `DroneFactory` and `MavrosDrone`.

### Deprecation Timeline

- **v0.1**: Legacy API fully supported
- **v0.2**: Deprecation warnings added
- **v0.3**: Legacy API moved to separate package
- **v1.0**: Legacy API removed

## Summary of Changes

### Removed

- Hardcoded indoor/outdoor drone classes
- `DroneCapabilities` (replaced with individual properties)
- `EvadeMove` dataclass (strategies call methods directly)
- Complex `NavigationModifiers` system
- `_move_to_gps_impl` indirection
- Redundant GPS utility wrappers

### Added

- `DroneFactory` with registration system
- Configuration dataclasses (`MavrosConfig`, `BebopConfig`)
- Protocol-based `Drone` and `ObstacleDetector` interfaces
- Strategy pattern for obstacle avoidance
- Event-based obstacle detection with timers
- `RTLStrategy` enum
- Yaw PID configuration
- `ObstacleManager` for multi-detector support

### Changed

- `move_velocity`: `ground_reference: bool` → `reference: MoveReference`
- `rtl`: Parameters reorganized, added `RTLStrategy`
- `move_to`: Added `NavigationStrategy` parameter
- GPS utilities: Simplified to direct `GPSCalculate` calls
- File organization: Drones moved to type-specific subfolders
- Base class location: `drones/base.py` → `control/base.py`

All changes maintain API compatibility through default parameters and legacy module.


