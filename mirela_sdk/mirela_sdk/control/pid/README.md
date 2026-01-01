# PID Control Module

A PID controller implementation for mirela_sdk, supporting both programmatic usage and standalone ROS2 node operation.

## Features

- **YAML Configuration**: configuration via YAML files
- **Obstacle Detection**: Lidar-based obstacle detection for altitude control
- **ROS2 Node**: Standalone node with dynamic parameter reconfiguration
- **Reusable**: Use programmatically or as a ROS2 node

## Usage

### 1. Programmatic Usage (Python)

```python
from mirela_sdk.control.pid import PIDController

# Create PID controller
pid = PIDController(
    kp=0.5,
    ki=0.0,
    kd=0.0,
    setpoint=100.0,
    output_limits=(-1.0, 1.0),
    integral_limits=(-0.5, 0.5)
)

# Update with current value
control_effort = pid.update(current_value=95.0)

# Tune gains dynamically
pid.tune(kp=0.8, ki=0.1, kd=0.05)

# Reset controller
pid.reset()
```

### 2. YAML Configuration

Create a YAML file (e.g., `my_pid_config.yaml`):

```yaml
x:
  kp: 0.5
  ki: 0.0
  kd: 0.0
  output_min: -1.0
  output_max: 1.0
  integral_min: -0.5
  integral_max: 0.5
```

Load configuration:

```python
from mirela_sdk.control.pid import PIDConfig, PositionPIDConfig

# Single axis PID
config = PIDConfig.from_yaml("my_pid_config.yaml")

# Multi-axis position control
pos_config = PositionPIDConfig.from_yaml("position_config.yaml")
```

### 3. Standalone ROS2 Node

Run as a standalone node for dynamic tuning:

```bash
ros2 run mirela_sdk pid_controller_node \
  --ros-args \
  -p p_gain:=0.5 \
  -p i_gain:=0.0 \
  -p d_gain:=0.0 \
  -p output_min:=-1.0 \
  -p output_max:=1.0 \
  -p state_topic:=/my/state \
  -p setpoint_topic:=/my/setpoint \
  -p control_effort_topic:=/my/control
```

### 4. Position Control with Custom Config

```python
from mirela_sdk.control.mavros.mavros_api import MavDrone

# Initialize drone
drone = MavDrone(node=node, indoor=True)

# Set custom PID configuration
drone.set_pid_config("path/to/my_config.yaml")

# Use position control with PID
drone.offboard_position(x=1.0, y=0.5, z=0.0, strategy="PID")
```

### 5. Centering Control

```python
from mirela_sdk.control.pid import PIDController

# Simple P controller for centering
centering_pid_x = PIDController(kp=0.001, output_limits=(-0.3, 0.3))
centering_pid_y = PIDController(kp=0.001, output_limits=(-0.3, 0.3))

# Update with error from image center
vel_x = centering_pid_y.update(-error_y)  
vel_y = centering_pid_x.update(-error_x)

drone.offboard_velocity(vel_x, vel_y, 0.0, 0.0)
```

## Mavros-Specific Features

For Mavros position control configurations and obstacle detection, see:
- Position control configs: `config/mavros/position_indoor.yaml` and `position_outdoor.yaml`
- Mavros documentation: `mirela_sdk/control/mavros/README.md`

## Dynamic Reconfiguration (ROS2 Node)

Change PID parameters in real-time:

```bash
ros2 param set /pid_controller p_gain 0.8
ros2 param set /pid_controller i_gain 0.1
ros2 param set /pid_controller d_gain 0.05
```

Enable/disable controller:

```bash
ros2 topic pub /pid_enable std_msgs/Bool "data: true"
```

## API Reference

### PIDController

- `update(current_value: float) -> float`: Compute control output
- `reset()`: Reset internal state
- `set_setpoint(setpoint: float)`: Update target value
- `tune(kp, ki, kd)`: Update gains
- `get_components() -> dict`: Get P, I, D components for debugging

### PIDConfig

- `from_yaml(file_path)`: Load from YAML file
- `from_dict(config_dict)`: Load from dictionary
- `get_output_limits()`: Get output limits tuple
- `get_integral_limits()`: Get integral limits tuple

