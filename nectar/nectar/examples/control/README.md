# Control Module Examples

| File | Description | Args |
|------|-------------|------|
| `basic.py` | Takeoff, velocity, land | `--drone mavros\|bebop` |
| `sensors.py` | Monitor GPS/vision data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `mavros_navigation.py` | Navigation test (BODY, TAKEOFF, GPS) | `--mode --no-takeoff --test --distance` |
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

# Navigation — full outdoor flight
python3 mavros_navigation.py --mode outdoor

# Navigation — hand-held test (no takeoff, verify axes)
python3 mavros_navigation.py --mode outdoor --no-takeoff --test body

# Navigation — TAKEOFF reference only
python3 mavros_navigation.py --mode indoor --no-takeoff --test takeoff-ref

# Navigation — custom distance and specific tests
python3 mavros_navigation.py --mode outdoor --test body gps --distance 3.0
```
