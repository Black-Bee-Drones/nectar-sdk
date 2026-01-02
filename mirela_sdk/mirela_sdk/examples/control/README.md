# Control Module Examples

| File | Description | Args |
|------|-------------|------|
| `basic.py` | Takeoff, velocity, land | `--drone mavros\|bebop` |
| `sensors.py` | Monitor GPS/vision data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `mavros_navigation.py` | PID position navigation | - |
| `mavros_obstacles.py` | Obstacle avoidance | - |

## Usage

```bash
# Basic flight
python3 basic.py --drone mavros

# Sensor monitoring
python3 sensors.py --source gps

# PID simulation (no ROS required)
python3 pid_simulation.py
python3 pid_simulation.py --setpoint 30 --kp 0.8 --ki 0.2
python3 pid_simulation.py --plot

# Navigation
python3 mavros_navigation.py
```

