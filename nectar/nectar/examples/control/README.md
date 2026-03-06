# Control Module Examples

| File | Description | Args |
|------|-------------|------|
| `basic.py` | Takeoff, velocity, land | `--drone mavros\|bebop` |
| `sensors.py` | Monitor GPS/vision/local data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `mavros_navigation.py` | Navigation test (BODY, TAKEOFF, GPS) | `--mode --strategy --test --distance` |
| `mavros_obstacles.py` | Obstacle avoidance | - |

## Usage

```bash
# Basic flight
python3 basic.py --drone mavros

# Sensor monitoring
python3 sensors.py --source gps
python3 sensors.py --source vision

# PID simulation (no ROS required)
python3 pid_simulation.py
python3 pid_simulation.py --setpoint 30 --kp 0.8 --ki 0.2
python3 pid_simulation.py --plot

# Navigation — full outdoor flight (default: PID strategy)
python3 mavros_navigation.py --mode outdoor

# Navigation — use EKF local position instead of raw GPS
python3 mavros_navigation.py --strategy pid-local

# Navigation — local setpoint (FCU handles position control)
python3 mavros_navigation.py --strategy setpoint --test body

# Navigation — GPS global setpoint for long-range waypoints
python3 mavros_navigation.py --mode outdoor --test gps --strategy setpoint-global

# Navigation — hand-held test (no takeoff, verify navigation logic)
python3 mavros_navigation.py --no-takeoff --test body

# Navigation — custom distance, specific tests
python3 mavros_navigation.py --test body takeoff-ref --distance 3.0
```

## Navigation Strategies

| Strategy | Description |
|----------|-------------|
| `pid` (default) | PID velocity control using raw sensors (vision/GPS) |
| `pid-local` | PID velocity control using EKF local position |
| `setpoint` | Local position setpoint via `setpoint_raw/local` |
| `setpoint-global` | GPS global setpoint (outdoor only, long range) |
