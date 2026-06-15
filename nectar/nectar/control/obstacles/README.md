# Obstacle Detection Module

Event-based obstacle detection with strategy pattern for avoidance behaviors.

## Architecture

```mermaid
classDiagram
    class ObstacleDetector {
        <<protocol>>
        +is_enabled bool
        +enable()
        +disable()
        +update() ObstacleInfo
        +reset()
    }

    class ObstacleInfo {
        <<dataclass>>
        +detected bool
        +direction Optional~ObstacleDirection~
        +distance Optional~float~
    }

    class ObstacleDirection {
        <<enum>>
        FRONT
        BACK
        LEFT
        RIGHT
        UP
        DOWN
    }

    class AvoidanceStrategy {
        <<abstract>>
        +execute(drone, info) bool
        +reset()*
    }

    class ObstacleHandler {
        -_detector ObstacleDetector
        -_strategy AvoidanceStrategy
        -_node Node
        -_config ObstacleHandlerConfig
        -_timer Optional~Timer~
        -_last_info ObstacleInfo
        -_lock Lock
        +detector ObstacleDetector
        +strategy AvoidanceStrategy
        +is_enabled bool
        +last_info ObstacleInfo
        +enable()
        +disable()
        +update() ObstacleInfo
        +should_continue(drone) bool
        +get_axis_modifiers() tuple~bool,bool,bool~
        +reset()
        +cleanup()
        -_update_callback()
    }

    class ObstacleHandlerConfig {
        <<dataclass>>
        +enabled bool
        +strategy Optional~AvoidanceStrategy~
        +update_rate float
    }

    class ObstacleManager {
        -_handlers dict~str,ObstacleHandler~
        +handlers dict~str,ObstacleHandler~
        +add(name, handler)
        +remove(name) Optional~ObstacleHandler~
        +get(name) Optional~ObstacleHandler~
        +enable(name)
        +disable(name)
        +enable_all()
        +disable_all()
        +should_continue_navigation(drone) bool
        +get_axis_control() tuple~bool,bool,bool~
        +reset_all()
        +cleanup()
    }

    class BaseObstacleDetector {
        <<abstract>>
        -_enabled bool
        -_lock Lock
        -_last_info ObstacleInfo
        +is_enabled bool
        +enable()
        +disable()
        +update() ObstacleInfo
        +get_last_info() ObstacleInfo
        +reset()
        #_detect()* ObstacleInfo
        #_on_enable()
        #_on_disable()
        #_on_reset()
    }

    class DepthObstacleDetector {
        -_node Node
        -_camera Optional~RealsenseCam~
        -_image_handler Optional~ImageHandler~
        -_detection_event Event
        -_color_topic str
        -_depth_topic str
        -_min_distance_mm float
        -_max_distance_mm float
        -_cluster_eps float
        -_cluster_min_samples int
        -_min_cluster_pixels int
        -_depth_threshold_mm float
        +update() ObstacleInfo
        -_detect() ObstacleInfo
        -_on_enable()
        -_on_disable()
        -_on_reset()
    }

    class PauseStrategy {
        -_paused bool
        +execute(drone, info) bool
        +reset()
    }

    class DisableAxisStrategy {
        +disable_x bool
        +disable_y bool
        +disable_z bool
        +execute(drone, info) bool
        +reset()
    }

    class SequenceStrategy {
        -_sequence_func Callable
        -_executed bool
        -_execution_event Event
        +execute(drone, info) bool
        +reset()
    }

    ObstacleDetector <|.. BaseObstacleDetector : implements
    BaseObstacleDetector <|-- DepthObstacleDetector
    AvoidanceStrategy <|-- PauseStrategy
    AvoidanceStrategy <|-- DisableAxisStrategy
    AvoidanceStrategy <|-- SequenceStrategy
    ObstacleHandler *-- ObstacleDetector
    ObstacleHandler *-- AvoidanceStrategy
    ObstacleHandler o-- ObstacleHandlerConfig
    ObstacleHandler ..> ObstacleInfo : uses
    ObstacleManager o-- ObstacleHandler
    ObstacleDetector ..> ObstacleInfo : returns
    ObstacleInfo o-- ObstacleDirection
```

## Real-Time Detection Flow

```mermaid
sequenceDiagram
    participant Nav as Navigation Loop<br/>(Main Thread)
    participant Mgr as ObstacleManager
    participant H as ObstacleHandler
    participant T as ROS2 Timer<br/>(Background)
    participant D as DepthDetector
    participant Cam as RealSense Camera
    participant S as Strategy

    Note over T,Cam: Background Detection (10Hz)
    loop Every 0.1s (Timer)
        T->>H: _update_callback()
        H->>D: update()
        D->>Cam: get_depth_frame()
        Cam-->>D: depth image
        D->>D: DBSCAN clustering
        D->>D: filter & classify
        D-->>H: ObstacleInfo
        H->>H: Lock & store
    end

    Note over Nav,S: Navigation Loop (100Hz)
    loop Every 0.01s
        Nav->>Mgr: should_continue_navigation(drone)
        Mgr->>H: should_continue(drone)
        H->>H: Lock & read last_info
        H->>S: execute(drone, info)

        alt Obstacle Detected
            S->>S: PauseStrategy
            S->>Nav: move_velocity(0,0,0,0)
            S-->>H: False (pause)
            H-->>Mgr: False
            Mgr-->>Nav: False (skip iteration)
        else Path Clear
            S-->>H: True (continue)
            H-->>Mgr: True
            Mgr-->>Nav: True
            Nav->>Nav: Compute PID
            Nav->>Nav: move_velocity(vx,vy,vz,vyaw)
        end
    end
```

## Core Concepts

### Separation of Concerns

**Detection** (What): Identify obstacles and return `ObstacleInfo`
**Strategy** (How): Define response behavior
**Handler** (When): Manage timing and integration
**Manager** (Where): Coordinate multiple detectors on a drone

### ObstacleInfo

Detection result data structure.

```python
@dataclass
class ObstacleInfo:
    detected: bool
    direction: Optional[ObstacleDirection] = None  # FRONT, BACK, LEFT, RIGHT, UP, DOWN
    distance: Optional[float] = None  # meters
```

### ObstacleDetector Protocol

Interface for obstacle detectors.

```python
class ObstacleDetector(Protocol):
    @property
    def is_enabled(self) -> bool: ...

    def enable(self) -> None: ...
    def disable(self) -> None: ...
    def update(self) -> ObstacleInfo: ...
    def reset(self) -> None: ...
```

## Detectors

### Detection Zones

**Direction returned** (from cluster position vs image center, as implemented in [`depth_camera.py`](depth_camera.py)):
- All clusters left of center (`x_max < center`) → `ObstacleDirection.RIGHT`
- All clusters right of center (`x_min > center`) → `ObstacleDirection.LEFT`
- Clusters on both sides → `ObstacleDirection.FRONT`

**Distance Thresholds**:
- Min: 0.1m (too close to camera)
- Max: 1.5m (detection limit)
- Threshold: 1.3m (cluster filter)

### DepthObstacleDetector

RealSense D435i depth camera-based detection using DBSCAN clustering.

**Configuration**:
```python
from nectar.control.obstacles import DepthObstacleDetector

detector = DepthObstacleDetector(
    min_distance_mm=100,         # ignore returns closer than this
    max_distance_mm=1500,        # maximum detection range
    cluster_eps=20,              # DBSCAN epsilon
    cluster_min_samples=20,      # DBSCAN minimum samples
    min_cluster_pixels=50,       # minimum valid pixels to attempt clustering
    depth_threshold_mm=1300,     # max cluster mean depth to count as obstacle
    color_topic="/camera/color/image_raw",
    depth_topic="/camera/depth/image_rect_raw",
)
```

The detector owns its own RealSense `ImageHandler` (and ROS node) internally — no `node` argument is passed.

**Algorithm**:
1. Acquire depth frame from RealSense camera
2. Downsample depth image (10% scale for performance)
3. Filter valid points (0 < depth < max_distance_mm)
4. Apply DBSCAN clustering to group obstacle points
5. Filter clusters by mean depth (< depth_threshold_mm)
6. Determine obstacle direction (LEFT, RIGHT, FRONT) based on cluster position
7. Calculate closest obstacle distance

**Direction Logic** (matches [`depth_camera.py`](depth_camera.py)):
- All clusters left of center → `ObstacleDirection.RIGHT`
- All clusters right of center → `ObstacleDirection.LEFT`
- Clusters on both sides → `ObstacleDirection.FRONT`

#### Depth Camera Processing Flow

```mermaid
flowchart TD
    Start([Depth Frame<br/>640x480 @ 30fps]) --> Convert[Convert to mm<br/>depth_mm = depth * 1000]
    Convert --> Downsample[Downsample 10%<br/>64x48 for performance]
    Downsample --> Filter{Filter Valid Depth}
    Filter -->|100mm < depth < 1500mm| ValidMask[Create Valid Mask]
    Filter -->|Outside range| Discard[Set to 0]

    ValidMask --> Count{Count Valid Pixels}
    Count -->|< 50 pixels| NoObstacle[Return: No Obstacle]
    Count -->|≥ 50 pixels| ExtractPoints[Extract Point Cloud<br/>xs, ys, depths]

    ExtractPoints --> DBSCAN[DBSCAN Clustering<br/>eps=20, min_samples=20]
    DBSCAN --> Clusters{Found Clusters?}
    Clusters -->|No clusters| NoObstacle
    Clusters -->|Yes| FilterClusters

    FilterClusters[Filter by Threshold<br/>mean_depth < 1300mm] --> ValidClusters{Valid Clusters?}
    ValidClusters -->|None| NoObstacle
    ValidClusters -->|Yes| AnalyzePosition

    AnalyzePosition[Analyze Cluster Position<br/>vs Image Center] --> Direction{Determine Direction}

    Direction -->|All clusters<br/>x_max < center| DirLeft[RIGHT]
    Direction -->|All clusters<br/>x_min > center| DirRight[LEFT]
    Direction -->|Clusters both sides| DirFront[FRONT]

    DirLeft --> CalcDist[Calculate Distance<br/>avg depth of clusters]
    DirRight --> CalcDist
    DirFront --> CalcDist

    CalcDist --> Return([Return ObstacleInfo<br/>detected=True, direction, distance])
    NoObstacle --> ReturnFalse([Return ObstacleInfo<br/>detected=False])

    style Start fill:#e1f5ff
    style Return fill:#d4edda
    style ReturnFalse fill:#f8d7da
    style DBSCAN fill:#fff3cd
    style Direction fill:#cce5ff
```

### BaseObstacleDetector

Abstract base class providing thread-safe state management.

```python
from nectar.control.obstacles import BaseObstacleDetector

class CustomDetector(BaseObstacleDetector):
    def _detect(self) -> ObstacleInfo:
        # Custom detection logic
        return ObstacleInfo(detected=True, direction=ObstacleDirection.FRONT)

    def _on_reset(self) -> None:
        # Reset internal state (optional hook)
        pass
```

## Strategies

### Strategy Decision Flow

```mermaid
flowchart TD
    Start([drone.move_to<br/>x=10, y=0, z=0]) --> Nav{Navigation Loop}

    Nav --> CheckObs{ObstacleManager:<br/>Check all detectors}

    CheckObs -->|No obstacles| ComputePID[Compute PID<br/>vx, vy, vz, vyaw]
    ComputePID --> SendVel[drone.move_velocity<br/>vx, vy, vz, vyaw]
    SendVel --> CheckDist{Distance to<br/>target < precision?}

    CheckObs -->|Obstacle detected| StrategyType{Which Strategy?}

    StrategyType -->|PAUSE| Pause[Stop drone<br/>move_velocity<br/>0, 0, 0, 0]
    Pause --> WaitClear{Path cleared?}
    WaitClear -->|No| Pause
    WaitClear -->|Yes| Nav

    StrategyType -->|DISABLE_AXIS| DisableZ[Disable Z axis<br/>Continue XY only]
    DisableZ --> ComputePID2[Compute PID<br/>vx, vy ONLY<br/>vz=0]
    ComputePID2 --> SendVel

    StrategyType -->|SEQUENCE| ExecuteSeq[Execute Sequence:<br/>Lateral → Forward → Return]
    ExecuteSeq --> SeqComplete{Sequence<br/>complete?}
    SeqComplete -->|No| ExecuteSeq
    SeqComplete -->|Yes| Nav

    CheckDist -->|No| Nav
    CheckDist -->|Yes| Done([Target Reached])

    style Pause fill:#ffe6e6
    style DisableZ fill:#fff4e6
    style ExecuteSeq fill:#e6f3ff
    style Done fill:#d4edda
```

### Strategies Summary

| Strategy | Behavior | Returns | Use Case |
|----------|----------|---------|----------|
| **PauseStrategy** | `move_velocity(0,0,0,0)` until clear | `False` while detected | Dynamic obstacles (people, drones) |
| **DisableAxisStrategy** | Disables specified axis control | `True` (continue) | Terrain following (lidar) |
| **SequenceStrategy** | Executes evasion maneuver | `False` during execution | Static obstacles (walls, trees) |

### AvoidanceStrategy Interface

```python
class AvoidanceStrategy(ABC):
    @abstractmethod
    def execute(self, drone: BaseDrone, info: ObstacleInfo) -> bool:
        """
        Execute avoidance behavior.

        Returns:
            True if navigation should continue, False to pause
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        pass
```

### PauseStrategy

Stops drone when obstacle detected, resumes when clear.

```python
from nectar.control.obstacles import strategies

strategy = strategies.PauseStrategy()
```

**Behavior**:
```python
def execute(self, drone, info):
    if info.detected:
        drone.move_velocity(0, 0, 0, 0)  # Stop
        return False  # Don't continue navigation
    else:
        return True  # Resume navigation
```

**Use Case**: Dynamic obstacles (people, other drones) that may move away.

### DisableAxisStrategy

Disables specific axis control during obstacle detection.

```python
strategy = strategies.DisableAxisStrategy(
    disable_x=False,
    disable_y=False,
    disable_z=True  # Disable altitude control
)
```

**Behavior**: Returns `True` (continue navigation) but signals which axes to disable via `get_axis_modifiers()`.

**Use Case**: Terrain following with lidar (disable Z PID, let ArduPilot handle altitude).

### SequenceStrategy

Executes custom callable sequence when obstacle detected.

```python
from functools import partial

strategy = strategies.SequenceStrategy(
    partial(
        strategies.lateral_pass_return_sequence,
        lateral_distance=1.0,
        forward_distance=2.5,
        precision=0.2
    )
)
```

**Behavior**: Calls `sequence_func(drone, info)` which executes `drone.move_to()` directly.

**Built-in Sequences**:

| Sequence | Steps | Result |
|----------|-------|--------|
| `lateral_pass_return_sequence` | ① `y=lateral` → ② `x=forward` → ③ `y=-lateral` | Returns to original path |
| `lateral_pass_sequence` | ① `y=lateral` → ② `x=forward` | Stays offset |
| `simple_lateral_sequence` | ① `y=lateral` | Single sidestep |
| `climb_over_sequence` | ① `z=+height` → ② `x=forward` → ③ `z=-height` | Vertical bypass |

**Direction logic**: `LEFT` → move right (`-y`), `RIGHT`/`FRONT` → move left (`+y`)

## Integration

### ObstacleHandler

Combines detector + strategy with timing.

```python
from nectar.control.obstacles import ObstacleHandler, ObstacleHandlerConfig

handler = ObstacleHandler(
    detector=DepthObstacleDetector(),
    strategy=strategies.PauseStrategy(),
    node=node,
    config=ObstacleHandlerConfig(
        enabled=True,
        update_rate=0.1
    )
)
```

**Update Mechanisms**:

1. **Timer-based** (default): ROS2 timer calls `_update_callback()` at specified rate
2. **Manual**: Call `handler.update()` explicitly (set `update_rate=0`)

**Thread Safety**: Uses locks for state access (`_last_info`).

### ObstacleManager

Manages multiple handlers on a drone.

```python
manager = ObstacleManager()

manager.add("depth", depth_handler)
manager.add("lidar", lidar_handler)

manager.enable("depth")
manager.disable("lidar")

# In navigation loop
if not manager.should_continue_navigation(drone):
    continue  # Strategy is handling obstacle

disable_x, disable_y, disable_z = manager.get_axis_control()
```

**Navigation Integration**:
```python
# In ArduPilotNavigator.navigate_pid()
while True:
    if not drone.obstacle_manager.should_continue_navigation(drone):
        continue  # Pause or sequence executing

    disable_x, disable_y, disable_z = drone.obstacle_manager.get_axis_control()

    control_x = x is not None and not disable_x
    control_y = y is not None and not disable_y
    control_z = z is not None and not disable_z

    # Continue with PID control
```

## Drone API

### Adding Detectors

```python
drone.add_obstacle_detector(
    name: str,
    detector: ObstacleDetector,
    strategy: AvoidanceStrategy,
    config: Optional[ObstacleHandlerConfig] = None
)
```

**Example**:
```python
detector = DepthObstacleDetector()
strategy = strategies.PauseStrategy()
config = ObstacleHandlerConfig(update_rate=0.15)  # 6.7 Hz

drone.add_obstacle_detector("depth", detector, strategy, config)
```

### Control

```python
drone.enable_obstacle_detector("depth")
drone.disable_obstacle_detector("depth")
drone.enable_all_obstacle_detectors()
drone.disable_all_obstacle_detectors()
drone.remove_obstacle_detector("depth")
```

## Usage Examples

### Simple Pause

```python
from nectar.control import DepthObstacleDetector, strategies

detector = DepthObstacleDetector()
drone.add_obstacle_detector("depth", detector, strategies.PauseStrategy())
drone.enable_obstacle_detector("depth")

drone.takeoff(1.5)
drone.move_to(x=10.0, y=0.0, z=0.0)  # Pauses when obstacle detected
drone.land()
```

### Lateral Evasion

```python
from functools import partial

detector = DepthObstacleDetector()

strategy = strategies.SequenceStrategy(
    partial(
        strategies.lateral_pass_return_sequence,
        lateral_distance=1.5,
        forward_distance=3.0
    )
)

drone.add_obstacle_detector("depth", detector, strategy)
drone.enable_obstacle_detector("depth")

drone.takeoff(1.5)
drone.move_to(x=10.0, y=0.0, z=0.0)  # Executes evasion when obstacle detected
drone.land()
```

### Custom Sequence

```python
def my_evasion(drone, info, climb_height=1.0):
    """Climb over obstacle."""
    drone.node.get_logger().info("Climbing over obstacle")
    drone.move_to(z=climb_height, precision=0.2)
    drone.move_to(x=3.0, precision=0.2)
    drone.move_to(z=-climb_height, precision=0.2)

strategy = strategies.SequenceStrategy(partial(my_evasion, climb_height=1.5))
drone.add_obstacle_detector("depth", detector, strategy)
```

### Terrain Following

```python
# Custom lidar detector (not provided)
lidar_detector = LidarObstacleDetector(node)

strategy = strategies.DisableAxisStrategy(disable_z=True)

drone.add_obstacle_detector("lidar", lidar_detector, strategy)
drone.enable_obstacle_detector("lidar")

# Z control disabled when lidar detects terrain variation
drone.move_to(x=10.0, y=0.0, z=0.0)
```

### Multiple Detectors

```python
depth_detector = DepthObstacleDetector()
ultrasonic_detector = UltrasonicDetector(node)  # Custom

drone.add_obstacle_detector(
    "depth", depth_detector,
    strategies.SequenceStrategy(strategies.lateral_pass_return_sequence)
)

drone.add_obstacle_detector(
    "ultrasonic", ultrasonic_detector,
    strategies.PauseStrategy()
)

drone.enable_all_obstacle_detectors()
```

## Custom Strategy Example

```python
from nectar.control.obstacles.strategies import AvoidanceStrategy

class BackupStrategy(AvoidanceStrategy):
    def __init__(self, backup_distance=1.0):
        self.backup_distance = backup_distance
        self._backing_up = False

    def execute(self, drone, info):
        if info.detected and not self._backing_up:
            self._backing_up = True
            drone.move_to(x=-self.backup_distance, precision=0.2)
            self._backing_up = False
            return False  # Don't continue until backup complete

        return not info.detected

    def reset(self):
        self._backing_up = False

drone.add_obstacle_detector("depth", detector, BackupStrategy(backup_distance=2.0))
```

## Thread Safety

**Detectors**: Run on independent ROS2 timers (background threads)
**Handlers**: Use locks for state access
**Strategies**: Execute in navigation thread (main thread)
**Manager**: Single-threaded (navigation loop)

**Synchronization**: Handler locks prevent race conditions between timer callback and navigation loop.
