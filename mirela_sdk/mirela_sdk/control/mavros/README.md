# Mavros Control Module

ArduPilot/Mavros integration for drone control using ROS2. Provides position control with PID, GPS navigation, obstacle detection, and precision landing.

## Module Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                          MavDrone                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ State Management                                         │  │
│  │ - FCU state, sensors (GPS, IMU, lidar, vision)           │  │
│  │ - Indoor/outdoor mode switching                          │  │
│  │ - Takeoff position tracking                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │PositionCtrl  │  │  GPSCtrl     │                            │
│  │- PID control │  │- Geofence    │                            │
│  │- Navigation  │  │- Bearing     │                            │
│  │- Obstacle    │  │- Haversine   │                            │
│  └──────────────┘  └──────────────┘                            │
│         │                                                      │
│  ┌──────────────┐                                              │
│  │ObstacleDetect│                                              │
│  │- Lidar buffer│                                              │
│  │- Deviation   │                                              │
│  └──────────────┘                                              │
└────────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
           ┌────────▼────┐  ┌─────▼──────┐
           │   MAVROS    │  │  ArduPilot │
           │  /topics    │  │    FCU     │
           │  /services  │  │            │
           └─────────────┘  └────────────┘
```

## Class Overview

### MavDrone (mavros_api.py)

Main control interface for ArduPilot drones via Mavros.

**Initialization:**
```python
MavDrone(
    node: Node,
    mavros: bool = False,  # Auto-start mavros driver
    indoor: bool = False   # Indoor (vision) or outdoor (GPS) mode
)
```

**Key Features:**

1. **Mode Management**
   - `set_mode(mode: str)`: FCU flight mode (GUIDED, STABILIZE, etc.)
   - `arm()`: Arm motors with GUIDED mode
   - `kill_motors()`: Emergency disarm (forced)

2. **Takeoff/Landing**
   - `arm_takeoff(alt: float)`: Arm + takeoff sequence
   - `takeoff(alt: float)`: Takeoff command
   - `land()`: Land at current position
   - `rtl(rtl_alt, strategy, land)`: Return-to-launch with multiple strategies

3. **Position Control**
   - `offboard_position(x, y, z, ground_reference, strategy)`: Relative movement
   - `offboard_position_gps_coords(lat, lon, alt, heading, strategy)`: GPS navigation
   - `offboard_velocity(vx, vy, vz, angular_z)`: Direct velocity commands

4. **Sensors & State**
   - `get_height`: Altitude from lidar, vision, or GPS
   - `get_position`: Current position (vision or GPS)
   - `get_gps`, `get_vision_pos`, `get_imu_data`: Raw sensor data
   - `get_rng_alt`: Lidar rangefinder data

5. **Utilities**
   - `set_home()`: Set/update home position
   - `set_takeoff_position()`: Store position for RTL/ground-reference
   - `set_pid_config(config)`: Update PID configuration (file, dict, or object)
   - `do_servo(aux, pwm)`: Control servo outputs
   - `delay(seconds)`: Non-blocking delay with ROS spinning

**Subscribers:**
- `/mavros/state`: FCU state (mode, armed, connected)
- `/mavros/rangefinder/rangefinder`: Lidar altitude
- `/mavros/imu/data`: IMU measurements
- `/mavros/vision_pose/pose_cov` (indoor): Vision-based position
- `/mavros/global_position/global` (outdoor): GPS position
- `/mavros/global_position/rel_alt` (outdoor): Relative altitude
- `/mavros/global_position/compass_hdg` (outdoor): Compass heading

**Publishers:**
- `/mavros/setpoint_raw/local`: Position/velocity setpoints (NED)
- `/mavros/setpoint_position/global` (outdoor): GPS position setpoints

**Services:**
- `/mavros/set_mode`: Change flight mode
- `/mavros/cmd/arming`: Arm/disarm
- `/mavros/cmd/takeoff`: Takeoff command
- `/mavros/cmd/land`: Landing command
- `/mavros/cmd/set_home`: Home position update
- `/mavros/cmd/command`: Generic MAVLink commands

---

### PositionController (position_controller.py)

PID-based position control for precise navigation.

**Architecture:**
```python
PositionController(drone, config_file=None)
```

**Control Strategies:**

1. **PID Control** (`strategy="PID"`)
   - Closed-loop velocity control
   - Separate X, Y, Z PID controllers
   - Obstacle detection integration
   - Default for precision tasks

2. **Setpoint Messages** (`strategy="mavros"`)
   - Direct position/GPS setpoint publishing
   - ArduPilot handles control loop
   - Less precise, simpler

**Methods:**

- `navigate_PID(target, lidar_alt, precision_radius, timeout)`: PID navigation
- `navigate_local_msg(target, precision_radius, timeout)`: Local setpoint navigation
- `navigate_gps_msg(gps_setpoint, precision_radius, timeout)`: GPS setpoint navigation
- `get_current_position(timeout)`: Read current position
- `set_pid_config(config)`: Update PID configuration

**Configuration:**

Default configs: `config/mavros/position_indoor.yaml`, `position_outdoor.yaml`

```yaml
x:  # Horizontal axis
  kp: 0.5
  ki: 0.0
  kd: 0.0
  output_min: -0.42
  output_max: 0.42
  integral_min: -0.5
  integral_max: 0.5
```

**PID Loop:**
```
Current Position → Body Frame Error → PID Controller → Velocity Command
       ↑                                                       ↓
       └───────────────────── Drone Movement ←────────────────┘
```

---

### ObstacleDetector (obstacle_detector.py)

Lidar-based obstacle detection using altitude variation buffer.

**Principle:**

Monitors lidar altitude changes to detect when drone passes over/under obstacles. When detected, vertical control is handed to ArduPilot's rangefinder system per [ArduPilot altitude control](https://ardupilot.org/copter/docs/common-understanding-altitude.html#target-alt-modification-using-rangefinder-rf).

**Configuration:**
```python
LidarObstacleDetector(
    buffer_size=10,          # Samples for baseline (10Hz → 1s)
    height_threshold=0.25,   # Minimum change to trigger (meters)
    timeout=8.0              # Max obstacle state duration (seconds)
)
```

**Detection Algorithm:**

1. **Buffer Collection**: Collect `buffer_size` lidar samples
2. **Baseline**: Calculate mean altitude from buffer
3. **Deviation**: `deviation = current_altitude - baseline`
4. **Trigger**: If `abs(deviation) > threshold` → obstacle detected
5. **Clearing**: 
   - Deviation returns to ±0.1m of baseline
   - Timeout reached (8s)

**API:**

- `update(lidar_altitude, current_time) -> bool`: Update detector, returns True if obstacle
- `reset()`: Clear all state
- `is_obstacle_detected`: Property for current state
- `get_elapsed_time(current_time)`: Time since detection

**Integration with Position Controller:**

```python
# In navigate_PID()
if obstacle_detected:
    vz = 0.0  # Stop vertical PID control
    # ArduPilot maintains altitude via rangefinder
else:
    vz = pid_z.update(altitude_error)  # Normal PID control
```

## Obstacle Detection Scenarios

### Scenario 1: Arriving Above Elevated Surface

**Setup:** Drone at 1.5m altitude navigates to waypoint above 1.2m plate.

```
Ground Level          Plate Surface
     ↓                      ↓
═════════                ╔═══╗
                         ║1.2m║
█████████████████████████████████  Ground
```

**Sequence:**

1. Lidar reads 1.5m (ground distance)
2. Approaching plate: lidar drops to 0.3m
3. `deviation = -1.2m` → **Obstacle detected**
4. Vertical PID: `vz = 0.0`
5. ArduPilot maintains altitude relative to plate
6. Horizontal navigation continues normally
7. Arrives at X/Y target

**Result:** Drone hovers at safe altitude above plate surface, not ground.

### Scenario 2: Passing Over Elevated Surface

**Setup:** Drone flies from point A to B, crossing 0.8m plate.

```
Start            Plate             Target
  ↓                ↓                 ↓
═════          ╔══════╗          ═════
               ║ 0.8m ║
█████████████████████████████████████  Ground
       ←──── Flight Path ────→
```

**Timeline:**

| Time | Event | Lidar | Control |
|------|-------|-------|---------|
| 0.0s | Over ground | 1.5m | PID active |
| 2.0s | Plate edge | 0.7m | ArduPilot takes over |
| 2-5s | Over plate | 0.7m | ArduPilot maintains |
| 5.0s | Leaving plate | 1.5m | Still ArduPilot |
| 5.5s | Cleared (dev < 0.1m) | 1.5m | PID resumes |
| 6.0s | Target reached | 1.5m | PID active |

**Behavior:**
- Drone rises by 0.8m when over plate (ArduPilot compensation)
- After clearing, PID resumes and returns to target altitude
- Horizontal navigation unaffected throughout

### Scenario 3: Multiple Close Obstacles

**Setup:** Multiple plates with <1m gaps between them.

```
     0.5m      0.3m      1.2m
   ╔════╗    ╔════╗    ╔════╗
   ║    ║    ║    ║    ║    ║
█████████████████████████████████  Ground
   ←──── Flight Path ────→
```

**Behavior:**

- **Small gaps (<1m)**: Buffer not fully refilled between plates
  - Obstacle state persists across gaps
  - Smoother flight (less control switching)

- **Large gaps (>1m)**: Buffer refills between plates
  - Obstacle cleared between plates
  - PID briefly resumes, then re-detects next plate

- **Timeout protection**: After 8s continuous detection
  - PID forcefully resumes
  - Prevents stuck state

**Buffer Size Impact:**
```python
buffer_size = 10 samples
update_rate = 10 Hz
buffer_time = 1 second

# Example:
plate_width = 1.5m
flight_speed = 0.5 m/s
time_over_plate = 3s  # Enough for detection + clearing
```

## Best Practices

### Grid Navigation (Constant Altitude)

**Recommended for:** Detection missions, mapping, inspection

```python
GRID_ALTITUDE = 1.8  # meters above ground

drone.arm_takeoff(GRID_ALTITUDE)  # Sets takeoff position automatically

for waypoint in grid_waypoints:
    drone.offboard_position(
        x=waypoint.x - current_x,
        y=waypoint.y - current_y,
        z=0.0,  # Maintain altitude
        precision_radius=0.3,
        strategy="PID",
        ground_reference=True  # Requires takeoff position set
    )
```

**Advantages:**
- Constant altitude for consistent sensor readings
- Obstacle detector prevents crashes over elevated surfaces
- ArduPilot automatically compensates for obstacles
- Returns to grid altitude after clearing obstacles

### Terrain Following

**Recommended for:** Terrain mapping, low-altitude flight over varying ground

```python
drone.offboard_position(
    x=target_x,
    y=target_y,
    z=0.0,
    lidar_target_alt=1.5,  # Stay 1.5m above surface
    precision_radius=0.5,
    strategy="PID"
)
```

**Behavior:**
- Follows terrain contours
- Climbs over elevated surfaces maintaining clearance
- Uses lidar as primary altitude reference

**Limitations:**
- Limited to 15m maximum altitude (lidar range)
- Not ideal for detecting specific objects at fixed altitudes

---

### GPSController (gps_controller.py)

GPS-specific navigation and geofencing utilities.

**Features:**

1. **Geofencing**
   ```python
   gps_controller.geofence(
       coords=[
           (-22.415, -45.447),
           (-22.414, -45.447),
           (-22.415, -45.442)
       ],
       rtl=True  # RTL on breach (False = kill motors)
   )
   ```
   - Polygon boundary checking
   - Auto-trigger RTL or motor kill on breach
   - 100Hz monitoring rate

2. **GPS Navigation**
   ```python
   gps_controller.gps_send(
       lat_setpoint=lat,
       lon_setpoint=lon,
       alt_setpoint=alt,
       heading=heading,
       precision_radius=0.5,
       alt_threshold=0.1,
       wait=True  # Block until reached
   )
   ```
   - Direct GPS coordinate setpoints
   - AMSL ↔ Ellipsoid height conversion (EGM96)
   - Blocking or non-blocking modes

3. **Utilities**
   - `calculate_bearing(lat, lon)`: Heading to coordinate
   - `haversine_distance(lat, lon)`: Distance to coordinate
   - `geoid_height(lat, lon)`: AMSL/ellipsoid conversion

**Note:** GPSController uses legacy setpoint publishing. For new code, use `MavDrone.offboard_position_gps_coords()` with `strategy="PID"`.

---

### PrecisionLanding (precision_landing.py)

ArUco marker-based precision landing for package delivery.

**Initialization:**
```python
PrecisionLanding(
    drone=drone,
    node=node,
    delivery=True,    # Enable package release
    aruco_target=42   # Target marker ID
)
```

**Process:**

1. **Detection Phase** (altitude > 8m):
   - Descends at 0.4 m/s
   - Scans for target ArUco marker

2. **Centering Phase** (8m > alt > 1.2m):
   - Visual servoing to marker center
   - Proportional control: `kp = 0.2`
   - Landing area: `0.04 * altitude`

3. **Landing Phase** (alt < 1.2m):
   - Execute landing
   - Package delivery (if enabled):
     - Servo control for release mechanism
     - Auto-takeoff to 10m
     - RTL

**Control Law:**
```python
vel_x = -0.2 * marker_translation_y
vel_y = -0.2 * marker_translation_x
```

**Integration:**
- Auto-starts `aruco_node` for marker detection
- Subscribes to `/aruco/pose_estimate`
- Self-cleanup on completion

---

## Configuration Files

Located in `config/mavros/`:

### position_indoor.yaml
```yaml
x:
  kp: 0.5
  output_min: -0.42
  output_max: 0.42
y:
  kp: 0.5
  output_min: -0.42
  output_max: 0.42
z:
  kp: 0.5
  output_min: -0.2
  output_max: 0.2
```

### position_outdoor.yaml
```yaml
x:
  kp: 0.8
  output_min: -1.0
  output_max: 1.0
y:
  kp: 0.8
  output_min: -1.0
  output_max: 1.0
z:
  kp: 0.5
  output_min: -0.8
  output_max: 0.8
```

---

## Usage Examples

### Basic Indoor Flight

```python
import rclpy
from mirela_sdk.control.mavros import MavDrone

rclpy.init()
node = rclpy.create_node('drone_node')

drone = MavDrone(node, indoor=True, mavros=True)

drone.arm_takeoff(1.5)

drone.offboard_position(x=1.0, y=0.5, z=0.0, strategy="PID")

drone.rtl(rtl_strategy="PID", land=True)
```

### Custom PID Configuration

```python
drone = MavDrone(node, indoor=True, mavros=True)

# Option 1: Load from YAML file
drone.set_pid_config("/path/to/aggressive_indoor.yaml")

# Option 2: Set from dictionary
drone.set_pid_config({
    "x": {"kp": 0.8, "output_min": -0.6, "output_max": 0.6},
    "y": {"kp": 0.8, "output_min": -0.6, "output_max": 0.6},
    "z": {"kp": 0.6, "output_min": -0.3, "output_max": 0.3}
})

# Option 3: Set from PositionPIDConfig object
from mirela_sdk.control.pid import PositionPIDConfig, PIDConfig
config = PositionPIDConfig(
    x=PIDConfig(kp=0.8, output_min=-0.6, output_max=0.6),
    y=PIDConfig(kp=0.8, output_min=-0.6, output_max=0.6),
    z=PIDConfig(kp=0.6, output_min=-0.3, output_max=0.3)
)
drone.set_pid_config(config)

# Navigate with new configuration
drone.offboard_position(x=5.0, y=0.0, z=1.0, strategy="PID")
```

---

## Exception Handling

### Custom Exceptions

```python
from mirela_sdk.control.mavros import (
    TakeoffPositionNotSetError,
    SensorNotAvailableError,
    InvalidModeError
)
```

**TakeoffPositionNotSetError:**
- Raised when using `ground_reference=True` or `rtl()` without setting takeoff position
- Solution: Call `arm_takeoff()` or `set_takeoff_position()` first

**SensorNotAvailableError:**
- Raised when accessing sensors unavailable in current mode
- Examples: GPS/heading in indoor mode

**InvalidModeError:**
- Raised when operation requires different flight mode
- Example: GPS navigation in indoor mode

### Usage Example

```python
try:
    drone.offboard_position(x=1.0, y=0.0, ground_reference=True)
except TakeoffPositionNotSetError as e:
    print(f"Error: {e}")
    drone.arm_takeoff(2.0)  # Set takeoff position
    drone.offboard_position(x=1.0, y=0.0, ground_reference=True)
```

---

## References

- [ArduPilot Copter Documentation](https://ardupilot.org/copter/)
- [MAVROS Documentation](https://github.com/mavlink/mavros)
- [ArduPilot Altitude Understanding](https://ardupilot.org/copter/docs/common-understanding-altitude.html)
- [MAVLink Protocol](https://mavlink.io/en/)

