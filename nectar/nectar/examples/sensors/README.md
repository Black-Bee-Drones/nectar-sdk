# Sensors Module Examples

Bench-test the companion-computer sensor pipelines before wiring them into a mission.

| Script | What it does |
|--------|--------------|
| `rangefinder_example.py` | Bench-test the TF-Luna -> filter -> MAVLink `DISTANCE_SENSOR` pipeline (no ROS) |

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `/dev/ttyUSB0` | TF-Luna serial port |
| `--baud` | `115200` | TF-Luna baud |
| `--mavlink` | `udp:127.0.0.1:14551` | MAVLink connection string (UDP/TCP/serial) |
| `--mavlink-baud` | `921600` | Serial baud for MAVLink endpoints (ignored for UDP/TCP) |
| `--filter` | `none` | `none` or `obstacle_mask` |
| `--obstacle-height` | `0.0` | Obstacle height (m); `<= 0` auto-estimates |
| `--max-change` | `0.30` | Obstacle-mask step-change threshold (m) |
| `--avg-window` | `10` | Obstacle-mask averaging window (samples) |
| `--estimate-lock-s` | `0.2` | Time to lock the auto-estimated height (s) |
| `--timeout-s` | `5.0` | Sensor read timeout (s) |
| `--rate` | `50.0` | Publish rate (Hz) |
| `--duration` | `0.0` | Run time (s); `0` = until Ctrl-C |

## Bench test

```bash
# Raw passthrough; runs until Ctrl-C.
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551

# Hook mission and similar: auto-detect the obstacle height. No prior knowledge needed.
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551 \
    --filter obstacle_mask \
    --duration 60

# Fixed-height override (SITL, known fixtures): lock to 1.7 m.
python3 rangefinder_example.py \
    --port /dev/ttyUSB0 \
    --mavlink udp:127.0.0.1:14551 \
    --filter obstacle_mask \
    --obstacle-height 1.7 \
    --duration 60
```

While the script is running, in another terminal echo the FCU rangefinder
topic to confirm the masked stream is reaching the EKF via MAVROS:

```bash
ros2 topic echo /mavros/rangefinder/rangefinder
```

Drop a known-height object under the sensor; the topic value should jump
by roughly the object's height and recover when removed.

For ROS deployments use the `rangefinder_node.py` entry point instead:

```bash
ros2 run nectar rangefinder_node.py --ros-args \
    -p serial_port:=/dev/ttyUSB0 \
    -p mavlink_url:=udp:127.0.0.1:14551 \
    -p filter:=obstacle_mask
```

See [`nectar/sensors/README.md`](../../sensors/README.md) for the full
parameter list, ArduPilot configuration steps, and troubleshooting.
