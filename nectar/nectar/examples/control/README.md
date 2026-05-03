# Control Module Examples

| File | Description | Args |
|------|-------------|------|
| `basic.py` | Takeoff, velocity/hover/position patterns, land | `--drone mavros\|bebop\|crazyflie --mode velocity\|hover\|position` |
| `sensors.py` | Monitor GPS/vision/local data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `mavros_navigation.py` | Navigation test (BODY, TAKEOFF, GPS) | `--mode --strategy --test --distance` |
| `mavros_obstacles.py` | Obstacle avoidance | - |

## Basic Flight

```bash
# MAVROS -- velocity box at 2m altitude
python3 basic.py --drone mavros --height 2.0

# Crazyflie -- hover test in simulation
python3 basic.py --drone crazyflie --mode hover --height 0.5 --backend sim --hover-time 10

# Crazyflie -- position box (move_to) with 0.6m sides
python3 basic.py --drone crazyflie --mode position --height 0.5 --side 0.6

# Crazyflie -- velocity box at 0.4m altitude
python3 basic.py --drone crazyflie --mode velocity --height 0.4 --velocity 0.2 --side 0.5

# Bebop -- velocity box
python3 basic.py --drone bebop --mode velocity
```

### Modes

| Mode | Description |
|------|-------------|
| `velocity` (default) | Takeoff, fly a square with velocity commands, land |
| `hover` | Takeoff, hold position for `--hover-time` seconds, land |
| `position` | Takeoff, fly a square with `move_to` commands, land |

## Sensor Monitoring

```bash
python3 sensors.py --source gps
python3 sensors.py --source vision
```

## PID Simulation

```bash
python3 pid_simulation.py
python3 pid_simulation.py --setpoint 30 --kp 0.8 --ki 0.2
python3 pid_simulation.py --plot
```

## MAVROS Navigation

```bash
# Full outdoor flight (default: PID strategy)
python3 mavros_navigation.py --mode outdoor

# Use EKF local position instead of raw GPS
python3 mavros_navigation.py --strategy pid-ekf

# Local setpoint (FCU handles position control)
python3 mavros_navigation.py --strategy position --test body

# GPS global setpoint for long-range waypoints
python3 mavros_navigation.py --mode outdoor --test gps --strategy position-global

# Hand-held test (no takeoff, verify navigation logic)
python3 mavros_navigation.py --no-takeoff --test body

# Custom distance, specific tests
python3 mavros_navigation.py --test body takeoff-ref --distance 3.0

# Figure-8 pattern (8 waypoints, tests sequential precision)
python3 mavros_navigation.py --test figure8 --distance 3.0

# Rectangle with midpoints (8 waypoints, denser precision sampling)
python3 mavros_navigation.py --test rectangle --strategy pid-ekf --distance 4.0

# GPS rectangle (4 GPS waypoints, outdoor only)
python3 mavros_navigation.py --test gps-rectangle --strategy position-global --distance 5.0
```

### Navigation Strategies

| Strategy | Description |
|----------|-------------|
| `pid` (default) | PID velocity control using raw sensors (vision/GPS) |
| `pid-ekf` | PID velocity control using EKF local position |
| `position` | Local position setpoint via `setpoint_raw/local` |
| `position-global` | GPS global setpoint (outdoor only, long range) |
