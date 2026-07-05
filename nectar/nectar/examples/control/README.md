# Control Module Examples

Flight examples for every supported drone and transport, from a basic takeoff to an
interactive navigation REPL. Run any script with `python3 <script>.py [flags]` (or
`ros2 run nectar <script>.py -- [flags]`); they default to `start_driver=False`, so start
the matching driver, bridge, or simulator first.

| Script | What it does | Key flags |
|--------|--------------|-----------|
| `basic.py` | Takeoff, velocity/hover/position patterns, land | `--drone {mavros,mavlink,px4,px4_mavlink,px4_dds,bebop,crazyflie}` · `--env {outdoor,indoor}` · `--mode {velocity,hover,position}` · `--connection` (mavlink/px4_mavlink) · `--height --side --velocity --precision --hover-time --cf-name --backend` |
| `sensors.py` | Monitor GPS/vision/local data | `--source gps\|vision` |
| `pid_simulation.py` | PID controller simulation | `--kp --ki --plot` |
| `navigation.py` | ArduPilot/PX4 navigation test suite | `--drone {mavros,mavlink,px4}` · `--mode {indoor,outdoor}` · `--connection` · `--strategy --test --distance` (see below) |
| `interactive_navigation.py` | Interactive REPL — type waypoints live | `--drone {mavros,mavlink,px4,px4_mavlink,px4_dds}` · `--mode {indoor,outdoor}` · `--connection --strategy --altitude --no-takeoff` |
| `servo_test.py` | Interactive REPL — pre-flight servo / PWM tester via `MAV_CMD_DO_SET_SERVO` | `--channel --hold --release` |
| `obstacles.py` | Depth-camera obstacle-aware navigation (RealSense) | run directly: `python3 obstacles.py` |

> Pose source vs flight pattern: in `basic.py`, `--env {outdoor,indoor}` selects the **pose source** (outdoor = GPS, indoor = vision — match the sim's `ENV=`) and `--mode` selects the **flight pattern** (`velocity`/`hover`/`position`). In `navigation.py` / `interactive_navigation.py`, `--mode {indoor,outdoor}` selects the pose source. `--connection` overrides the connection string for the direct-pymavlink drones `--drone mavlink` (ArduPilot, e.g. `tcp:127.0.0.1:5762`) and `--drone px4_mavlink` (PX4, e.g. `udp:0.0.0.0:14540`); `--drone px4` (MAVROS) uses a `fcu_url` like `udp://:14540@127.0.0.1:14580`.

## Basic Flight

`basic.py` arms, takes off to `--height`, flies one `--mode` pattern, and lands. Common invocations:

| Case | Command |
|------|---------|
| ArduPilot / MAVROS, velocity box (outdoor GPS, default) | `python3 basic.py --drone mavros --height 2.0` |
| ArduPilot / MAVROS, indoor position box (vision pose) | `python3 basic.py --drone mavros --env indoor --mode position --height 2.0` |
| Crazyflie, hover in simulation | `python3 basic.py --drone crazyflie --mode hover --height 0.5 --backend sim --hover-time 10` |
| Crazyflie, position box (0.6 m sides) | `python3 basic.py --drone crazyflie --mode position --height 0.5 --side 0.6` |
| Crazyflie, velocity box | `python3 basic.py --drone crazyflie --mode velocity --height 0.4 --velocity 0.2 --side 0.5` |
| Bebop, velocity box | `python3 basic.py --drone bebop --mode velocity` |
| PX4 / MAVROS | `python3 basic.py --drone px4 --height 2.0` |
| PX4 / direct MAVLink | `python3 basic.py --drone px4_mavlink --connection udp:0.0.0.0:14540 --height 2.0` |
| PX4 / native uXRCE-DDS | `python3 basic.py --drone px4_dds --height 2.0` |

Expected result: the drone arms, climbs to `--height`, flies the selected pattern (a square for `velocity`/`position`, a timed hold for `hover`), then lands and disarms.

For PX4 in simulation start the matching sim first: `make sim-start FIRMWARE=px4 ENV=outdoor` plus `make sim-bridge FIRMWARE=px4 ENV=outdoor` (add `PROTOCOL=mavlink` for `px4_mavlink`, `PROTOCOL=dds` for `px4_dds`, which runs MicroXRCEAgent).

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

ArduPilot or PX4 — `--drone mavros|mavlink|px4` (default `mavros`). `--mode indoor` uses the vision pose source, `--mode outdoor` (default) uses GPS.

| Case | Command |
|------|---------|
| Full outdoor flight (default PID strategy) | `python3 navigation.py --mode outdoor` |
| Indoor (vision pose) over MAVROS | `python3 navigation.py --mode indoor --test body` |
| Direct MAVLink against SITL secondary port (5762) | `python3 navigation.py --drone mavlink --connection tcp:127.0.0.1:5762 --test body` |
| EKF local position instead of raw GPS | `python3 navigation.py --strategy pid-ekf` |
| Local setpoint (FCU handles position control) | `python3 navigation.py --strategy position --test body` |
| GPS global setpoint (long-range waypoints) | `python3 navigation.py --mode outdoor --test gps --strategy position-global` |
| Hand-held test (no takeoff) | `python3 navigation.py --no-takeoff --test body` |
| Custom distance, selected tests, CSV log, repeat 3x | `python3 navigation.py --test body takeoff-ref --distance 3.0 --csv runs.csv --loop 3` |

### Tests (`--test`, one or more; default `all`)

`body`, `takeoff-ref`, `altitude`, `velocity`, `gps`, `figure8`, `rectangle`, `cube-xyz`, `cube`, `gps-rectangle`. GPS tests (`gps`, `gps-rectangle`) require `--mode outdoor`.

### Other arguments

| Arg | Default | Purpose |
|-----|---------|---------|
| `--altitude` | `2.0` | Takeoff altitude (m), ignored with `--no-takeoff` |
| `--no-takeoff` | off | Set GUIDED + takeoff position without arming (hand-held testing) |
| `--distance` | `2.0` | Navigation distance per waypoint (m) |
| `--precision` | `0.2` | Arrival precision radius (m) |
| `--timeout` | `30.0` | Timeout per waypoint (s) |
| `--csv FILE` | none | Append per-leg results to a CSV (created if missing) |
| `--loop [N]` | none | Repeat selected tests N times; `--loop` with no value runs until Ctrl+C |

## Interactive Navigation

| Case | Command |
|------|---------|
| Outdoor, default PID | `python3 interactive_navigation.py --mode outdoor` |
| Direct MAVLink transport | `python3 interactive_navigation.py --drone mavlink --mode outdoor` |
| Outdoor, EKF, 3 m altitude | `python3 interactive_navigation.py --mode outdoor --strategy pid-ekf --altitude 3.0` |
| Hand-held (no arm/takeoff) | `python3 interactive_navigation.py --no-takeoff` |

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

## Obstacle Avoidance

```bash
python3 obstacles.py
```

Attaches a `DepthObstacleDetector` (RealSense D435i) with a pause strategy and runs an obstacle-aware `move_to`. Requires a connected depth camera; see [`control/obstacles/README.md`](../../control/obstacles/README.md) for detectors and strategies.

## Servo / PWM Test

Drives `MavrosDrone.do_servo` (`MAV_CMD_DO_SET_SERVO`, 183) from a REPL so you
can verify the correct AUX OUT channel and the PWM endpoints (e.g. hook hold /
release) on the bench. The script never arms the drone and never takes off —
keep props off.

**Defaults** — channel 3 (FCU ch 11 = AUX OUT 3), hold 1000 us, release 2000 us; MAVROS already running:

```bash
python3 servo_test.py
```

**Custom channel and presets**

```bash
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
