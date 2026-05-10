# Sensors Module

Companion-side sensor drivers and value filters, plus a ready-made ROS2 node that bridges a serial rangefinder to MAVLink `DISTANCE_SENSOR` so an ArduPilot/PX4 FCU can consume it as its primary rangefinder.

The module is composition-first: a `DistanceSensor` (driver) and an optional `DistanceFilter` are wired into a `RangefinderPublisher` that pushes filtered samples into a `MavlinkConnection`. Each piece is independently usable.

## Why this exists

When a downward-facing LiDAR is the EKF altitude source (`EK3_SRC1_POSZ = Rangefinder`), flying over a fixed obstacle (e.g. a sphere on a hose) causes a step drop in the rangefinder reading that ArduPilot interprets as the vehicle descending. The position controller climbs to compensate, lifting the drone above its target altitude. Connecting the LiDAR to the companion computer instead of the FCU lets us mask those step drops before the EKF ever sees them.

ArduPilot has no native parameter to reject step changes in the rangefinder — the filter must live upstream of the FCU. See [ArduPilot terrain following docs](https://ardupilot.org/copter/docs/terrain-following.html) and [`AP_RangeFinder_Benewake_CAN.h`](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_RangeFinder/AP_RangeFinder_Benewake_CAN.h).

## Architecture

```mermaid
classDiagram
    class DistanceSensor {
        <<protocol>>
        +read() Optional~float~
        +close()
    }

    class DistanceFilter {
        <<protocol>>
        +process(raw) Optional~float~
        +reset()
    }

    class TFLuna {
        -_ser Serial
        -_buffer bytearray
        -_min_strength int
        +read() Optional~float~
        +close()
        -_parse_one_frame() Optional~float~
    }

    class ObstacleMaskFilter {
        -_obstacle_height_m float
        -_max_change_m float
        -_timeout_s Optional~float~
        -_window deque
        -_over_obstacle bool
        -_entry_raw Optional~float~
        -_entry_time Optional~float~
        +is_masking bool
        +process(raw) Optional~float~
        +reset()
    }

    class RangefinderPublisher {
        -_sensor DistanceSensor
        -_connection MavlinkConnection
        -_filter Optional~DistanceFilter~
        -_sensor_id int
        -_sensor_type int
        -_orientation int
        -_min_cm int
        -_max_cm int
        -_covariance int
        -_period float
        -_stop_event Event
        -_thread Optional~Thread~
        +is_running bool
        +start()
        +stop(timeout)
        -_loop()
        -_send(distance_m)
    }

    class MavlinkConnection {
        -_source_system int
        -_source_component int
        -_heartbeat_timeout float
        +master Optional~mavfile~
        +is_connected bool
        +connect(device, baud)
        +close()
        -_await_heartbeat()
    }

    class RangefinderNode {
        -_sensor TFLuna
        -_connection MavlinkConnection
        -_publisher RangefinderPublisher
        +__init__()
        +destroy_node()
        -_build_pipeline()
        -_build_filter()
    }

    DistanceSensor <|.. TFLuna
    DistanceFilter <|.. ObstacleMaskFilter
    RangefinderPublisher o-- DistanceSensor
    RangefinderPublisher o-- DistanceFilter
    RangefinderPublisher o-- MavlinkConnection
    RangefinderNode *-- RangefinderPublisher
```

## Data flow

```mermaid
flowchart LR
    HW["TF-Luna UART"] --> TFLuna
    TFLuna -->|"raw m"| Filter["ObstacleMaskFilter (optional)"]
    Filter -->|"masked m"| Pub["RangefinderPublisher"]
    Pub -->|"DISTANCE_SENSOR (132)"| Conn["MavlinkConnection"]
    Conn -->|"MAVLink UDP/Serial"| FCU["Pixhawk RNGFND1_TYPE=10"]
    FCU -->|"EKF Z fusion"| Ctrl["AC_PosControl"]
    FCU -->|"RANGEFINDER (173)"| MAVROS
    MAVROS -->|"/mavros/rangefinder/rangefinder"| Mission["MavrosDrone + missions (unchanged)"]
```

## Components

### `DistanceSensor` and `DistanceFilter` (Protocols)

Lightweight structural interfaces in [`base.py`](base.py). Implementations only need to match the shape; no inheritance is required (matches the `Drone` and `ObstacleDetector` convention in `nectar/control`).

```python
class DistanceSensor(Protocol):
    def read(self) -> Optional[float]: ...
    def close(self) -> None: ...

class DistanceFilter(Protocol):
    def process(self, raw_distance: float) -> Optional[float]: ...
    def reset(self) -> None: ...
```

### `TFLuna`

Benewake TF-Luna serial driver in [`benewake/tfluna.py`](benewake/tfluna.py). Parses the standard 9-byte UART frame (`0x59 0x59 ...`), validates checksum and signal strength, and returns the latest valid reading on each `read()`. Non-blocking: small serial timeout, drains `in_waiting` per call, returns `None` when no fresh frame is ready.

```python
from nectar.sensors import TFLuna

sensor = TFLuna(port="/dev/ttyUSB0", baudrate=115200)
distance_m = sensor.read()  # float | None
sensor.close()
```

Hardware reference: [TF-Luna product page](https://en.benewake.com/TFLuna/index.html).

### `ObstacleMaskFilter`

Stateful rangefinder filter in [`filters/obstacle_mask.py`](filters/obstacle_mask.py). Detects a sudden drop, masks readings for the duration of the obstacle, recovers when the reading returns to the pre-entry baseline.

Algorithm:
- Maintain a rolling average over the last `avg_window` readings while not masking.
- Enter the masked state when `raw < baseline - max_change_m`. Save `entry_raw`.
- While masking, return `raw + obstacle_height_m`.
- Exit when `raw > entry_raw + max_change_m`, or after `timeout_s` (safety reset).

```python
from nectar.sensors import ObstacleMaskFilter

f = ObstacleMaskFilter(
    obstacle_height_m=1.7,   # known obstacle thickness (e.g. SAE 2026 sphere)
    max_change_m=0.30,       # entry/exit hysteresis
    avg_window=10,           # samples for the entry baseline
    timeout_s=5.0,           # force-reset if stuck masked too long
)

filtered = f.process(raw)    # float (current sample masked or passed through)
f.reset()                    # clear all state (e.g. on mode change)
```

### `RangefinderPublisher`

Composition piece in [`rangefinder_publisher.py`](rangefinder_publisher.py). Owns a background thread that reads the sensor at a configurable rate, applies the optional filter, and sends MAVLink `DISTANCE_SENSOR` (id 132) over the connection.

```python
from nectar.control import MavlinkConnection
from nectar.sensors import (
    ObstacleMaskFilter,
    RangefinderPublisher,
    TFLuna,
)
from pymavlink import mavutil

sensor = TFLuna(port="/dev/ttyUSB0")
conn = MavlinkConnection()
conn.connect("udp:127.0.0.1:14551")

publisher = RangefinderPublisher(
    sensor=sensor,
    connection=conn,
    sensor_id=0,
    sensor_type=mavutil.mavlink.MAV_DISTANCE_SENSOR_LASER,
    orientation=mavutil.mavlink.MAV_SENSOR_ROTATION_PITCH_270,  # downward
    min_distance_m=0.05,
    max_distance_m=8.0,
    rate_hz=50.0,
    filter=ObstacleMaskFilter(obstacle_height_m=1.7),
)

publisher.start()
# ... mission runs ...
publisher.stop()
sensor.close()
conn.close()
```

`filter=None` publishes raw readings.

### `RangefinderNode`

ROS2 entry point in [`nodes/rangefinder_node.py`](nodes/rangefinder_node.py). Declares every knob as a ROS parameter so per-mission tuning lives in the launch file rather than in mission code.

```bash
# Raw passthrough (no filter)
ros2 run nectar rangefinder_node.py --ros-args \
    -p serial_port:=/dev/ttyUSB0 \
    -p mavlink_url:=udp:127.0.0.1:14551

# Hook mission: mask the 1.7m sphere
ros2 run nectar rangefinder_node.py --ros-args \
    -p serial_port:=/dev/ttyUSB0 \
    -p mavlink_url:=udp:127.0.0.1:14551 \
    -p filter:=obstacle_mask \
    -p obstacle_height_m:=1.7 \
    -p max_change_m:=0.30 \
    -p avg_window:=10 \
    -p timeout_s:=5.0
```

#### Parameters

- `serial_port` (string, default `/dev/ttyUSB0`) — TF-Luna device path.
- `baudrate` (int, default `115200`) — TF-Luna baud rate.
- `mavlink_url` (string, default `udp:127.0.0.1:14551`) — pymavlink endpoint to the FCU. Use a UDP fan-out (e.g. mavlink-router) if MAVROS already owns the FCU's serial line.
- `mavlink_baud` (int, default `921600`) — Used only for serial endpoints.
- `source_system` (int, default `1`) — MAVLink system ID this companion presents.
- `source_component` (int, default `191`) — `MAV_COMP_ID_ONBOARD_COMPUTER`.
- `heartbeat_timeout_s` (float, default `30.0`) — Max wait for the first FCU heartbeat.
- `sensor_id` (int 0-7, default `0`) — Maps to ArduPilot `RNGFND<id+1>_*` slot.
- `orientation` (int, default `25`) — `MAV_SENSOR_ORIENTATION` enum (`25` = `PITCH_270`, downward).
- `min_distance_m` / `max_distance_m` (float, default `0.05` / `8.0`) — Sensor range, sent as part of `DISTANCE_SENSOR`.
- `covariance_cm` (int 0-254, default `0`) — `0` means "use FCU defaults".
- `rate_hz` (float, default `50.0`) — Publish rate.
- `filter` (string, default `none`) — `none` or `obstacle_mask`.
- `obstacle_height_m`, `max_change_m`, `avg_window`, `timeout_s` — Forwarded to `ObstacleMaskFilter` when `filter=obstacle_mask`. Use `timeout_s <= 0` to disable the safety reset.

## ArduPilot setup (one-time)

Set on the FCU via Mission Planner / parameter editor:

- `RNGFND1_TYPE = 10` (MAVLink)
- `RNGFND1_MIN_CM = 20`, `RNGFND1_MAX_CM = 800` ([TF-Luna](https://en.benewake.com/TFLuna/index.html) effective range)
- `RNGFND1_ORIENT = 25` (Down)
- Physically disconnect the TF-Luna's UART from the Pixhawk so the only rangefinder source is the filtered MAVLink stream.
- Keep `EK3_SRC1_POSZ = Rangefinder` and `EK3_RNG_USE_HGT = -1` if that is your current configuration; the masking filter is what makes that combination safe across known obstacles.

The Jetson and MAVROS both need access to the FCU MAVLink stream. The standard pattern is to run [mavlink-router](https://github.com/mavlink-router/mavlink-router) (or equivalent) on the Jetson to fan out the FCU's serial link to both MAVROS and this node's UDP endpoint.

## DISTANCE_SENSOR vs RANGEFINDER

These are two different MAVLink messages with opposite directions:

- [`DISTANCE_SENSOR` (id 132)](https://mavlink.io/en/messages/common.html#DISTANCE_SENSOR): companion-to-FCU. What this node sends. Carries sensor metadata (id, type, orientation, min/max).
- [`RANGEFINDER` (id 173, ardupilotmega)](https://github.com/mavlink/c_library_v1/blob/master/ardupilotmega/mavlink_msg_rangefinder.h): FCU-to-GCS telemetry. What MAVROS reads to publish `/mavros/rangefinder/rangefinder`.

This node only emits `DISTANCE_SENSOR`. The `RANGEFINDER` flow is handled by ArduPilot and MAVROS without any code from this module.

## Validation

Bench (no flight):

```bash
ros2 run nectar rangefinder_node.py --ros-args -p mavlink_url:=udp:127.0.0.1:14551
ros2 topic echo /mavros/rangefinder/rangefinder
```

Drop a known-height object under the sensor while echoing the topic. The reading should jump by the masked offset and recover when the object is removed.

Standalone (no ROS): see [`examples/sensors/rangefinder_example.py`](../examples/sensors/rangefinder_example.py).

## Troubleshooting

- **`No FCU heartbeat received within 30s`**: pymavlink can't reach the FCU. Check `mavlink_url`, that mavlink-router is running, and that the UDP port matches. Verify with `mavproxy.py --master=udp:127.0.0.1:14551`.
- **MAVROS still shows the raw reading**: confirm `RNGFND1_TYPE = 10` on the FCU and that the direct UART is physically disconnected. The FCU prefers the directly wired sensor when both are present.
- **Filter masks during a legitimate descent**: `max_change_m` is too tight. Increase it, or shrink `avg_window` so the baseline tracks the descent faster.
- **Stuck masked**: lower `timeout_s` (default 5.0s) or set it to a value just larger than the longest obstacle traversal expected for the mission.
- **TF-Luna returns `None` constantly**: check baud (default 115200), wiring, and that no other process is holding the serial port. Increase `min_strength` if you suspect the sensor is reading through low-confidence reflections.

## References

- [Benewake TF-Luna product page](https://en.benewake.com/TFLuna/index.html)
- [ArduPilot rangefinder landing page](https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html)
- [ArduPilot terrain following](https://ardupilot.org/copter/docs/terrain-following.html)
- [ArduPilot Benewake setup](https://ardupilot.org/copter/docs/common-benewake-tf02-lidar.html)
- [`AP_RangeFinder.h`](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_RangeFinder/AP_RangeFinder.h)
- [`DISTANCE_SENSOR` MAVLink message](https://mavlink.io/en/messages/common.html#DISTANCE_SENSOR)
- [pymavlink documentation](https://mavlink.io/en/mavgen_python/)
