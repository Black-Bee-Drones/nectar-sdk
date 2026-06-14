# Simulation Module

ArduPilot SITL + Gazebo Harmonic simulation for Nectar drone development and testing, over either transport (MAVROS or direct MAVLink).

## How It Works

ArduPilot [SITL](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html) runs the full ArduCopter firmware on the host machine. [Gazebo Harmonic](https://gazebosim.org/docs/harmonic) provides physics and sensor simulation. The [ArduPilotPlugin](https://github.com/ArduPilot/ardupilot_gazebo) bridges Gazebo physics to SITL via JSON over UDP (port 9002). SITL exposes two MAVLink endpoints: TCP `5760` (SERIAL0, for [MAVROS](https://github.com/mavlink/mavros)) and TCP `5762` (SERIAL1, for a direct pymavlink client / `MavlinkDrone`) — so both transports can run against the same simulator. The [ros_gz_bridge](https://github.com/ros-gz/ros_gz) converts Gazebo sensor data to ROS 2 messages.

```mermaid
flowchart LR
    subgraph sitl [ArduPilot SITL]
        ArduCopter["arducopter binary"]
    end

    subgraph gazebo [Gazebo Harmonic]
        Physics["Physics + Sensors"]
        ArduPlugin["ArduPilotPlugin"]
        GUI["GUI: 3D + ImageDisplay + TopicEcho"]
    end

    subgraph bridge [ros_gz_bridge]
        SensorBridge["Cameras + Lidar"]
        PoseBridge["Pose bridge (indoor)"]
    end

    subgraph ros2 [ROS 2]
        MAVROS["MAVROS"]
        VisionSource["gz_vision_source (indoor)"]
        VisionNode["vision_pose_node (mavros)"]
        SDK["Nectar SDK / MavrosDrone | MavlinkDrone"]
    end

    ArduPlugin -->|"JSON UDP:9002"| ArduCopter
    ArduCopter -->|"TCP:5760 (MAVROS)"| MAVROS
    ArduCopter -->|"TCP:5762 (direct MAVLink)"| SDK
    Physics --> SensorBridge
    SensorBridge --> SDK
    PoseBridge --> VisionSource
    VisionSource -->|"/visual_slam/tracking/vo_pose_covariance"| VisionNode
    VisionSource -->|"/visual_slam/tracking/vo_pose_covariance"| SDK
    VisionNode -->|"/mavros/vision_pose/pose_cov"| MAVROS
    MAVROS --> SDK
```

## Two Environments

### Outdoor (GPS)

- World: `outdoor_field.sdf` -- open field with obstacle zone at x=13..18, fly-through gate
- GPS via `gz-sim-navsat-system` plugin with WGS84 coordinates (Canberra default)
- ArduPilot params: `copter.parm` + `gazebo.parm` (rangefinder enabled)
- Config preset: `SITL_GAZEBO_CONFIG` (PoseSource.GPS)

### Indoor (Vision)

- World: `indoor_room.sdf` -- 20x20x12m enclosed room, drone at x=-5, obstacle zone at x=5..9, gate
- No GPS. EKF3 uses ExternalNav (vision) for position
- `gz_vision_source.py` publishes Gazebo ground-truth pose on the canonical VSLAM topic `/visual_slam/tracking/vo_pose_covariance`; `vision_pose_node` (mavros) relays it to `/mavros/vision_pose/pose_cov`, or `MavlinkDrone` consumes it directly (mavlink) -- the same bridges as real hardware
- ArduPilot params: `copter.parm` + `gazebo.parm` + `indoor.parm` (GPS disabled, EKF3 ExternalNav)
- Config preset: `SITL_VISION_CONFIG` (PoseSource.VISION)

## Simulated Sensors

| Real sensor | Gazebo sensor | Topic (ROS 2) | Notes |
|---|---|---|---|
| RealSense D435i (front) | `rgbd_camera` | `/front_camera/image`, `/front_camera/depth_image`, `/front_camera/points` | 640x480, RGB + depth + point cloud |
| Arducam (down) | `camera` | `/down_camera` | 640x480 RGB, downward-facing |
| TFLuna lidar (down) | SITL simulated sonar | `/mavros/rangefinder_pub` | `RNGFND1_TYPE=1`, ground distance from physics |
| TFLuna lidar (down) | `gpu_lidar` | `/lidar/range` | Direct LaserScan via Gazebo, 1-sample rangefinder |

The rangefinder has two data paths: SITL sonar (via MAVLink `DISTANCE_SENSOR` to MAVROS) and Gazebo `gpu_lidar` (via `ros_gz_bridge`). Same as real hardware where the lidar feeds both ArduPilot and ROS directly.

## Gazebo GUI

Both world SDFs include built-in GUI plugins (no extra windows needed):

- **ImageDisplay** panels for front RGB, front depth, and down camera (start collapsed, click to expand)
- **TopicEcho** for viewing any Gazebo transport topic live
- **WorldStats** showing sim time, real time, RTF

## Installation

```bash
# ArduPilot SITL (clones ~/ardupilot, builds ArduCopter)
make sim-install

# Gazebo Harmonic + ArduPilotPlugin + ros_gz_bridge from source
make sim-install-gazebo

source ~/.bashrc
```

## Usage

Two terminals: **Terminal 1** runs the SITL physics, **Terminal 2** runs the
Gazebo world + ROS stack. Use the matched pair for your scenario. The SITL
parameters must match the world (indoor = no GPS), so always pair the same row.

| Scenario | Terminal 1 (physics) | Terminal 2 (world + ROS) | Drone in your mission |
|---|---|---|---|
| Outdoor, MAVROS | `make sim-start-outdoor` | `make sim-outdoor` | `MavrosDrone` / `SITL_GAZEBO_CONFIG` |
| Outdoor, direct MAVLink | `make sim-start-outdoor` | `make sim-outdoor-direct` | `MavlinkDrone` / `MAVLINK_SITL_GAZEBO_CONFIG` |
| Indoor, MAVROS | `make sim-start-indoor` | `make sim-indoor` | `MavrosDrone` / `SITL_VISION_CONFIG` |
| Indoor, direct MAVLink | `make sim-start-indoor` | `make sim-indoor-direct` | `MavlinkDrone` / `MAVLINK_SITL_VISION_CONFIG` |

- **MAVROS** targets start MAVROS on SERIAL0 (tcp `5760`). **direct MAVLink**
  targets pass `mavros:=false` (no MAVROS); connect a `MavlinkDrone` on SERIAL1
  (tcp `5762`), which `start_sitl.sh` always exposes.
- **Indoor** targets add the vision pipeline: `gz_vision_source` publishes the
  canonical VSLAM topic; with MAVROS, `vision_pose_node` relays it to
  `/mavros/vision_pose/pose_cov`; with direct MAVLink, `MavlinkDrone`'s
  `VisionPoseBridge` consumes it. Same bridges as real hardware.

> Always run `make sim-stop` before relaunching Terminal 2. `ros2 launch` on
> Ctrl+C can leave a stray Python node alive (e.g. a duplicate
> `/gz_vision_source`); `sim-stop` clears them.

### Headless (no Gazebo)

```bash
# Terminal 1: SITL with internal physics
make sim-start

# Terminal 2: MAVROS only
make sim-mavros
```

### Stop all

```bash
make sim-stop
```

Kills arducopter, Gazebo, MAVROS, ros_gz_bridge, gz_vision_source, and vision_pose_node processes.

### Verify sensors

```bash
# State
ros2 topic echo /mavros/state --once

# GPS (outdoor)
ros2 topic echo /mavros/global_position/global --once --qos-reliability best_effort

# Vision pose (indoor)
ros2 topic echo /mavros/vision_pose/pose_cov --once

# Rangefinder
ros2 topic echo /mavros/rangefinder_pub --once

# Front camera
ros2 topic echo /front_camera/image --once

# Depth
ros2 topic echo /front_camera/depth_image --once
```

### Multi-orientation rangefinders

`rangefinder_test.sdf` places an iris with front and back single-ray lidars
between two walls. The `iris_with_rangefinders` model forwards the front/back
lidars to ArduPilot as `rng_2/rng_3`, and `rangefinder_test.parm` exposes them
as `RNGFND2/3` (orientations forward/back). The downward rangefinder
(`RNGFND1`, orientation down) stays on the analog SITL sonar from `gazebo.parm`:
on the ground the airframe is only ~0.2 m tall, so a downward GPU lidar reads
below its minimum range, while the sonar reports vehicle height above terrain
reliably. ArduPilot emits one `DISTANCE_SENSOR` per instance, accessible through
`drone.distance_sensors` and `drone.get_distance(orientation)`.

```bash
# Terminal 1: SITL with the three rangefinders
./scripts/simulation/start_sitl.sh --gazebo \
    --params nectar/simulation/params/rangefinder_test.parm

# Terminal 2: Gazebo (and MAVROS) with the test world
ros2 launch nectar sitl_gazebo.launch.py world:=rangefinder_test.sdf

# Terminal 3: read the readings
python3 nectar/nectar/examples/simulation/read_distance_sensors.py            # direct MAVLink
python3 nectar/nectar/examples/simulation/read_distance_sensors.py --mavros   # MAVROS
```

The MAVROS path relies on the `distance_sensor` plugin entries in
`config/apm_config_sitl.yaml` (`rangefinder/rangefinder`, `rangefinder/front`,
`rangefinder/back`) mapped to orientations in the example via `DistanceSensorTopic`.

## Configuration Presets

Defined in `nectar/control/config.py`:

| Preset | Transport | Port | PoseSource | Lidar | Use case |
|---|---|---|---|---|---|
| `SITL_CONFIG` | mavros | 5760 | GPS | No | Headless SITL, no sensors |
| `SITL_GPS_CONFIG` | mavros | 5760 | GPS | No | Headless SITL with GPS |
| `SITL_GAZEBO_CONFIG` | mavros | 5760 | GPS | Yes | Gazebo outdoor |
| `SITL_VISION_CONFIG` | mavros | 5760 | VISION | Yes | Gazebo indoor |
| `MAVLINK_SITL_CONFIG` | mavlink | 5760 | GPS | No | Headless SITL, direct pymavlink |
| `MAVLINK_SITL_GAZEBO_CONFIG` | mavlink | 5762 | GPS | No | Gazebo outdoor, direct (SERIAL1, alongside MAVROS) |
| `MAVLINK_SITL_VISION_CONFIG` | mavlink | 5762 | VISION | No | Gazebo indoor, direct (reuses the MAVROS vision relay topic) |

```python
from nectar.control import DroneFactory, SITL_GAZEBO_CONFIG, MAVLINK_SITL_GAZEBO_CONFIG

# Outdoor over MAVROS (port 5760)
drone = DroneFactory.create("mavros", SITL_GAZEBO_CONFIG, node)

# Outdoor over direct MAVLink (port 5762, with `make sim-outdoor-direct`)
drone = DroneFactory.create("mavlink", MAVLINK_SITL_GAZEBO_CONFIG, node)
```

## Test Suite

`sitl_test.py` runs atomic navigation tests. Each test starts from a clean hover and verifies a specific capability.

### Usage

```bash
# All outdoor tests (31 tests)
python3 nectar/nectar/examples/simulation/sitl_test.py

# All indoor-compatible tests (skips GPS-only tests)
python3 nectar/nectar/examples/simulation/sitl_test.py --indoor

# Specific tests
python3 nectar/nectar/examples/simulation/sitl_test.py pid_fwd setpoint_fwd

# Test group
python3 nectar/nectar/examples/simulation/sitl_test.py --group vel

# List all tests and groups
python3 nectar/nectar/examples/simulation/sitl_test.py --list
```

### Test categories

| Group | Tests | Description |
|---|---|---|
| `vel` | vel_fwd, vel_lat, vel_up, vel_yaw, vel_takeoff, vel_world, brake | Velocity commands in BODY/WORLD/TAKEOFF frames |
| `pid` | pid_fwd, pid_lat, pid_alt, pid_yaw | PID navigation with raw GPS |
| `pid_local` | pid_local_fwd, pid_local_lat, pid_local_yaw | PID navigation with EKF local position |
| `setpoint` | setpoint_fwd, setpoint_lat, setpoint_yaw | Local position setpoint publishing |
| `setpoint_global` | setpoint_global, setpoint_global_yaw | GPS global setpoint (outdoor only) |
| `rtl` | rtl_pid, rtl_ardupilot | Return to launch |
| `square` | sq_pid, sq_pid_takeoff, sq_pid_local, sq_setpoint, sq_setpoint_global, sq_wpnav | 3m square patterns |

GPS-only tests (skipped with `--indoor`): `heading_enu`, `setpoint_global`, `setpoint_global_yaw`, `sq_setpoint_global`, `rtl_ardupilot`.

## ArduPilot Parameters

### gazebo.parm (loaded for all Gazebo sessions)

| Parameter | Value | Purpose |
|---|---|---|
| `SIM_SONAR_SCALE` | 10 | SITL sonar scaling factor |
| `RNGFND1_TYPE` | 1 | Analog rangefinder driven by SIM_SONAR |
| `RNGFND1_SCALING` | 10 | Voltage-to-distance scaling |
| `RNGFND1_PIN` | 0 | Analog pin |
| `RNGFND1_MAX` | 40 | Max range (m) |
| `RNGFND1_MIN` | 0.10 | Min range (m) |

### indoor.parm (loaded additionally for indoor)

| Parameter | Value | Purpose |
|---|---|---|
| `GPS1_TYPE` | 0 | Disable GPS |
| `EK3_SRC1_POSXY` | 6 | ExternalNav for XY position |
| `EK3_SRC1_VELXY` | 6 | ExternalNav for XY velocity |
| `EK3_SRC1_POSZ` | 1 | Barometer for Z (default) |
| `EK3_SRC1_YAW` | 6 | ExternalNav for yaw |
| `VISO_TYPE` | 1 | Enable visual odometry input |
| `ARMING_CHECK` | 388598 | Disable GPS-related arming checks |

## Indoor Vision Pose Pipeline

```mermaid
flowchart LR
    GzPose["Gazebo PosePublisher<br/>/world/indoor_room/dynamic_pose/info<br/>gz.msgs.Pose_V"]
    Bridge["ros_gz_bridge<br/>gz.msgs.Pose_V → tf2_msgs/TFMessage"]
    VPB["gz_vision_source.py<br/>Selects iris model pose"]
    Topic["/visual_slam/tracking/vo_pose_covariance<br/>(canonical VSLAM topic)"]
    VPN["vision_pose_node (mavros)<br/>or MavlinkDrone VisionPoseBridge"]
    FCU["ArduPilot EKF3<br/>ExternalNav fusion"]

    GzPose --> Bridge --> VPB --> Topic --> VPN --> FCU
```

The `gz_vision_source.py` node replaces the real RealSense D435i + Isaac ROS VSLAM pipeline. It selects the `iris` model pose from the Gazebo ground-truth `TFMessage` and publishes `PoseWithCovarianceStamped` on the same canonical topic Isaac ROS Visual SLAM uses, `/visual_slam/tracking/vo_pose_covariance`. The downstream delivery is then identical to real hardware: `vision_pose_node` (backend `mavros`) relays it to `/mavros/vision_pose/pose_cov`, or `MavlinkDrone`'s `VisionPoseBridge` (backend `mavlink`) forwards it as `VISION_POSITION_ESTIMATE`.

**Frame-name fallback**: it first matches the transform whose `child_frame_id` equals the model name. On ROS 2 Jazzy the `ros_gz_bridge` `Pose_V → TFMessage` conversion strips the frame ids, leaving `child_frame_id` empty. When all names are empty the node falls back to the transform at `model_index` (default `0`, the iris model root) and logs a one-time warning, so the indoor pipeline publishes reliably on Jazzy.

## File Structure

```
simulation/
├── README.md                 # This file
├── params/
│   ├── gazebo.parm           # Rangefinder params (all Gazebo sessions)
│   ├── indoor.parm           # No-GPS + EKF3 ExternalNav params
│   └── rangefinder_test.parm # RNGFND2/3 front/back for the test world (down stays analog)
├── models/
│   └── iris_with_rangefinders/  # iris + ArduPilotPlugin + down/front/back lidar
└── worlds/
    ├── outdoor_field.sdf     # Open field + obstacles + GPS
    ├── indoor_room.sdf       # 20x20x12m room + obstacles + no GPS
    └── rangefinder_test.sdf  # iris between two walls for distance-sensor checks

scripts/simulation/
├── install_sitl.sh           # Clone and build ArduPilot SITL
├── install_gazebo.sh         # Install Gazebo + ArduPilotPlugin + ros_gz from source
├── start_sitl.sh             # Start arducopter binary (--gazebo, --indoor flags)
└── gz_vision_source.py       # Gazebo ground-truth → canonical VSLAM pose topic

nectar/launch/
├── sitl.launch.py            # MAVROS-only launch (headless SITL)
└── sitl_gazebo.launch.py     # Gazebo + ros_gz_bridge (+ MAVROS unless mavros:=false)

nectar/nectar/examples/simulation/
├── sitl_test.py                # Navigation test suite (--indoor flag)
└── read_distance_sensors.py    # Print distance_sensors map (MAVLink / MAVROS)
```

## References

- [ArduPilot SITL](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html)
- [ArduPilot SITL with Gazebo](https://ardupilot.org/dev/docs/sitl-with-gazebo.html)
- [ardupilot_gazebo plugin](https://github.com/ArduPilot/ardupilot_gazebo)
- [Gazebo Harmonic](https://gazebosim.org/docs/harmonic)
- [Gazebo sensors](https://gazebosim.org/api/sensors)
- [ros_gz_bridge](https://github.com/ros-gz/ros_gz)
- [MAVROS](https://github.com/mavlink/mavros)
- [ArduPilot EKF3](https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html)
- [ArduPilot VIO setup](https://ardupilot.org/copter/docs/common-vio-tracking-camera.html)
- [ArduPilot rangefinders](https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html)
