# MAVROS Control Module

ArduPilot/PX4 drone control via MAVROS for ROS2.

## Key Concepts

### MAVLink and MAVROS

[MAVLink](https://ardupilot.org/dev/docs/mavlink-basics.html) is a lightweight binary protocol used for communication between the flight controller (FCU), ground stations, and companion computers. [MAVROS](https://github.com/mavlink/mavros) is a ROS2 node that bridges MAVLink and ROS2, exposing FCU data as topics/services and translating ROS2 commands into MAVLink messages.

This SDK uses MAVROS to send velocity/position commands and read sensor data. The drone must be in [GUIDED mode](https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html) for offboard control.

### Flight Modes

ArduPilot [flight modes](https://ardupilot.org/copter/docs/flight-modes.html) determine how the FCU interprets inputs. Key modes used by this SDK:

| Mode | Description |
|------|-------------|
| GUIDED | Offboard control. Accepts position/velocity commands from companion computer via MAVLink. Required for SDK navigation. |
| STABILIZE | Manual stabilized flight. Pilot controls via RC. |
| LOITER | GPS-based position hold. Maintains position when sticks centered. |
| RTL | Return to launch. Autonomously flies back to home position and lands. |
| LAND | Auto-land at current position. |

Mode is set via `drone.set_mode()` which calls the [`/mavros/set_mode`](https://docs.ros.org/en/humble/p/mavros/) service. See [MAVLink flight mode protocol](https://ardupilot.org/dev/docs/mavlink-get-set-flightmode.html).

### EKF (Extended Kalman Filter)

The [EKF](https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html) is ArduPilot's state estimator. It fuses IMU, GPS, barometer, and optionally vision/rangefinder data to produce a reliable estimate of the vehicle's position, velocity, and attitude. All altitude and position values in this SDK ultimately come from the EKF's output via MAVROS topics.

### Altitude Types

ArduPilot uses [several altitude definitions](https://ardupilot.org/copter/docs/common-understanding-altitude.html):

| Type | Description | Source | SDK Usage |
|------|-------------|--------|-----------|
| **AGL** (Above Ground Level) | Distance from vehicle to ground directly below | Rangefinder (lidar) | `AltitudeSource.LIDAR`, terrain following |
| **Relative** | Altitude above HOME/ORIGIN. Displayed in GCS/OSD. | EKF (baro + GPS) | `AltitudeSource.REL_ALT`, `move_to_gps` |
| **AMSL** (Above Mean Sea Level) | Altitude above mean sea level | EKF + geoid model | MAVROS GPS setpoint topics |
| **Ellipsoid (WGS84)** | Raw GPS altitude above WGS84 reference ellipsoid. Not the same as AMSL. | GPS receiver | Raw `NavSatFix.altitude` |
| **Vision Z** | Z component from vision pose in local frame. Relative to vision system origin. | External VIO (T265, d435i, etc.) | `AltitudeSource.VISION`, indoor navigation |

**AMSL vs Ellipsoid**: GPS receivers output altitude above the WGS84 ellipsoid, but MAVROS setpoint topics expect AMSL. The difference is the [geoid height](https://en.wikipedia.org/wiki/EGM96), corrected by `GPSUtils` using the EGM96 model.

**Surface Tracking**: When a [downward-facing rangefinder](https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html) is within range, ArduPilot performs [surface tracking](https://ardupilot.org/copter/docs/terrain-following.html) -- adjusting target altitude to maintain constant AGL. Our `AltitudeSource.LIDAR` mode implements a similar concept at the SDK level via PID control.

### Coordinate Frames

The FCU uses **NED** (North-East-Down) / **FRD** (Forward-Right-Down) internally. ROS uses **ENU** (East-North-Up) / **FLU** (Forward-Left-Up). MAVROS [automatically transforms](https://github.com/mavlink/mavros/blob/ros2/mavros/src/plugins/setpoint_raw.cpp) between them — **SDK code always uses ROS conventions**.

| Frame | SDK Input (ROS) | FCU Internal | Origin |
|-------|----------------|-------------|--------|
| **World** | ENU: X=East, Y=North, Z=Up | NED: X=North, Y=East, Z=Down | EKF origin |
| **Body** | FLU: X=Forward, Y=Left, Z=Up | FRD: X=Forward, Y=Right, Z=Down | Vehicle center |
| **WGS84** | Latitude, Longitude, Altitude | Same | Earth reference ellipsoid |

MAVROS transform per [`PositionTarget.coordinate_frame`](https://docs.ros.org/en/api/mavros_msgs/html/msg/PositionTarget.html):
- `FRAME_LOCAL_NED` (1) / `FRAME_LOCAL_OFFSET_NED` (7): ENU→NED (absolute directions)
- `FRAME_BODY_NED` (8) / `FRAME_BODY_OFFSET_NED` (9): FLU→FRD (heading-relative)

For velocity-only commands (`type_mask` ignoring position fields), only the velocity reference matters.

The SDK's `MoveReference` enum:

| MoveReference | `coordinate_frame` | Velocity meaning (SDK input) |
|---|---|---|
| **BODY** | `FRAME_BODY_NED` | vx=forward, vy=left, vz=up (heading-relative) |
| **WORLD** | `FRAME_LOCAL_NED` | vx=east, vy=north, vz=up (absolute directions) |
| **TAKEOFF** | `FRAME_BODY_NED` | Velocities in takeoff heading, rotated to current body frame |

#### EKF Origin (Indoor Requirement)

The EKF local frame needs an origin — the (0,0,0) reference point. Outdoors, GPS sets this automatically. **Indoors, set it manually before flight** via Mission Planner ("Set EKF Origin Here") or [`SET_GPS_GLOBAL_ORIGIN`](https://mavlink.io/en/messages/common.html#SET_GPS_GLOBAL_ORIGIN) MAVLink message. The actual lat/lon values don't matter — the EKF just needs a defined origin to fuse vision data.

Without the EKF origin set, `/mavros/local_position/pose` won't be published and `FRAME_LOCAL_NED` commands won't work.

#### Vision Systems (Indoor Position Source)

An external vision system feeds pose data to ArduPilot's EKF via MAVROS:

**T265** ([vision_to_mavros](https://github.com/Black-Bee-Drones/vision_to_mavros)): `T265 VIO → /tf → vision_to_mavros (ENU alignment) → /mavros/vision_pose/pose`

**D435i** ([Isaac ROS vSLAM](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/tutorial_realsense.html)): `D435i stereo+IMU → isaac_ros_visual_slam → relay → /mavros/vision_pose/pose_cov`

MAVROS converts the ENU pose to NED and sends [`VISION_POSITION_ESTIMATE`](https://mavlink.io/en/messages/common.html#VISION_POSITION_ESTIMATE) to the FCU. The EKF fuses this with IMU and outputs `/mavros/local_position/pose`.

Key ArduPilot parameters: `EK3_SRC1_POSXY=6`, `EK3_SRC1_POSZ=6`, `EK3_SRC1_YAW=6` (ExternalNav), `VISO_TYPE=1`. See [ArduPilot VIO setup](https://ardupilot.org/copter/docs/common-vio-tracking-camera.html) and [ROS VIO guide](https://ardupilot.org/dev/docs/ros-vio-tracking-camera.html).

## Architecture

```mermaid
classDiagram
    class MavrosDrone {
        -_navigator MavrosNavigator
        -_mavros_state State
        -_gps Optional~NavSatFix~
        -_heading Optional~Float64~
        -_rel_alt Optional~Float64~
        -_vision_pos Optional~PoseStamped~
        -_local_pos Optional~PoseStamped~
        -_rng_alt Optional~Range~
        -_imu Optional~Imu~
        -_pid_config Optional~PositionPIDConfig~
        -_setpoint_config Optional~SetpointNavConfig~
        -_takeoff_position Optional
        -_takeoff_local Optional~PositionTarget~
        -_initial_altitude float
        -_initial_heading float
        -_pose_source PoseSource
        +is_indoor bool
        +mavros_state State
        +is_armed Optional~bool~
        +flight_mode Optional~str~
        +is_fcu_connected Optional~bool~
        +gps NavSatFix
        +heading float
        +rel_alt float
        +vision_pos Optional~PoseStamped~
        +local_pos Optional~PoseStamped~
        +lidar_available bool
        +pid_config Optional~PositionPIDConfig~
        +setpoint_config Optional~SetpointNavConfig~
        +position Union~PoseStamped,NavSatFix~
        +position_as_target Optional~Union~PositionTarget,GeoPoseStamped~~
        +from_config(config, node)$ MavrosDrone
        +get_altitude(source) Optional~float~
        +connect() bool
        +arm() bool
        +disarm() bool
        +takeoff(altitude, max_retries, adjust_altitude, precision, timeout) bool
        +land(timeout) bool
        +move_velocity(vx, vy, vz, vyaw, duration, reference)
        +move_to(x, y, z, yaw, reference, timeout, precision, method, altitude_source) bool
        +move_to_gps(lat, lon, alt, heading, timeout, precision, method) bool
        +publish_setpoint(target)
        +emergency_stop()
        +set_home() bool
        +set_takeoff_position(pose, heading)
        +set_pid_config(config)
        +set_setpoint_config(config)
        +set_speed(speed, speed_type) bool
        +set_mode(mode) bool
        +set_param(param_id, value) bool
        +do_servo(aux_out, pwm_value) bool
        +rtl(altitude, precision, method, land) bool
        -_compute_pid_target(x, y, z, yaw, reference, method)
        -_get_local_position() tuple
        -_get_takeoff_for_method(method)
        -_validate_position_sensors(method)
        -_call_service(service, request, success_msg, fail_msg, sync, timeout)
    }

    class TargetComputer {
        <<static>>
        +compute_local_target(pos, yaw, x, y, z, yaw, ref, takeoff)$ PositionTarget
        +compute_gps_target(gps, heading, x, y, z, yaw, ref, takeoff)$ GeoPoseStamped
        +compute_gps_setpoint(gps, heading, x, y, z, yaw, ref, takeoff, rel_alt, init_alt)$ GeoPoseStamped
        +compute_target_rel_alt(rel_alt, z, reference)$ float
        +gps_to_local_target(lat, lon, alt, gps, local, rel_alt, hdg)$ PositionTarget
    }

    class MavrosNavigator {
        -_drone MavrosDrone
        +navigate_pid(target, active_axes, yaw, timeout, precision, altitude_source, altitude_target, use_local) bool
        +navigate_setpoint(target, timeout, precision, check_alt) bool
        +resolve_altitude_target(z, reference, altitude_source) float
        -_get_current_yaw(use_local) float
        -_compute_errors(target, yaw, altitude_source, altitude_target, use_local) tuple
        -_resolve_altitude_error(dz_default, altitude_source, altitude_target) float
        -_resolve_lidar_target(z, reference) float
        -_resolve_rel_alt_target(z, reference) float
        -_check_reached_local(target, precision) tuple
        -_check_reached_gps(target, check_alt, precision) tuple
        -_create_pid(axis) PIDController
    }

    class GPSUtils {
        <<static>>
        -_egm96 GeoidPGM
        +geoid_height(lat, lon)$ float
        +create_gps_setpoint(lat, lon, alt_rel, heading, init_alt)$ GeoPoseStamped
        +check_reached(cur_lat, cur_lon, cur_alt, tgt_lat, tgt_lon, tgt_alt, precision, alt_threshold)$ tuple
    }

    class PositionPIDConfig {
        <<dataclass>>
        +x PIDConfig
        +y PIDConfig
        +z PIDConfig
        +yaw PIDConfig
        +from_yaml(file_path)$ PositionPIDConfig
    }

    class SetpointNavConfig {
        <<dataclass>>
        +guid_options int
        +use_wpnav bool «property»
        +speed float
        +speed_up float
        +speed_down float
        +accel float
        +radius float
        +jerk float
        +psc_jerk float
        +rfnd_use int
        +from_yaml(file_path)$ SetpointNavConfig
        +from_dict(config_dict)$ SetpointNavConfig
    }

    class BaseDrone {
        <<abstract>>
        +add_obstacle_detector()
        +enable_obstacle_detector()
        +cleanup()
    }

    BaseDrone <|-- MavrosDrone
    MavrosDrone *-- MavrosNavigator
    MavrosDrone ..> TargetComputer : uses
    MavrosNavigator ..> PIDController : creates
    MavrosNavigator ..> GPSUtils : uses
    MavrosNavigator ..> PositionUtils : uses
    MavrosDrone o-- PositionPIDConfig
    MavrosDrone o-- SetpointNavConfig
```

## MavrosDrone

### Initialization

```python
from nectar.control import DroneFactory, MavrosConfig, PoseSource

config = MavrosConfig(
    pose_source=PoseSource.VISION,          # or GPS
    expect_lidar=True,                      # Wait for lidar at startup
    connection_string="serial:///dev/ttyUSB0:921600",
    pid_config_file=None,                   # Optional custom PID config
    setpoint_config_file=None,              # Optional custom setpoint nav config
    apply_setpoint_params=False,            # True to push WPNAV params to FCU on arm
)

drone = DroneFactory.create("mavros", config, node)
```

### Pose Sources

**VISION** (Indoor):
- Subscribes to `/mavros/vision_pose/pose_cov`
- Uses local NED frame
- Requires external pose estimation (Realsense, T265, etc.)

**GPS** (Outdoor):
- Subscribes to `/mavros/global_position/global`
- Uses WGS84 coordinates with EGM96 geoid correction
- Requires GPS fix and compass heading

### Properties

```python
drone.is_indoor                 # bool: True if pose_source == VISION
drone.mavros_state             # State: FCU state (mode, armed, connected)
drone.gps                      # NavSatFix: GPS data (outdoor only)
drone.heading                  # float: Compass heading degrees (outdoor only)
drone.rel_alt                  # float: Relative altitude (outdoor only)
drone.vision_pos               # PoseStamped: Vision pose (indoor only, normalized)
drone.local_pos                # PoseStamped: EKF local position (always available)
drone.lidar_available          # bool: Whether lidar data has been received
drone.get_altitude()           # float: Best available altitude (lidar > vision Z > rel_alt)
drone.get_altitude(AltitudeSource.LIDAR)   # float: Lidar rangefinder reading
drone.get_altitude(AltitudeSource.VISION)  # float: Vision pose Z
drone.get_altitude(AltitudeSource.REL_ALT) # float: GPS relative altitude
drone.position                 # Union[PoseStamped, NavSatFix]: Raw position
drone.pid_config               # PositionPIDConfig: Current PID configuration
drone.setpoint_config          # SetpointNavConfig: Current setpoint nav configuration
```

### Takeoff

```python
drone.takeoff(altitude=1.5)  # Default: adjust_altitude=True, precision=0.12m, timeout=25s
drone.takeoff(altitude=2.0, adjust_altitude=False)
drone.takeoff(altitude=1.5, precision=0.15, timeout=30.0)
```

**Sequence**:
1. Arms drone in GUIDED mode
2. Sets takeoff position (first attempt only)
3. Sends takeoff command to FCU
4. Waits for altitude gain (verifies height change >= 0.1m)
5. If `adjust_altitude=True`: Uses `move_to()` to fine-tune altitude to target
6. Retries up to `max_retries` times if altitude doesn't change

## Navigation

Navigation logic is encapsulated in `MavrosNavigator` (composition), keeping `MavrosDrone` focused on hardware interface, sensor data, and target computation.

`move_to` and `move_to_gps` accept `method: NavigationMethod` (defaults: `move_to` → `NavigationMethod.PID_EKF`, `move_to_gps` → `NavigationMethod.PID`). `rtl` accepts `method: RTLMethod` (default `RTLMethod.NAVIGATE`). RTL with `NAVIGATE` uses `PID_EKF` internally.

### Capability Matrix

| Entry Point | PoseSource | Method | Reference | AltitudeSource | Notes |
|------------|-----------|--------|-----------|----------------|-------|
| `move_to` | VISION | PID | BODY, TAKEOFF | AUTO, VISION, LIDAR | Raw vision pose (SDK velocity PID) |
| `move_to` | VISION | PID_EKF | BODY, TAKEOFF | AUTO, VISION, LIDAR | **Default** — EKF local pose (unified frame) |
| `move_to` | VISION | POSITION | BODY, TAKEOFF | N/A | Local setpoint via setpoint_raw/local |
| `move_to` | VISION | ~~POSITION_GLOBAL~~ | — | — | ❌ No GPS indoors |
| `move_to` | GPS | PID | BODY, TAKEOFF | AUTO, LIDAR, REL_ALT | Raw GPS (SDK velocity PID) |
| `move_to` | GPS | PID_EKF | BODY, TAKEOFF | AUTO, LIDAR, REL_ALT | **Default** — EKF local pose (unified frame) |
| `move_to` | GPS | POSITION | BODY, TAKEOFF | N/A | Local setpoint via setpoint_raw/local |
| `move_to` | GPS | POSITION_GLOBAL | BODY, TAKEOFF | N/A | GPS setpoint with AMSL (long range) |
| `move_to` | any | any | WORLD | any | ❌ Not supported |
| `move_to_gps` | GPS | PID | N/A | REL_ALT | GPS waypoint with raw GPS PID |
| `move_to_gps` | GPS | PID_EKF | N/A | REL_ALT | GPS waypoint with EKF local PID |
| `move_to_gps` | GPS | ~~POSITION~~ | — | — | ❌ GPS input needs global output |
| `move_to_gps` | GPS | POSITION_GLOBAL | N/A | N/A | GPS setpoint to FCU |
| `move_to_gps` | VISION | any | N/A | any | ❌ Not supported |
| `move_velocity` | any | N/A | BODY, WORLD, TAKEOFF | N/A | Direct velocity command |

### `move_to` Parameter Behavior

**Axis values — `x`, `y`, `z`, `yaw`**:

Each axis can be a `float` value or `None`. The behavior depends on the navigation method:

| Parameter | Value | PID / PID_EKF | POSITION / POSITION_GLOBAL |
|-----------|-------|-----------------|---------------------------|
| `x` | `float` | Active — PID drives this axis | Included in target position |
| `x` | `None` | **Disabled** — no velocity on this axis, excluded from arrival check | Zero offset — holds current position on this axis |
| `y` | `float` | Active — PID drives this axis | Included in target position |
| `y` | `None` | **Disabled** — no velocity on this axis, excluded from arrival check | Zero offset — holds current position on this axis |
| `z` | `float` | Active — PID drives altitude | Included in target altitude |
| `z` | `None` | **Disabled** — FCU holds altitude, excluded from arrival check | Zero offset — holds current altitude |
| `yaw` | `float` | Active — PID drives yaw (degrees) | Included in target orientation |
| `yaw` | `None` | **Disabled** — maintains current yaw | Holds current yaw |

**Key difference**: With PID methods (`NavigationMethod.PID`, `NavigationMethod.PID_EKF`), `None` truly disables the axis — no velocity is published and the axis is excluded from the distance check. With POSITION methods (`NavigationMethod.POSITION`, `NavigationMethod.POSITION_GLOBAL`), the FCU receives a full 3D+yaw target and controls all axes; `None` means zero offset (hold current).

> **Note on `None` accuracy**: Using `None` is convenient for not having to specify every axis, but comes with trade-offs. With **PID**, a disabled axis is completely uncontrolled — wind or inertia can cause drift on that axis with no correction. The drone may arrive at the correct x but have drifted on y. With **POSITION**, the target for a `None` axis is a snapshot of the current position at call time, which may differ slightly from where you actually want to be (e.g., if the drone was still settling). In both cases, small deviations on unspecified axes are expected. For precise multi-axis positioning, specify all axes explicitly.

**Reference frames — `reference`**:

| Reference | Origin | Heading | Use case |
|-----------|--------|---------|----------|
| `BODY` | Current position | Current heading | "Move 2m forward from where I am now" |
| `TAKEOFF` | Takeoff position | Takeoff heading | "Go to the point 3m forward of where I took off" |

With **BODY**: offsets are relative to where the drone is right now. Each `move_to` chains from the previous position.

With **TAKEOFF**: offsets are absolute from the takeoff origin. Calling `move_to(x=3, reference=TAKEOFF)` always goes to the same world point regardless of current position. `None` axes hold the current position — not the takeoff origin (e.g., if the drone is at y=-3 in takeoff frame, `y=None` keeps it at y=-3).

#### None Axis Behavior by Reference

```
BODY reference:  None = "don't move on this axis" (zero offset from current)
TAKEOFF reference: None = "hold current position on this axis" (not takeoff origin)

Example: drone is at (3, -2) in takeoff frame

move_to(x=0, y=None, reference=TAKEOFF)
→ Target: x=0 (takeoff origin X), y=-2 (current Y preserved)
→ Drone moves to (0, -2) in takeoff frame

move_to(x=0, y=0, reference=TAKEOFF)
→ Target: x=0, y=0 (full takeoff origin)
→ Drone moves to (0, 0) in takeoff frame
```

#### Yaw + Position Behavior (PID / PID_EKF)

When `yaw` is specified together with position axes (`x` or `y`), PID navigation uses a **yaw-first** approach:

1. **Phase 1 — Yaw alignment**: Rotates to target yaw while holding position (zero translational velocity). Completes when yaw error ≤ 3°.
2. **Phase 2 — Translation**: Moves to the target position with yaw hold. Both `x` and `y` axes are activated regardless of which was originally specified, because after rotation the world-frame target may project onto either body axis.

The position target is always computed at call time in the original heading direction. Yaw rotation does not change where the drone goes — only its final orientation.

```
move_to(x=5, yaw=90):                       move_to(x=5, y=2, yaw=90):

  Phase 1: Rotate 90°                         Phase 1: Rotate 90°
  Phase 2: Fly to target                       Phase 2: Fly to target

       target ←─── 5m ───── start                  target
         ·                    │                    ╱
         ·                    │ rotate            ╱  ~5.4m
         ·  · · · · · · · · ·│ 90°              ╱
         ▼                    ▼               start
      (arrives facing 90°)                    │ rotate
                                              ▼ 90°
                                           (arrives facing 90°)
```

With POSITION / POSITION_GLOBAL methods, yaw and position are controlled simultaneously by the FCU (no yaw-first phase needed — the target is in world frame).

### Navigation Examples

**Move relative to current position (BODY)**:
```python
drone.move_to(x=2.0, y=0.0, z=0.0)             # 2m forward
drone.move_to(x=0.0, y=1.0, z=0.0)             # 1m left
drone.move_to(z=0.5)                            # 0.5m up (x/y disabled)
drone.move_to(x=3.0, yaw=45.0)                  # rotate 45° left, then 3m to target
```

**Move relative to takeoff position (TAKEOFF)**:
```python
# Coordinates are absolute offsets from where the drone took off
drone.move_to(x=2.0, y=0.0, z=0.0, reference=MoveReference.TAKEOFF)  # 2m forward of takeoff
drone.move_to(x=2.0, y=1.0, z=0.0, reference=MoveReference.TAKEOFF)  # same X, 1m left of takeoff
drone.move_to(x=0.0, y=0.0, z=0.0, reference=MoveReference.TAKEOFF)  # back to takeoff position

# None axes hold current position, not takeoff origin
drone.move_to(x=0.0, reference=MoveReference.TAKEOFF)  # return to takeoff X, keep current Y and Z
drone.move_to(z=1.5, reference=MoveReference.TAKEOFF)   # go to 1.5m above takeoff, keep current XY
```

**Terrain following with lidar**:
```python
# z is height above ground (lidar reading), not position-based
drone.move_to(x=2.0, y=0.0, z=0.3, altitude_source=AltitudeSource.LIDAR)  # fly at 0.3m AGL
drone.move_to(x=2.0, y=0.0, z=1.5, altitude_source=AltitudeSource.LIDAR)  # fly at 1.5m AGL

# With TAKEOFF reference, z is absolute AGL altitude
drone.move_to(x=0.0, y=0.0, z=1.0,
              reference=MoveReference.TAKEOFF,
              altitude_source=AltitudeSource.LIDAR)  # hold 1.0m AGL at takeoff XY
```

**EKF local position (PID_EKF) — unified indoor/outdoor**:
```python
# Uses /mavros/local_position/pose for PID feedback (same code indoor and outdoor)
drone.move_to(x=2.0, y=0.0, z=0.0, method=NavigationMethod.PID_EKF)
```

**Local position (POSITION) — FCU handles position control**:
```python
# Publishes target to setpoint_raw/local. Works indoor and outdoor.
# FCU controls all axes simultaneously (including yaw)
drone.move_to(x=2.0, y=1.0, z=0.0, method=NavigationMethod.POSITION)
drone.move_to(x=3.0, yaw=90.0, method=NavigationMethod.POSITION)  # simultaneous position + yaw
```

**GPS waypoint navigation (outdoor)**:
```python
# PID with raw GPS (default for move_to_gps)
drone.move_to_gps(lat=-27.1234, lon=-48.4567, altitude=15.0, precision=1.0)

# GPS global setpoint (long range, FCU handles navigation)
drone.move_to_gps(lat=-27.1234, lon=-48.4567, altitude=15.0,
                  method=NavigationMethod.POSITION_GLOBAL)

# PID with EKF local position
drone.move_to_gps(lat=-27.1234, lon=-48.4567, altitude=15.0,
                  method=NavigationMethod.PID_EKF)
```

**Velocity control**:
```python
# Body-frame: forward relative to where drone is pointing
drone.move_velocity(vx=0.5, vy=0.0, vz=0.0, reference=MoveReference.BODY)

# World-frame: move east at 0.5 m/s regardless of heading (ENU: vx=east)
drone.move_velocity(vx=0.5, vy=0.0, vz=0.0, reference=MoveReference.WORLD)

# Timed: move forward for 2 seconds then stop
drone.move_velocity(vx=1.0, duration=2.0, reference=MoveReference.BODY)
```

### Altitude Source Behavior

| AltitudeSource | Sensor | When Used | dz Computation |
|---------------|--------|-----------|----------------|
| AUTO | Best available | Default for `move_to` | Position-based via `get_body_distance()` |
| LIDAR | Rangefinder | Terrain following, precise AGL | `altitude_target - current_lidar` |
| VISION | Vision pose Z | Indoor altitude hold | Position-based via `get_body_distance()` |
| REL_ALT | GPS relative alt | `move_to_gps` PID, outdoor | `altitude_target - current_rel_alt` |

**Altitude `z` parameter by reference**:

| Reference | `z` value | LIDAR source | REL_ALT source | AUTO / VISION source |
|-----------|-----------|-------------|----------------|---------------------|
| BODY | `float` | `current_lidar + z` (relative) | `current_rel_alt + z` (relative) | Position-based dz |
| BODY | `None` | Disabled | Disabled | Disabled (FCU holds) |
| TAKEOFF | `float` | `z` (absolute AGL) | `z` (absolute rel alt) | `takeoff_z + z` |
| TAKEOFF | `None` | Disabled | Disabled | Disabled (holds current) |

**LIDAR limits**: Capped at 15m; falls back to position-based if exceeded.

#### Altitude with TAKEOFF Reference — How `takeoff_z` Works

The takeoff position is stored by `_set_takeoff_position()` at the **start of `takeoff()`** — while the drone is still on the ground, before it climbs. This means:

- For **vision/local** (PID, PID_EKF, POSITION): `takeoff_z ≈ 0` (ground level in vision/EKF frame)
- For **GPS** (PID outdoor, POSITION_GLOBAL): `takeoff_z` = raw GPS altitude on the ground (e.g., 605m ellipsoid height)

With **AUTO/VISION** source (the default), `z` with TAKEOFF reference computes `target_z = takeoff_z + z`. Since `takeoff_z ≈ 0` for vision/local, `z` is effectively the **absolute height above the takeoff ground level**:

```
drone.takeoff(altitude=1.5)
# Drone is now at 1.5m altitude. Stored takeoff_z ≈ 0 (ground level).

drone.move_to(z=1.5, reference=MoveReference.TAKEOFF)   # target = 0 + 1.5 = 1.5m → stay at same height
drone.move_to(z=2.0, reference=MoveReference.TAKEOFF)   # target = 0 + 2.0 = 2.0m → climb 0.5m
drone.move_to(z=0.5, reference=MoveReference.TAKEOFF)   # target = 0 + 0.5 = 0.5m → descend 1.0m
drone.move_to(z=0.0, reference=MoveReference.TAKEOFF)   # target = 0 + 0.0 = 0.0m → descend to ground level
```

With **LIDAR** source and TAKEOFF reference, `z` is the **absolute height above the ground** (direct sensor target):

```
drone.move_to(z=1.0, reference=MoveReference.TAKEOFF, altitude_source=AltitudeSource.LIDAR)
# Target: lidar reads 1.0m. Independent of takeoff_z.
```

With **REL_ALT** source and TAKEOFF reference, `z` is the **absolute relative altitude** (above home):

```
drone.move_to_gps(lat=..., lon=..., altitude=15.0)
# Target: rel_alt = 15.0m
```

> **Key takeaway**: With TAKEOFF reference, `z` is always an **absolute target value**, not a relative offset. After `takeoff(1.5)`, use `z=1.5` to maintain the same height — not `z=0`. `z=0` with AUTO source means "go to ground-level Z".

**Ground collision safety**: `move_to` rejects `z` values that would produce a target altitude ≤ 0. With TAKEOFF reference, `z ≤ 0` is rejected. With BODY reference, `z` is rejected if `current_altitude + z ≤ 0`. In both cases, `z` is set to `None` (altitude disabled) and a warning is logged. The drone still moves on the other axes. Very low positive values (e.g., `z=0.05`) are accepted — the user is responsible for ensuring they are safe for the aircraft and mission.

### Navigation Flow

```mermaid
flowchart TD
    A["move_to / move_to_gps"] --> B{"Method?"}
    B -->|PID / PID_EKF| C["Compute PID target"]
    B -->|POSITION / POSITION_GLOBAL| D["Compute setpoint target"]
    C --> E["resolve_altitude_target"]
    E --> F["navigator.navigate_pid"]
    D --> G["navigator.navigate_setpoint"]
    F --> yawCheck{"yaw specified +\nposition axes active?"}
    yawCheck -->|Yes| yawPhase["Phase 1: Align yaw\n(zero translation)"]
    yawPhase --> yawDone{"yaw ≤ 3°?"}
    yawDone -->|No| yawPhase
    yawDone -->|Yes| enableXY["Enable both x,y axes\nReset yaw PID"]
    enableXY --> H
    yawCheck -->|No| H["Phase 2: PID loop"]
    H --> J["_compute_errors\n(body-frame dx,dy,dz,dyaw)"]
    J --> L["PID → move_velocity"]
    L --> yawPID{"Position + yaw\nconverged?"}
    yawPID -->|No| H
    yawPID -->|Yes| donePID["Target reached ✓"]
    G --> I["Setpoint loop"]
    I --> M{"Target type?"}
    M -->|PositionTarget| N["publish_setpoint\n+ _check_reached_local"]
    M -->|GeoPoseStamped| O["publish_setpoint\n+ _check_reached_gps"]
    N --> yawSP{"Position + yaw\nconverged?"}
    O --> yawSP
    yawSP -->|No| I
    yawSP -->|Yes| doneSP["Setpoint reached ✓"]
```

### PID Navigation

Velocity-based control with closed-loop feedback via `MavrosNavigator.navigate_pid()`.

**Algorithm**:
```
1. MavrosDrone computes target position (world frame, based on reference)
2. MavrosDrone resolves altitude_target (based on altitude_source)
3. MavrosNavigator creates PID controllers from config
4. If yaw + position specified: align yaw first (Phase 1)
   - Publish yaw-rate only (vx=vy=vz=0)
   - Wait until |dyaw| ≤ 3°
   - Activate both x and y axes for Phase 2
5. Position loop (Phase 2) at ~100 Hz:
   a. Compute body-frame errors (dx, dy, dz, dyaw)
   b. Override dz if altitude_target set (LIDAR/REL_ALT source)
   c. Update PID controllers with errors
   d. Generate and publish velocity commands
   e. Check arrival: distance ≤ precision AND |dyaw| ≤ 3°
```

**Dead Zone**: Per-axis velocity zeroed when error < `precision / 2` to prevent oscillation.

**Active axes**: Only axes with non-`None` values are controlled and included in the distance check. Exception: when yaw is specified with x or y, both horizontal axes are activated after yaw alignment (the world-frame target may project onto either body axis after rotation).

### Position Navigation

Direct position setpoint publishing via `MavrosNavigator.navigate_setpoint()`. The FCU receives a full target (position + yaw) and controls all axes simultaneously — no yaw-first phase needed.

**Indoor** (PositionTarget): Publishes to `/mavros/setpoint_raw/local`, checks Euclidean distance using EKF local position.

**Outdoor** (GeoPoseStamped): Publishes to `/mavros/setpoint_position/global` with AMSL-corrected altitude, checks geodesic distance using GPS and relative altitude.

**Yaw convergence**: PID navigation and position-setpoint navigation (`navigate_setpoint`) both verify that the target yaw has been reached (within `YAW_THRESHOLD = 3°`) before declaring arrival. Yaw error is computed via `PositionUtils.compute_yaw_error()` and logged alongside distance each iteration.

#### ArduPilot GUIDED Mode Position Controllers

When the SDK publishes a `PositionTarget` to `/mavros/setpoint_raw/local`, MAVROS translates it into a [`SET_POSITION_TARGET_LOCAL_NED`](https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED) MAVLink message (see [`setpoint_mixin.hpp`](https://github.com/mavlink/mavros/blob/ros2/mavros/include/mavros/setpoint_mixin.hpp)). ArduPilot's GUIDED mode then routes the message to one of two internal position controllers, depending on the [`GUID_OPTIONS`](https://ardupilot.org/copter/docs/ac2_guidedmode.html#guided-mode-options) parameter:

| Controller | GUID_OPTIONS | ArduPilot SubMode | Trajectory | Speed Control |
|---|---|---|---|---|
| **AC_PosControl** (default) | bit 6 = 0 | `SubMode::Pos` | Direct PID to target | Speed limits from WPNAV at init |
| **AC_WPNav** | bit 6 = 1 (value 64) | `SubMode::WP` | S-curve path planning | Full WPNAV parameter set |

Source: [`mode_guided.cpp :: set_pos_NED_m()`](https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_guided.cpp) — the `use_wpnav_for_position_control()` conditional selects the sub-mode based on GUID_OPTIONS bit 6.

**AC_PosControl (SubMode::Pos) — Default behavior**

The default GUIDED mode behavior for position-only targets. ArduPilot's position controller runs a PID loop directly toward the target point. At initialization ([`pva_control_start()`](https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_guided.cpp)), speed limits are read from WPNAV parameters:

```
pos_control->NE_set_max_speed_accel_m(wp_nav->get_default_speed_NE_ms(), ...)
pos_control->D_set_max_speed_accel_m(wp_nav->get_default_speed_down_ms(), wp_nav->get_default_speed_up_ms(), ...)
```

Characteristics:
- Flies toward target with basic PID, no trajectory shaping
- Speed limits are set once at mode init, not re-read dynamically from WPNAV params
- No internal "arrival radius" concept — the SDK's `_check_reached_local()` handles arrival detection
- Target can be updated rapidly (suitable for continuous position streaming)
- Can produce abrupt movements at high speeds or long distances

**AC_WPNav (SubMode::WP) — S-curve path planning**

Enabled by setting `GUID_OPTIONS` bit 6 (value 64). Uses the same [AC_WPNav](https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_WPNav) library as AUTO mode, providing S-curve trajectory planning with controlled acceleration and deceleration.

Characteristics:
- Flies a straight-line path with smooth S-curve speed profile (trapezoidal accel/decel)
- Respects all `WPNAV_*` parameters dynamically (speed, radius, accel, jerk)
- Uses `WPNAV_RADIUS` for internal arrival detection and deceleration planning
- Supports object avoidance path planning ([Bendy Ruler](https://ardupilot.org/copter/docs/common-oa-bendyruler.html), [Dijkstra](https://ardupilot.org/copter/docs/common-oa-dijkstras.html))
- Target should **not** be updated rapidly — each new target triggers a full trajectory replan
- Best suited for point-to-point missions (go to point, stop, perform action)

See [ArduPilot PosControl and Navigation overview](https://ardupilot.org/dev/docs/code-overview-copter-poscontrol-and-navigation.html) and [Guided Mode documentation](https://ardupilot.org/copter/docs/ac2_guidedmode.html).

#### WPNAV Parameters

ArduPilot v4.6.3 [`WPNAV_*` parameters](https://ardupilot.org/copter/docs/parameters-Copter-stable-V4.6.3.html#wpnav-parameters) control navigation speed, acceleration, and precision. Default values from [`AC_WPNav.cpp`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_WPNav/AC_WPNav.cpp):

| Parameter | Description | ArduPilot Default | Unit | Range |
|---|---|---|---|---|
| `WPNAV_SPEED` | Horizontal speed | 1000 (10 m/s) | cm/s | 10–2000 |
| `WPNAV_SPEED_UP` | Climb speed | 250 (2.5 m/s) | cm/s | 10–1000 |
| `WPNAV_SPEED_DN` | Descent speed | 150 (1.5 m/s) | cm/s | 10–500 |
| `WPNAV_ACCEL` | Horizontal acceleration | 250 (2.5 m/s²) | cm/s/s | 50–500 |
| `WPNAV_RADIUS` | Waypoint arrival radius | 200 (2.0 m) | cm | 5–1000 |
| `WPNAV_ACCEL_Z` | Vertical acceleration | 100 (1.0 m/s²) | cm/s/s | 50–500 |
| `WPNAV_JERK` | Horizontal jerk | 1.0 | m/s/s/s | 1–20 |
| `WPNAV_RFND_USE` | Rangefinder terrain following | 1 (enabled) | bool | 0–1 |

> **Note**: In ArduPilot dev (v4.8+), these are renamed to `WP_*`. The SDK uses descriptive field names (`speed`, `radius`) so only the internal `_apply_setpoint_config()` mapping needs updating for version changes.

The SDK also configures `PSC_JERK_XY` (4.6.3) / `PSC_JERK_NE` (4.8+) — position controller horizontal jerk, default 5.0 m/s³, range 1–20 — via `SetpointNavConfig.psc_jerk`. This controls AC_PosControl's response speed in SubMode::Pos. In SITL, higher values (e.g. 50) are typically needed for usable response time.

**How parameters affect each sub-mode:**

| Behavior | SubMode::Pos (default) | SubMode::WP (GUID_OPTIONS bit 6) |
|---|---|---|
| WPNAV_SPEED | Read once at submode init; `set_param` mid-flight has no effect (use `MAV_CMD_DO_CHANGE_SPEED`) | Re-read on each `set_destination()` call; `set_param` takes effect on next target |
| WPNAV_RADIUS | Not used (SDK handles arrival via `_check_reached_local`) | Re-read on each `set_destination()`; controls deceleration planning and arrival detection |
| WPNAV_ACCEL | Read once at submode init | Re-read on each `set_destination()`; controls S-curve acceleration profile |
| WPNAV_JERK | Not used | Controls S-curve trajectory smoothness |
| WPNAV_RFND_USE | Not used (`is_terrain_alt=false` for `SET_POSITION_TARGET_LOCAL_NED`) | Only if terrain alt is explicitly requested |
| PSC_JERK_XY/NE | Controls position controller horizontal jerk limit | Not used (WPNav has own jerk via WPNAV_JERK) |

> **Runtime `set_param` summary**: In SubMode::WP, all `WPNAV_*` parameters are picked up on the next target because [`wp_nav->set_wp_destination()`](https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_WPNav) re-reads them. In SubMode::Pos, speed/accel limits are set once via [`AC_PosControl`](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_AttitudeControl/AC_PosControl.h) at submode entry (`pva_control_start()`); use `MAV_CMD_DO_CHANGE_SPEED` for dynamic changes. The SDK's `_sync_wpnav_radius()` leverages this WPNav behavior to update `WPNAV_RADIUS` on each `move_to` / `move_to_gps` call that uses `NavigationMethod.POSITION` or `NavigationMethod.POSITION_GLOBAL` (with WPNav enabled) from the `precision` argument.

#### Speed Control at Runtime

Two mechanisms exist for changing speed limits during flight:

**`set_param("WPNAV_SPEED", value)`** — Updates the stored FCU parameter via [`PARAM_SET`](https://mavlink.io/en/messages/common.html#PARAM_SET). In SubMode::WP, the new value is picked up on the next `update_wpnav()` loop. In SubMode::Pos, it only takes effect at the next mode initialization (e.g., re-arm or mode switch).

**`set_speed(speed, speed_type)`** — Sends [`MAV_CMD_DO_CHANGE_SPEED`](https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed) (command 178). This directly calls `set_speed_NE_ms()` / `set_speed_up_ms()` / `set_speed_down_ms()` on the current flight mode, which immediately updates AC_PosControl's active speed limits. Works in both sub-modes.

Source: [`GCS_MAVLink_Copter.cpp :: handle_MAV_CMD_DO_CHANGE_SPEED()`](https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/GCS_MAVLink_Copter.cpp)

```python
# Immediate speed change via MAV_CMD_DO_CHANGE_SPEED
drone.set_speed(0.5, "horizontal")   # 0.5 m/s horizontal
drone.set_speed(0.3, "climb")        # 0.3 m/s climb
drone.set_speed(0.3, "descent")      # 0.3 m/s descent
drone.set_speed(-2, "horizontal")    # revert to WPNAV_SPEED default
```

#### Position + Velocity in PositionTarget

The `PositionTarget` message supports both position and velocity fields simultaneously via `type_mask`. However, combined position+velocity does **not** mean "go to position at this max speed". As explained in [ArduPilot issue #3536](https://github.com/ArduPilot/ardupilot/issues/3536#issuecomment-305703504), the caller must provide a **continuous stream** of desired positions and velocities — the vehicle tries to achieve both simultaneously. This is useful for curved paths (e.g., circles) where the caller continuously updates the position and velocity vector, but is **not suitable** for point-to-point navigation where the drone should fly to a point and stop.

### Velocity Control

Direct velocity command publishing to flight controller.

**Method**: `move_velocity(vx, vy, vz, vyaw, duration, reference)`

**Reference Frames**:
- **BODY** (default): `FRAME_BODY_NED`. vx=forward, vy=left, vz=up (heading-relative, FLU input).
- **WORLD**: `FRAME_LOCAL_NED`. vx=east, vy=north, vz=up (absolute directions, ENU input).
- **TAKEOFF**: `FRAME_BODY_NED`. Velocities in takeoff heading, rotated to current body frame.

**Duration**: If `duration` is specified, command is published at 30 Hz for the specified time. If `None`, command is published once (continuous until next command).

## Reference Frame Transformations

### Supported references by API

| API | BODY | WORLD | TAKEOFF |
|-----|------|-------|---------|
| `move_velocity()` | yes | yes | yes |
| `move_to()` | yes | no | yes |

**Note**: `move_to()` does not support `WORLD` reference and will raise `CapabilityNotSupportedError` if used.

### BODY Frame

Relative to current position and orientation.

**move_velocity**: Uses `FRAME_BODY_NED` coordinate frame.

**move_to**: Transforms relative offsets to world coordinates:
```python
dx = x * cos(current_yaw) - y * sin(current_yaw)
dy = x * sin(current_yaw) + y * cos(current_yaw)
target = current_position + (dx, dy, z)
```

### WORLD Frame

Absolute direction velocities regardless of drone heading. **`move_velocity` only** — `move_to` raises `CapabilityNotSupportedError`.

Uses `FRAME_LOCAL_NED`: velocities are in ENU convention (vx=east, vy=north, vz=up). MAVROS converts to NED before sending to the FCU. "North/East" are relative to the EKF origin's frame — indoors, these directions depend on the magnetometer or vision yaw when the EKF origin was set.

Works both indoors (with vision + EKF origin set) and outdoors (with GPS).

### TAKEOFF Frame

Relative to takeoff position and orientation.

**move_velocity**: Transforms velocities from takeoff frame to body frame before publishing.

**move_to**: Direct offset from takeoff position:
```python
target = takeoff_position + rotate(x, y, z, takeoff_yaw)
```

**Requirement**: Takeoff position must be set via `takeoff()` or `set_takeoff_position()`.

## RTL Implementation

Default `rtl()` uses `RTLMethod.NAVIGATE` (SDK PID path to home). Use `RTLMethod.NATIVE` for the FCU RTL mode.

### NAVIGATE (`RTLMethod.NAVIGATE`)

Navigate to takeoff position using PID control.

**Sequence**:
1. If altitude specified: climb/descend to altitude
2. Navigate to takeoff position (x=0, y=0, z=0, reference=TAKEOFF)
3. If `land=True`: execute landing

```python
drone.rtl(altitude=5.0, method=RTLMethod.NAVIGATE, land=True)
```

### NATIVE (`RTLMethod.NATIVE`)

Trigger ArduPilot's native RTL mode. See [RTL Mode](https://ardupilot.org/copter/docs/rtl-mode.html).

**Sequence**:
1. Set `RTL_ALT`: if `altitude` is specified, sets the minimum return altitude (in cm). If `altitude` is `None`, sets `RTL_ALT=0` so the drone returns at its current altitude (ArduPilot default is 15m which causes unwanted climbing).
2. Set `RTL_ALT_FINAL`: if `land=True`, sets to 0 (auto-land after loiter). If `land=False`, sets to the same value as `RTL_ALT` (hold altitude above home, no descent).
3. Set mode to "RTL".

Parameter names differ between ArduPilot versions: `RTL_ALT` / `RTL_ALT_FINAL` (v4.6.3, centimeters) vs `RTL_ALT_M` / `RTL_ALT_FINAL_M` (v4.8+, meters). The SDK tries the v4.6.3 name first and falls back to v4.8+ automatically.

```python
drone.rtl(method=RTLMethod.NATIVE)                        # return at current altitude, auto-land
drone.rtl(altitude=15.0, method=RTLMethod.NATIVE)          # climb to 15m, return, auto-land
drone.rtl(method=RTLMethod.NATIVE, land=False)             # return at current altitude, hold above home
drone.rtl(altitude=10.0, method=RTLMethod.NATIVE, land=False)  # climb to 10m, return, hold at 10m
```

## ROS2 Topics

### Subscribers

| Topic | Type | Purpose |
|-------|------|---------|
| `/mavros/state` | State | FCU connection and mode |
| `/mavros/rangefinder/rangefinder` | Range | Lidar altitude |
| `/mavros/imu/data` | Imu | IMU measurements |
| `/mavros/local_position/pose` | PoseStamped | EKF local position (always) |
| `/mavros/vision_pose/pose_cov` | PoseWithCovarianceStamped | Vision pose (indoor, auto-detected) |
| `/mavros/vision_pose/pose` | PoseStamped | Vision pose (indoor, auto-detected) |
| `/mavros/global_position/global` | NavSatFix | GPS position (outdoor) |
| `/mavros/global_position/rel_alt` | Float64 | Relative altitude (outdoor) |
| `/mavros/global_position/compass_hdg` | Float64 | Compass heading (outdoor) |

### Publishers

| Topic | Type | Purpose |
|-------|------|---------|
| `/mavros/setpoint_raw/local` | PositionTarget | Velocity/position setpoints |
| `/mavros/setpoint_position/global` | GeoPoseStamped | GPS setpoints (outdoor) |
| `/mavros/setpoint_raw/global` | GlobalPositionTarget | GPS raw setpoints (outdoor) |

### Services

| Service | Type | Purpose |
|---------|------|---------|
| `/mavros/set_mode` | SetMode | Change flight mode |
| `/mavros/cmd/arming` | CommandBool | Arm/disarm motors |
| `/mavros/cmd/takeoff` | CommandTOL | Takeoff command |
| `/mavros/cmd/land` | CommandTOL | Land command |
| `/mavros/cmd/set_home` | CommandHome | Set home position |
| `/mavros/cmd/command` | CommandLong | Generic MAVLink commands |
| `/mavros/param/set_parameters` | SetParameters | Set FCU parameters |

## PID Configuration

### Default Configurations

**Indoor** (`config/mavros/position_indoor.yaml`):
```yaml
x:
  kp: 0.5
  output_min: -0.42
  output_max: 0.42

y:
  kp: 0.5
  output_min: -0.42
  output_max: 0.42

z:
  kp: 0.22
  output_min: -0.15
  output_max: 0.1

yaw:
  kp: 0.5
  ki: 0.1
  output_min: -0.2
  output_max: 0.2
```

**Outdoor** (`config/mavros/position_outdoor.yaml`):
```yaml
x:
  kp: 0.8
  output_min: -1.0
  output_max: 1.0

y:
  kp: 0.8
  output_min: -1.0
  output_max: 1.0

z:
  kp: 0.5
  output_min: -0.8
  output_max: 0.8

yaw:
  kp: 0.5
  ki: 0.1
  output_min: -0.3
  output_max: 0.3
```

### Runtime Updates

```python
# From YAML file
drone.set_pid_config("/path/to/config.yaml")

# From dictionary
drone.set_pid_config({
    "x": {"kp": 0.8, "output_min": -1.0, "output_max": 1.0},
    "y": {"kp": 0.8, "output_min": -1.0, "output_max": 1.0},
    "z": {"kp": 0.5, "output_min": -0.8, "output_max": 0.8},
    "yaw": {"kp": 0.5, "ki": 0.1, "output_min": -0.3, "output_max": 0.3}
})

# From PositionPIDConfig object
from nectar.control.pid import PositionPIDConfig, PIDConfig

config = PositionPIDConfig(
    x=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
    y=PIDConfig(kp=0.8, output_min=-1.0, output_max=1.0),
    z=PIDConfig(kp=0.5, output_min=-0.8, output_max=0.8),
    yaw=PIDConfig(kp=0.5, ki=0.1, output_min=-0.3, output_max=0.3)
)
drone.set_pid_config(config)
```

## Setpoint Navigation Configuration

Controls ArduPilot GUIDED mode behavior when using `NavigationMethod.POSITION` (local setpoints via `setpoint_raw/local`). Manages the position controller sub-mode (AC_PosControl vs AC_WPNav) and WPNAV parameters.

### How It Works

1. **On init**: `_load_setpoint_config()` loads from `setpoint_config_file` (if provided), otherwise from `config/mavros/setpoint_indoor.yaml` or `setpoint_outdoor.yaml` based on `is_indoor`. The config is always loaded for SDK-side logic (e.g., `use_wpnav` checks).
2. **On arm** (only if `apply_setpoint_params=True`): `_apply_setpoint_config()` sends `GUID_OPTIONS` and all `WPNAV_*` parameters to the FCU via `set_param()`. Logs which parameters failed.
3. **On `move_to` / `move_to_gps` with `NavigationMethod.POSITION` or `POSITION_GLOBAL`** (only if `apply_setpoint_params=True`): If `use_wpnav` (bit 6 set in `guid_options`), syncs `WPNAV_RADIUS` with the `precision` parameter.

> **Important — FCU parameter persistence**: `set_param()` sends a MAVLink `PARAM_SET` message. ArduPilot's handler calls `vp->save()`, which **writes to EEPROM/flash**. Values persist across reboots. By default `apply_setpoint_params=False` so the SDK does not touch FCU parameters. Set `apply_setpoint_params=True` only when you want the SDK to control these values (e.g., SITL). You can also push parameters on demand via `drone.set_setpoint_config(config)` regardless of this flag.

```mermaid
flowchart TD
    A["MavrosConfig.setpoint_config_file"] --> B["_load_setpoint_config()"]
    B --> C["SetpointNavConfig loaded"]
    D["arm() → set_mode GUIDED"] --> E{"apply_setpoint_params?"}
    E -->|Yes| F["_apply_setpoint_config()"]
    F --> G["set_param GUID_OPTIONS"]
    F --> H["set_param WPNAV_SPEED/UP/DN"]
    F --> I["set_param WPNAV_ACCEL/RADIUS/JERK"]
    F --> Ip["set_param PSC_JERK_XY/NE"]
    E -->|No| skip["Skip — use existing FCU values"]
    J["move_to(precision=0.1)"] --> K{"apply_setpoint_params\n+ guid_options bit 6?"}
    K -->|Yes| L["set_param WPNAV_RADIUS = precision"]
    L --> M["navigate_setpoint"]
    K -->|No| M
```

### Default Configurations

All values in SI units (m/s, m, m/s³). Speed/accel/radius are converted to ArduPilot units (cm/s, cm) internally by `_apply_setpoint_config()`. Jerk values are already in m/s³.

**Indoor** (`config/mavros/setpoint_indoor.yaml`):
```yaml
guid_options: 1     # bit 0 (arm from TX, AC_PosControl)
speed: 0.5          # 50 cm/s horizontal
speed_up: 0.3       # 30 cm/s climb
speed_down: 0.3     # 30 cm/s descent
accel: 0.5          # 50 cm/s/s horizontal acceleration
radius: 0.1         # 10 cm arrival radius
jerk: 1.0           # WPNav S-curve jerk (m/s³)
psc_jerk: 5.0       # Position controller NE jerk (m/s³)
rfnd_use: 0         # Rangefinder terrain following off
```

**Outdoor** (`config/mavros/setpoint_outdoor.yaml`):
```yaml
guid_options: 1     # bit 0 (arm from TX, AC_PosControl)
speed: 2.0          # 200 cm/s horizontal
speed_up: 1.5       # 150 cm/s climb
speed_down: 1.0     # 100 cm/s descent
accel: 1.0          # 100 cm/s/s horizontal acceleration
radius: 0.3         # 30 cm arrival radius
jerk: 1.0           # WPNav S-curve jerk (m/s³)
psc_jerk: 5.0       # Position controller NE jerk (m/s³)
rfnd_use: 1         # Rangefinder terrain following on
```

Both default to `guid_options: 1` (arm from TX, AC_PosControl). The SDK speed defaults are intentionally conservative compared to ArduPilot's factory defaults (10 m/s, 2.0 m radius) to prevent aggressive movements.

### Dataclass Defaults

`SetpointNavConfig()` without a YAML file uses these values (fallback if no config file is found):

| Field | Default | ArduPilot Factory Default |
|---|---|---|
| `guid_options` | `1` (bit 0) | `0` |
| `speed` | 2.0 m/s | 10.0 m/s |
| `speed_up` | 1.5 m/s | 2.5 m/s |
| `speed_down` | 1.5 m/s | 1.5 m/s |
| `accel` | 1.0 m/s² | 2.5 m/s² |
| `radius` | 0.2 m | 2.0 m |
| `jerk` | 1.0 m/s³ | 1.0 m/s³ |
| `psc_jerk` | 5.0 m/s³ | 5.0 m/s³ |
| `rfnd_use` | 1 | 1 |

`guid_options` is the [`GUID_OPTIONS`](https://ardupilot.org/copter/docs/ac2_guidedmode.html#guided-mode-options) bitmask sent directly to the FCU. The `use_wpnav` property returns `True` when bit 6 is set. Common values:

| Value | Bits | Meaning |
|---|---|---|
| 0 | — | Default GUIDED (AC_PosControl, no TX arm) |
| 1 | 0 | Allow arming from TX |
| 64 | 6 | WPNav S-curve only |
| 65 | 0 + 6 | **SDK default**: arm from TX + WPNav |
| 193 | 0 + 6 + 7 | Arm from TX + WPNav + weathervaning |

### Runtime Updates

```python
# Push config to FCU (default: apply=True)
drone.set_setpoint_config("/path/to/custom_setpoint.yaml")
drone.set_setpoint_config({"guid_options": 65, "speed": 0.3, "radius": 0.1})
drone.set_setpoint_config(SetpointNavConfig(guid_options=65, speed=0.5, radius=0.1))

# Update SDK-side config only, without touching FCU parameters
drone.set_setpoint_config({"guid_options": 1, "speed": 0.5}, apply=False)
```

`set_setpoint_config()` always pushes to the FCU by default (`apply=True`), regardless of `apply_setpoint_params`. This is an explicit user action. Pass `apply=False` to update only the SDK-side config.

### Speed Control

For immediate speed changes during flight (without re-applying the full config), use `set_speed()`:

```python
drone.set_speed(0.8, "horizontal")   # MAV_CMD_DO_CHANGE_SPEED type 0
drone.set_speed(0.5, "climb")        # MAV_CMD_DO_CHANGE_SPEED type 1
drone.set_speed(0.3, "descent")      # MAV_CMD_DO_CHANGE_SPEED type 2
```

This sends [`MAV_CMD_DO_CHANGE_SPEED`](https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed) which directly updates AC_PosControl's active speed limits. Works in both SubMode::Pos and SubMode::WP. See [Guided Mode speed control](https://ardupilot.org/copter/docs/ac2_guidedmode.html#speed-control).

### Usage Examples

**Conservative indoor navigation with WPNav S-curve:**
```python
config = MavrosConfig(
    pose_source=PoseSource.VISION,
    setpoint_config_file="/path/to/slow_indoor.yaml",
)
drone = DroneFactory.create("mavros", config, node)

# WPNav enabled by default (guid_options=65), just adjust speed
drone.set_setpoint_config({"speed": 0.3, "radius": 0.1})

# move_to syncs WPNAV_RADIUS with precision when WPNav is enabled (bit 6)
drone.move_to(x=2.0, y=0.0, z=0.0, method=NavigationMethod.POSITION, precision=0.1)
```

**Outdoor with WPNav + runtime speed adjustment:**
```python
# Uses setpoint_outdoor.yaml automatically (pose_source=GPS, guid_options=65 → WPNav)
drone.move_to(x=5.0, y=0.0, z=0.0, method=NavigationMethod.POSITION)

# Slow down for precise approach
drone.set_speed(0.5, "horizontal")
drone.move_to(x=1.0, y=0.0, z=0.0, method=NavigationMethod.POSITION, precision=0.2)
```

## ArduPilot-Specific Features

### Flight Modes

```python
drone.set_mode("GUIDED")     # Offboard control
drone.set_mode("STABILIZE")  # Manual stabilized
drone.set_mode("LOITER")     # Position hold
drone.set_mode("RTL")        # Return to launch
drone.set_mode("LAND")       # Auto land
```

### Parameter Setting

Supports both integer and float values. Uses `integer_value` for `int`, `double_value` for `float`.

```python
drone.set_param("RTL_ALT", 1500)           # int: RTL altitude in cm
drone.set_param("WPNAV_SPEED", 200.0)      # float: 200 cm/s horizontal
drone.set_param("GUID_OPTIONS", 65)         # int: bits 0 + 6 (arm from TX + WPNav)
```

### Speed Control

Runtime speed changes via [`MAV_CMD_DO_CHANGE_SPEED`](https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed). Immediately updates AC_PosControl limits.

```python
drone.set_speed(0.5, "horizontal")   # groundspeed (type 0)
drone.set_speed(0.3, "climb")        # climb speed (type 1)
drone.set_speed(0.3, "descent")      # descent speed (type 2)
drone.set_speed(-2, "horizontal")    # revert to WPNAV_SPEED default
```

### Servo Control

Controls auxiliary servo outputs (AUX1-AUX8, mapped to FCU channels 9-16). See [ArduPilot Servo Documentation](https://ardupilot.org/copter/docs/common-servo.html).

```python
drone.do_servo(aux_out=1, pwm_value=1500)  # Servo channel 9
drone.do_servo(aux_out=2, pwm_value=2000)  # Servo channel 10
```

## GPS Utilities

`GPSUtils` provides static methods for GPS navigation, used internally by `MavrosNavigator` and `MavrosDrone` for outdoor operations.

### EGM96 Geoid Correction

GPS altitude (WGS84 ellipsoid) differs from AMSL by the geoid height at a given location. MAVROS setpoint topics expect AMSL altitude. `GPSUtils` uses the [EGM96 geoid model](https://en.wikipedia.org/wiki/EGM96) (5-minute grid, cubic interpolation) to convert:

```
AMSL = GPS_ellipsoid_altitude - geoid_height + relative_altitude
```

The EGM96 dataset must be installed (provided by [GeographicLib](https://geographiclib.sourceforge.io/)). Can check in the intallation guide.

### API

**create_gps_setpoint**: Creates a `GeoPoseStamped` with AMSL-corrected altitude and heading quaternion.

```python
from nectar.control.mavros.gps_utils import GPSUtils

setpoint = GPSUtils.create_gps_setpoint(
    latitude=-27.1234,
    longitude=-48.4567,
    altitude_rel=15.0,         # Relative altitude above home (meters)
    heading=90.0,              # Heading in degrees (0=North, clockwise)
    initial_altitude=100.0,    # GPS altitude at startup for offset calculation
)
# Returns: GeoPoseStamped with AMSL altitude ready for MAVROS
```

**geoid_height**: Returns the EGM96 geoid height for a coordinate.

```python
height = GPSUtils.geoid_height(latitude=-27.1234, longitude=-48.4567)
```

**check_reached**: Checks if current GPS position is within precision of target using geodesic distance.

```python
reached, distance, alt_diff = GPSUtils.check_reached(
    current_lat, current_lon, current_alt,
    target_lat, target_lon, target_alt,
    precision_radius=0.5,   # Horizontal threshold (meters)
    alt_threshold=0.5,      # Vertical threshold (meters)
)
```

## Service Call Behavior

All MAVROS service calls use `_call_service` with automatic response validation and deadlock-safe execution.

Per [ROS 2 guidelines](https://docs.ros.org/en/humble/How-To-Guides/Sync-Vs-Async.html), we use `call_async()` with a cooperative wait that drives the global executor when no external one is bound to the node, and just sleeps when the user owns spinning (Yasmin singleton, Qt executor, etc.). The wait helper preserves `node.executor` so subscriptions added after a service call still wake the right executor:

```python
future = service.call_async(request)
deadline = time.time() + timeout
while not future.done():
    if time.time() > deadline:
        raise TimeoutError(...)
    self._wait(0.05)  # spin_once with executor-binding restore, or time.sleep
result = future.result()
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sync` | `True` | If True, waits for response using spin loop. If False, returns immediately. |
| `timeout` | `10.0` | Maximum seconds to wait for service availability and response. |

### Response Validation

| Service Type | Field Checked | Failure Condition |
|--------------|---------------|-------------------|
| `SetMode` | `mode_sent` | `False` |
| `CommandBool`, `CommandTOL`, `CommandLong` | `success`, `result` | `success=False` or `result != ACCEPTED` |
| `SetParameters` | `results[].successful` | Any `False` |

### MAV_RESULT Codes

MAVROS command services return [MAVLink MAV_RESULT](https://mavlink.io/en/messages/common.html#MAV_RESULT) codes in the `result` field:

| Code | Name | Description |
|------|------|-------------|
| 0 | `ACCEPTED` | Command executed successfully |
| 1 | `TEMPORARILY_REJECTED` | Command valid but cannot execute now |
| 2 | `DENIED` | Command invalid or not permitted |
| 3 | `UNSUPPORTED` | Command not supported by autopilot |
| 4 | `FAILED` | Command failed to execute |
| 5 | `IN_PROGRESS` | Command being executed |

Failed commands log the result code:
```
[WARN] /mavros/cmd/arming: Failed (Result: DENIED)
```

---

## References

### MAVLink & MAVROS
- [MAVLink Basics](https://ardupilot.org/dev/docs/mavlink-basics.html)
- [MAVLink Protocol](https://mavlink.io/en/)
- [MAV_RESULT Enum](https://mavlink.io/en/messages/common.html#MAV_RESULT)
- [MAV_CMD Commands](https://mavlink.io/en/messages/common.html#mav_commands)
- [MAV_FRAME](https://mavlink.io/en/messages/common.html#MAV_FRAME) — coordinate frame definitions
- [SET_POSITION_TARGET_LOCAL_NED](https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED)
- [SET_GPS_GLOBAL_ORIGIN](https://mavlink.io/en/messages/common.html#SET_GPS_GLOBAL_ORIGIN) — EKF origin for indoor flight
- [MAVROS GitHub](https://github.com/mavlink/mavros)
- [MAVROS ROS2 API](https://docs.ros.org/en/humble/p/mavros/)
- [MAVROS Wiki (ROS1, still useful)](https://wiki.ros.org/mavros)

### ArduPilot
- [ArduPilot Copter Documentation](https://ardupilot.org/copter/)
- [Flight Modes](https://ardupilot.org/copter/docs/flight-modes.html)
- [MAVLink Flight Mode Protocol](https://ardupilot.org/dev/docs/mavlink-get-set-flightmode.html)
- [GUIDED Mode Commands](https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html) — SET_POSITION_TARGET_LOCAL_NED handling
- [Guided Mode](https://ardupilot.org/copter/docs/ac2_guidedmode.html) — GUID_OPTIONS, speed control, WPNav
- [PosControl and Navigation Code Overview](https://ardupilot.org/dev/docs/code-overview-copter-poscontrol-and-navigation.html) — AC_PosControl vs AC_WPNav
- [WPNAV Parameters (v4.6.3)](https://ardupilot.org/copter/docs/parameters-Copter-stable-V4.6.3.html#wpnav-parameters)
- [MAV_CMD_DO_CHANGE_SPEED](https://ardupilot.org/copter/docs/common-mavlink-mission-command-messages-mav_cmd.html#mav-cmd-do-change-speed)
- [Understanding Altitude](https://ardupilot.org/copter/docs/common-understanding-altitude.html)
- [EKF Navigation Filter](https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html)
- [Rangefinders](https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html)
- [Terrain Following](https://ardupilot.org/copter/docs/terrain-following.html)
- [Servo Configuration](https://ardupilot.org/copter/docs/common-servo.html)

### ArduPilot Source Code
- [`mode_guided.cpp`](https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_guided.cpp) — GUIDED mode sub-modes, pva_control_start(), set_pos_NED_m()
- [`AC_WPNav.cpp`](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_WPNav/AC_WPNav.cpp) — WPNav parameter defaults, S-curve trajectory
- [`AC_PosControl.h`](https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_AttitudeControl/AC_PosControl.h) — Position controller PID, speed limits
- [`GCS_MAVLink_Copter.cpp`](https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/GCS_MAVLink_Copter.cpp) — MAV_CMD_DO_CHANGE_SPEED handler, SET_POSITION_TARGET_LOCAL_NED handler

### Vision & Indoor Navigation
- [VIO Tracking Camera (ArduPilot)](https://ardupilot.org/copter/docs/common-vio-tracking-camera.html)
- [ROS VIO Setup Guide](https://ardupilot.org/dev/docs/ros-vio-tracking-camera.html)
- [Indoor Non-GPS Flight (LuckyBird tutorial)](https://discuss.ardupilot.org/t/integration-of-ardupilot-and-vio-tracking-camera-part-2-complete-installation-and-indoor-non-gps-flights/43405)
- [vision_to_mavros](https://github.com/Black-Bee-Drones/vision_to_mavros)
- [Isaac ROS cuVSLAM with RealSense](https://nvidia-isaac-ros.github.io/concepts/visual_slam/cuvslam/tutorial_realsense.html)

### ROS2
- [Sync vs Async Service Clients](https://docs.ros.org/en/humble/How-To-Guides/Sync-Vs-Async.html)
- [ROS2 Executors](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Executors.html)
- [Callback Groups](https://docs.ros.org/en/humble/How-To-Guides/Using-callback-groups.html)
