# Indoor vision flight — command card

Prerequisite: same `ROS_DOMAIN_ID` on Jetson and companion (default `14`). FCU must already be set for ExternalNav (ArduPilot: `VISO_TYPE=1`, `EK3_SRC1_POSXY/POSZ/YAW=6`, `GPS1_TYPE=0`).

---

## Terminal 1 — Jetson (producer)

```bash
isaac
nectar-vslam
```

Publishes `/visual_slam/tracking/vo_pose_covariance` (~90 Hz) and `/visual_slam/tracking/odometry` (derived twist).

For RViz **full** profile landmarks (laptop), start with visualization on:

```bash
nectar-vslam enable_visualization:=true
```

---

## Terminal 2 — companion (consumer)

### Pose only (default — use this first)

| How you fly | Command |
|---|---|
| MAVROS (ArduPilot) | `./setup.sh driver mavros --env indoor` |
| MAVROS (PX4) | `./setup.sh driver px4 --env indoor` |
| Direct MAVLink **mission** (`PoseSource.VISION`) | no bridge — mission starts the pose feeder |
| Direct MAVLink **bridge only** (RC / no mission feeder) | `./setup.sh driver mavlink --env indoor` |
| PX4 DDS | `./setup.sh driver px4-dds --env indoor` then, another terminal: `ros2 launch nectar vision_pose.launch.py backend:=dds` |

Equivalent explicit launches (override serial if needed):

```bash
ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600
ros2 launch nectar vision_pose.launch.py backend:=mavlink mavlink_url:=udp:127.0.0.1:14551
ros2 launch nectar vision_pose.launch.py backend:=dds
```

### Pose + speed

Same commands, add `send_speed:=true`:

```bash
ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600 send_speed:=true
ros2 launch nectar vision_pose.launch.py backend:=mavlink mavlink_url:=udp:127.0.0.1:14551 send_speed:=true
ros2 launch nectar vision_pose.launch.py backend:=dds send_speed:=true
```

Or via driver:

```bash
./setup.sh driver mavros --env indoor send_speed:=true
./setup.sh driver mavlink --env indoor send_speed:=true
```

FCU for speed (only if `send_speed:=true`): ArduPilot `EK3_SRC1_VELXY/VELZ=6`; PX4 `EKF2_EV_CTRL` with velocity bit. Leave speed **off** unless Loiter improves.

---

## Terminal 3 — mission (optional)

```bash
python3 nectar/nectar/examples/control/basic.py --drone mavros --env indoor
# or mavlink / px4 / px4_mavlink / px4_dds with PoseSource.VISION
```

**One feeder:** do not run `driver … --env indoor` **and** a mavlink mission that also owns `VisionPoseBridge` on the same link.

---

## Check the pipeline

All machines must share `ROS_DOMAIN_ID`. Run these on the companion or laptop.

### Vision FCU check (recommended)

Terminal dashboard of **FCU fused** local pose (what the estimator is using), plus
optional ROS rates. `VISION_*` on the wire is best-effort — companion→FCU traffic
is usually not mirrored on a separate GCS telem link.

```bash
# Needs pymavlink (nectar-activate / workspace .venv)
nectar-activate

# Hardware GCS telem (typical)
ros2 run nectar vision_fcu_check.py --connection udp:0.0.0.0:14550 --ros

# ArduPilot SITL with MAVROS on SERIAL0 (5760): use SERIAL1 — one TCP client per port
ros2 run nectar vision_fcu_check.py --connection tcp:127.0.0.1:5762 --ros

# ArduPilot SITL when nothing else owns SERIAL0 (e.g. PROTOCOL=mavlink feeder on 5762)
ros2 run nectar vision_fcu_check.py --connection tcp:127.0.0.1:5760 --ros

# PX4 SITL
ros2 run nectar vision_fcu_check.py --connection udp:0.0.0.0:14540 --ros

# Smoke / CI: exit non-zero if fused pose is stale
ros2 run nectar vision_fcu_check.py --connection tcp:127.0.0.1:5762 --ros \
  --expect-hz 5 --duration 10
```

GUI equivalent: Mission Planner *Ctrl+F → MAVLink Inspector*, or QGroundControl
*Analyze Tools → MAVLink Inspector*.

### 1. Producer (always — VSLAM topics)

```bash
ros2 topic hz /visual_slam/tracking/vo_pose_covariance
ros2 topic echo /visual_slam/tracking/vo_pose_covariance --once
ros2 topic hz /visual_slam/tracking/odometry          # needed if send_speed:=true
```

Expect ~90 Hz pose. Move the drone by hand; position must change.

### 2. MAVROS backend

```bash
ros2 topic hz /mavros/vision_pose/pose_cov
ros2 topic echo /mavros/vision_pose/pose_cov --once
ros2 topic hz /mavros/vision_speed/speed_twist        # only with send_speed:=true
ros2 topic echo /mavros/local_position/pose --once --qos-reliability best_effort
```

Or use `vision_fcu_check.py --ros` (above) for rates + fused FCU pose together.

### 3. Direct MAVLink backend

There is no ROS republish of what went on the wire. Check upstream ROS (section 1),
then run `vision_fcu_check.py` on the **GCS/telem** endpoint and confirm fused
`LOCAL_POSITION_NED` updates when you move the airframe. Do not attach the check
to a serial/UDP link already owned by a mission `PymavlinkTransport`.

### 4. DDS backend (PX4)

```bash
ros2 topic hz /fmu/in/vehicle_visual_odometry
ros2 topic echo /fmu/in/vehicle_visual_odometry --once --qos-reliability best_effort
ros2 run nectar vision_fcu_check.py --connection udp:0.0.0.0:14540 --ros
```

---

## Laptop — RViz (optional)

Same `ROS_DOMAIN_ID` as the Jetson. Prefer the laptop, not the Jetson.

```bash
# light: TF + odometry + SLAM path (green) + VO path (purple), rolling 15 s
ros2 launch nectar vslam_rviz.launch.py profile:=light

# longer path buffer
ros2 launch nectar vslam_rviz.launch.py profile:=light window_seconds:=30

# full path history
ros2 launch nectar vslam_rviz.launch.py profile:=light window_seconds:=0

# full: + landmarks / loop-closure clouds (needs nectar-vslam enable_visualization:=true)
ros2 launch nectar vslam_rviz.launch.py profile:=full
```

Hand-move the drone: green SLAM path should track; on loop closure it snaps relative to the purple VO path.
