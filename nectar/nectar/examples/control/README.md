# Control Module Examples

| File | Description | Args |
|------|-------------|------|
| `basic.py` | Takeoff, velocity/hover/position patterns, land | `--drone mavros\|mavlink\|bebop\|crazyflie --mode velocity\|hover\|position` |
| `sensors.py` | Monitor GPS/vision/local data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `navigation.py` | Navigation test (BODY, TAKEOFF, GPS) | `--drone --mode --strategy --test --distance` |
| `interactive_navigation.py` | Interactive REPL — type waypoints live | `--drone --mode --strategy --altitude` |
| `servo_test.py` | Interactive REPL — pre-flight servo / PWM tester via `MAV_CMD_DO_SET_SERVO` | `--channel --hold --release` |
| `obstacles.py` | Obstacle avoidance | - |

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

## Navigation

Works with both ArduPilot transports via `--drone mavros|mavlink` (default `mavros`).

```bash
# Full outdoor flight (default: PID strategy)
python3 navigation.py --mode outdoor

# Direct pymavlink transport
python3 navigation.py --drone mavlink --test body

# Use EKF local position instead of raw GPS
python3 navigation.py --strategy pid-ekf

# Local setpoint (FCU handles position control)
python3 navigation.py --strategy position --test body

# GPS global setpoint for long-range waypoints
python3 navigation.py --mode outdoor --test gps --strategy position-global

# Hand-held test (no takeoff, verify navigation logic)
python3 navigation.py --no-takeoff --test body

# Custom distance, specific tests
python3 navigation.py --test body takeoff-ref --distance 3.0

# Figure-8 pattern (8 waypoints, tests sequential precision)
python3 navigation.py --test figure8 --distance 3.0

# Rectangle with midpoints (8 waypoints, denser precision sampling)
python3 navigation.py --test rectangle --strategy pid-ekf --distance 4.0

# GPS rectangle (4 GPS waypoints, outdoor only)
python3 navigation.py --test gps-rectangle --strategy position-global --distance 5.0
```

## Interactive Navigation

```bash
# Outdoor with default PID
python3 interactive_navigation.py --mode outdoor

# Direct pymavlink transport
python3 interactive_navigation.py --drone mavlink --mode outdoor

# Outdoor with EKF, 3m altitude
python3 interactive_navigation.py --mode outdoor --strategy pid-ekf --altitude 3.0

# Hand-held testing (no arm/takeoff)
python3 interactive_navigation.py --no-takeoff
```

Once running, type waypoints at the `nav>` prompt:

```
nav> 2 0           # 2m forward
nav> 0 3 0         # 3m left, hold altitude
nav> -2 -3 0       # back
nav> set ref takeoff
nav> 5 0 0         # 5m forward from takeoff origin
nav> 0 0 0         # return to takeoff
nav> set method pid-ekf
nav> 3 2            # now uses PID_EKF
nav> gps -22.413 -45.449 15
nav> status         # show drone state + settings
nav> land
```

### Navigation Strategies

| Strategy | Description |
|----------|-------------|
| `pid` (default) | PID velocity control using raw sensors (vision/GPS) |
| `pid-ekf` | PID velocity control using EKF local position |
| `position` | Local position setpoint via `setpoint_raw/local` |
| `position-global` | GPS global setpoint (outdoor only, long range) |

## Servo / PWM Test

Drives `MavrosDrone.do_servo` (`MAV_CMD_DO_SET_SERVO`, 183) from a REPL so you
can verify the correct AUX OUT channel and the PWM endpoints (e.g. hook hold /
release) on the bench. The script never arms the drone and never takes off —
keep props off.

```bash
# MAVROS already running. Defaults: channel=3 (FCU ch 11 = AUX OUT 3),
# hold=1000us, release=2000us.
python3 servo_test.py

# Custom channel and presets
python3 servo_test.py --channel 4 --hold 1100 --release 1900
```

At the `servo>` prompt:

```
servo> 1500              # send PWM 1500 to current channel
servo> ch 3              # switch to AUX OUT 3 (FCU ch 11)
servo> hold              # send 'hold' preset
servo> release           # send 'release' preset
servo> sweep 1000 2000 100 0.3
servo> cycle 3 0.8       # toggle hold<->release 3 times, 0.8s apart
servo> set hold 1100     # update presets at runtime
servo> status            # channel, last PWM, FCU state
```

`do_servo(N, pwm)` maps to FCU servo number `N + 8`, so `ch 3` drives AUX OUT 3
on a Pixhawk-style FCU (Copter recommends AUX OUT 1-4 for hobby servos at 50 Hz;
avoid MAIN OUT 1-8, which run at 400 Hz). If a write returns `OK` but the servo
does not move, check the safety switch and that `SERVOx_FUNCTION = 0` in
ArduPilot. See [common-servo](https://ardupilot.org/copter/docs/common-servo.html)
and [MAV_CMD_DO_SET_SERVO](https://mavlink.io/en/messages/common.html#MAV_CMD_DO_SET_SERVO).
