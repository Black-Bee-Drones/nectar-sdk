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

## Position Utilities

Coordinate transformations, rotation conversions, and ROS message utilities.

### PositionUtils Class

Static utility class for position and orientation operations.

| Method | Description |
|--------|-------------|
| `get_body_distance(target, current, heading)` | Calculate distance from current to target in body frame coordinates |
| `get_yaw_from_pose(pose)` | Extract yaw angle from ROS pose message (radians) |
| `convert_position_to_target(pose, heading, lidar)` | Convert position messages to target message types |
| `transform_takeoff_to_body_velocities(vx, vy, vz, current_yaw, takeoff_yaw)` | Transform velocities from takeoff frame to body frame |

### Usage

```python
from nectar.utils.position_utils import PositionUtils
from geometry_msgs.msg import PoseWithCovarianceStamped
from mavros_msgs.msg import PositionTarget

# Calculate body frame distance
dx_body, dy_body, dz_body = PositionUtils.get_body_distance(
    target=target_position,  # PositionTarget or GeoPoseStamped
    current=current_pose,     # PoseWithCovarianceStamped or NavSatFix
    heading=45.0  # degrees
)

# Extract yaw from pose
yaw = PositionUtils.get_yaw_from_pose(pose_message)  # radians

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
- `target`: `PositionTarget` (indoor) or `GeoPoseStamped` (outdoor)
- `current`: `PoseWithCovarianceStamped` (indoor) or `NavSatFix` (outdoor)

**PositionUtils.get_yaw_from_pose()**:
- `PoseWithCovarianceStamped`, `GeoPoseStamped`, or `PositionTarget`

**PositionUtils.convert_position_to_target()**:
- `PoseWithCovarianceStamped` → `PositionTarget` (indoor)
- `NavSatFix` → `GeoPoseStamped` (outdoor, requires heading)

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
