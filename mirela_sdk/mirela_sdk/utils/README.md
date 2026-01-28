# Utilities Module 🧙‍♂️

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
| `is_gui_available()` | Check if gnome-terminal is present 🖥️ |
| `start_process(command, name, gui)` | Launch command in tmux session or terminal |
| `has_process(name)` | Check if tmux session exists 🔍 |
| `kill_process(name)` | Terminate tmux session ❌ |

### Usage

```python
from mirela_sdk.utils import ProcessUtils

# Start a ROS2 node in background
ProcessUtils.start_process(
    command="ros2 run mavros mavros_node",
    name="mavros_session",
    gui=False  # Use tmux (headless)
)

# Check if running
if ProcessUtils.has_process("mavros_session"):
    print("MAVROS is running")

# Stop the process
ProcessUtils.kill_process("mavros_session")
```

## GPS Utilities

Geographic coordinate calculations using [pygeodesy](https://mrjean1.github.io/PyGeodesy/) for geodetic operations.

### Functions

| Function | Description |
|----------|-------------|
| `haversine_distance(lat1, lon1, lat2, lon2)` | Distance between GPS points (meters) |
| `calculate_bearing(lat1, lon1, lat2, lon2)` | Bearing angle between points (degrees) |
| `geoid_height(lat, lon)` | EGM96 geoid undulation at location |
| `gps_to_local(lat, lon, ref_lat, ref_lon)` | Convert GPS to local NED frame |

### Usage

```python
from mirela_sdk.utils.gps_calculate import haversine_distance, calculate_bearing

# Calculate distance between two GPS coordinates
dist = haversine_distance(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Distance: {dist:.2f} m")

# Calculate bearing
bearing = calculate_bearing(-27.1234, -48.4567, -27.1245, -48.4578)
print(f"Bearing: {bearing:.1f}°")
```

## Position Utilities

Coordinate transformations and rotation conversions.

### Functions

| Function | Description |
|----------|-------------|
| `quaternion_to_euler(q)` | Quaternion to roll, pitch, yaw |
| `euler_to_quaternion(roll, pitch, yaw)` | Euler angles to quaternion |
| `body_to_world(velocity, yaw)` | Body-frame to world-frame velocity |
| `world_to_body(velocity, yaw)` | World-frame to body-frame velocity |

### Usage

```python
from mirela_sdk.utils.position_utils import body_to_world, quaternion_to_euler

# Convert body-frame velocity to world-frame
vx_world, vy_world = body_to_world(vx=1.0, vy=0.5, yaw=45.0)

# Convert quaternion to Euler angles
roll, pitch, yaw = quaternion_to_euler([0.0, 0.0, 0.707, 0.707])
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `pygeodesy` | Geodetic calculations |
| `transforms3d` | Rotation conversions |
| `numpy` | Array operations |
