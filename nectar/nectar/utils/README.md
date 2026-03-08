# Utilities Module

Shared utility functions for process management, GPS calculations, and position operations.

## Components

| File | Description |
|------|-------------|
| `process.py` | Process lifecycle management using tmux/gnome-terminal |
| `gps_calculate.py` | GPS coordinate transformations and distance calculations |
| `position_utils.py` | Position/orientation conversions and transformations |

## ProcessUtils

Manages external processes with tmux or gnome-terminal fallback.

### API

| Method | Description |
|--------|-------------|
| `is_gui_available()` | Check if gnome-terminal is available |
| `get_ros2_nodes(timeout)` | Get list of running ROS2 node names |
| `is_node_running(node_pattern, timeout)` | Check if ROS2 node matching pattern is running |
| `wait_for_node(node_pattern, timeout, poll_interval)` | Wait for ROS2 node to appear |
| `start_process(command, name, gui)` | Launch command in tmux session or terminal |
| `has_process(name)` | Check if tmux session exists |
| `kill_process(name)` | Terminate tmux session |

### Usage

```python
from nectar.utils import ProcessUtils

# Check if ROS2 node is running
if ProcessUtils.is_node_running("mavros_node"):
    print("MAVROS node is running")

# Start a ROS2 node in background
ProcessUtils.start_process(
    command="ros2 launch mavros apm.launch fcu_url:=serial:///dev/ttyUSB0:921600",
    name="mavros_node",
    gui=False  # Use tmux (headless)
)

# Wait for node to appear
if ProcessUtils.wait_for_node("mavros_node", timeout=10.0):
    print("MAVROS node started")

# Check if tmux session exists
if ProcessUtils.has_process("mavros_node"):
    print("MAVROS session exists")

# Stop the process
ProcessUtils.kill_process("mavros_node")
```

### Behavior

- `start_process()` checks for existing tmux session and kills it before starting
- `kill_process()` returns True if session does not exist (no error)
- All methods use Python logging module (no print statements)
- ROS2 node detection uses `ros2 node list` command

## GPS Utilities

Geographic coordinate calculations using [geographiclib](https://geographiclib.sourceforge.io/) for geodetic operations.

### GPSCalculate Class

Static utility class for GPS coordinate calculations.

| Method | Description |
|--------|-------------|
| `haversine(lat1, lon1, lat2, lon2)` | Distance between GPS points using Haversine formula (meters) |
| `bearing(lat1, lon1, lat2, lon2)` | Initial bearing angle between points (degrees, 0-360°) |
| `calculate_gps_offset(x, y, z, lat, lon, alt, heading)` | Calculate new GPS coordinates from offset in meters |
| `interp_geo(start, end, frac)` | Geodesic interpolation between two GPS coordinates |
| `generate_point_grid(vertices, grid_shape)` | Generate 2D grid of GPS coordinates within quadrilateral area |

### Usage

```python
from nectar.utils.gps_calculate import GPSCalculate

# Calculate distance between two GPS coordinates
dist = GPSCalculate.haversine(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Distance: {dist:.2f} m")

# Calculate bearing
bearing = GPSCalculate.bearing(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Bearing: {bearing:.1f}°")

# Calculate GPS offset
new_lat, new_lon, new_alt = GPSCalculate.calculate_gps_offset(
    x=10.0,  # 10 meters east
    y=5.0,   # 5 meters north
    z=2.0,   # 2 meters up
    latitude=-27.1234,
    longitude=-48.4567,
    altitude=100.0,
    heading=45.0  # degrees
)

# Interpolate between GPS points
midpoint = GPSCalculate.interp_geo(
    start=(-27.1234, -48.4567),
    end=(-27.1245, -48.4578),
    frac=0.5  # 50% of the way
)

# Generate grid of GPS points
vertices = (
    (-27.1234, -48.4567),  # top-left
    (-27.1234, -48.4578),  # top-right
    (-27.1245, -48.4578),  # bottom-right
    (-27.1245, -48.4567),  # bottom-left
)
grid = GPSCalculate.generate_point_grid(vertices, grid_shape=(10, 10))
```

### Haversine vs Geodesic Precision

`PositionUtils.get_body_distance()` uses `Geodesic.WGS84.Inverse` ([Karney 2013](https://doi.org/10.1007/s00190-012-0578-z)) for GPS distance and bearing. Haversine (spherical, R=6371km) remains in `GPSCalculate` for general use.

Points placed at exact known distances using `Geodesic.WGS84.Direct` (accurate to ~15nm). Both methods then compute the distance. Full benchmark: [`scripts/benchmark_geodesic_vs_haversine.py`](../../../scripts/experiments/benchmark_geodesic_vs_haversine.py)

**Distance error** (against exact known distances):

| Distance | Geodesic Error | Haversine Error | Haversine % |
|----------|---------------:|----------------:|------------:|
| 1m N | 0.80 nm | 0.35 cm | 0.353% |
| 1m E | 0.09 nm | 0.18 cm | 0.181% |
| 5m N | 0.10 nm | 1.77 cm | 0.353% |
| 10m E | 0.14 nm | 1.81 cm | 0.181% |
| 50m N | 0.16 nm | 17.66 cm | 0.353% |
| 100m E | 0.02 nm | 18.08 cm | 0.181% |
| 1km | 0.00 nm | 1.23 m | 0.123% |
| 5km | 0.00 nm | 17.68 m | 0.354% |
| 100km | 0.00 nm | 121.91 m | 0.122% |
| 500km | 0.00 nm | 2138.93 m | 0.428% |

Haversine error is (0.1%–0.43%), driven by Earth's flattening (1/298). It underestimates equatorial distances (~0.11%) and polar distances (~0.45%) because the actual radius of curvature differs from the mean sphere.

**Bearing error**: Geodesic is exact (0.000000°). Haversine < 0.2° for typical cases.

**Timing** (mean over 10,000 iterations):

| Scale | Haversine+Bearing | Geodesic.Inverse | Ratio |
|-------|------------------:|-----------------:|------:|
| 1m | 18 µs | 37 µs | 2.1x |
| 10m | 17 µs | 93 µs | 5.4x |
| 1km | 22 µs | 38 µs | 1.7x |
| 100km | 18 µs | 93 µs | 5.1x |
| 5570km | 18 µs | 152 µs | 8.4x |

Both are negligible for a 100Hz PID loop (10ms budget). Geodesic worst case is < 200µs.

## Position Utilities

Coordinate transformations, rotation conversions, and ROS message utilities.

### PositionUtils Class

Static utility class for position and orientation operations.

| Method | Description |
|--------|-------------|
| `get_body_distance(target, current, heading)` | Calculate distance from current to target in body frame coordinates |
| `get_yaw_from_pose(pose)` | Extract yaw angle from ROS pose message (radians) |
| `compute_yaw_error(target_yaw, current_yaw, threshold)` | Compute shortest-path yaw error in radians with optional deadband |
| `convert_position_to_target(pose, heading, lidar)` | Convert position messages to target message types |
| `transform_takeoff_to_body_velocities(vx, vy, vz, current_yaw, takeoff_yaw)` | Transform velocities from takeoff frame to body frame |

### Usage

```python
from nectar.utils.position_utils import PositionUtils
from geometry_msgs.msg import PoseStamped
from mavros_msgs.msg import PositionTarget

# Calculate body frame distance
dx_body, dy_body, dz_body = PositionUtils.get_body_distance(
    target=target_position,  # PositionTarget or GeoPoseStamped
    current=current_pose,     # PoseStamped, PoseWithCovarianceStamped, or NavSatFix
    heading=45.0  # degrees (required for NavSatFix)
)

# Extract yaw from pose
yaw = PositionUtils.get_yaw_from_pose(pose_message)  # radians

# Compute yaw error (shortest path, wrapped to [-pi, pi])
import numpy as np
dyaw = PositionUtils.compute_yaw_error(target_yaw=1.0, current_yaw=0.5)  # radians
dyaw = PositionUtils.compute_yaw_error(1.0, 0.5, threshold=np.radians(3))  # with deadband

# Convert position to target message
target = PositionUtils.convert_position_to_target(
    pose=current_pose,
    heading=45.0,  # degrees, required for NavSatFix
    lidar=2.5  # optional altitude override
)

# Transform velocities from takeoff frame to body frame
vx_body, vy_body, vz_body = PositionUtils.transform_takeoff_to_body_velocities(
    vx=1.0,
    vy=0.5,
    vz=0.0,
    current_yaw=0.785,  # radians (45°)
    takeoff_yaw=0.0     # radians
)
```

### Supported Message Types

**PositionUtils.get_body_distance()**:
- `target`: `PositionTarget` (local) or `GeoPoseStamped` (GPS)
- `current`: `PoseStamped` or `PoseWithCovarianceStamped` (local) or `NavSatFix` (GPS)

**PositionUtils.get_yaw_from_pose()**:
- `PoseStamped`, `PoseWithCovarianceStamped`, `GeoPoseStamped`, or `PositionTarget`

**PositionUtils.compute_yaw_error()**:
- `target_yaw`, `current_yaw`: floats in radians
- `threshold`: optional deadband in radians (errors below this return 0.0)

**PositionUtils.convert_position_to_target()**:
- `PoseStamped` / `PoseWithCovarianceStamped` → `PositionTarget` (local)
- `NavSatFix` → `GeoPoseStamped` (GPS, requires heading)

## Dependencies

| Package | Purpose |
|---------|---------|
| `geographiclib` | Geodetic calculations (WGS84 ellipsoid) |
| `tf_transformations` | ROS quaternion/Euler conversions |
| `numpy` | Array operations |
| `geographic_msgs` | ROS GPS message types |
| `geometry_msgs` | ROS pose message types |
| `mavros_msgs` | MAVROS message types |
| `sensor_msgs` | ROS sensor message types |
