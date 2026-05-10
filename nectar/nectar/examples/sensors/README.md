# Sensors Module Examples

| File | Description | Args |
|------|-------------|------|
| `rangefinder_example.py` | Bench-test the TF-Luna -> filter -> MAVLink `DISTANCE_SENSOR` pipeline (no ROS) | `--port --mavlink --filter --obstacle-height --estimate-lock-s --rate --duration` |

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
