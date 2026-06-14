# Localization (control/localization)

External-navigation integration for GPS-denied (indoor) flight. Feeds a Visual
SLAM pose to the FCU so EKF3 can estimate position without GPS.

It lives under `control` because it bridges the VSLAM producer to the MAVROS and
MAVLink transports. The pipeline is split into a **producer** (RealSense + Isaac
ROS Visual SLAM, runs in the Isaac container) and a **consumer** (a vision-pose
bridge that forwards the pose to the FCU, runs on the SDK side). They communicate
over host networking with a shared `ROS_DOMAIN_ID`.

## Topology

```mermaid
flowchart LR
  subgraph isaac [Isaac container]
    rs[realsense2_camera infra1/2 + IMU]
    vslam[isaac_ros_visual_slam]
    rs --> vslam
  end
  subgraph sdk [SDK container or host]
    bridge[vision_pose_node backend mavros|mavlink]
    mavros[MAVROS indoor]
  end
  vslam -->|"/visual_slam/tracking/vo_pose_covariance"| bridge
  bridge -->|"mavros: /mavros/vision_pose/pose_cov"| mavros
  bridge -->|"mavlink: VISION_POSITION_ESTIMATE"| fcu[FCU]
  mavros --> fcu
```

## Components

| Part | Path | Role |
|------|------|------|
| Producer launch | `nectar/launch/isaac_vslam_realsense.launch.py` | RealSense + Visual SLAM (Isaac container) |
| Consumer launch | `nectar/launch/vision_pose.launch.py` | MAVROS (optional) + vision-pose bridge |
| MAVROS relay | `control/localization/vision_pose_bridge.py` (`MavrosVisionRelay`) | republish pose to `/mavros/vision_pose/pose_cov` |
| MAVLink bridge | reused from `nectar.control.mavlink.VisionPoseBridge` | send `VISION_POSITION_ESTIMATE` |
| Node | `control/localization/nodes/vision_pose_node.py` | select backend, wire the bridge |
| VSLAM params | `control/localization/config/vslam_realsense.yaml` | RealSense + Visual SLAM tuning |
| MAVROS config | `control/mavros/config/indoor_mavros.yaml`, `indoor_pluginlists.yaml` | indoor MAVROS profile |

## Run

Both sides must share `ROS_DOMAIN_ID` (default `14`, see `scripts/lib/config.sh`).

1. Producer (Isaac container). One self-contained command clones `isaac_ros_common`
   (`release-3.2`), pulls the prebuilt NVCR base, builds the Nectar layer, and
   drops you into the Isaac container with the workspace mounted:

```bash
make isaac-run          # or: ./docker/isaac_vslam/run_docker.sh
# inside the container, start the producer with the baked helper:
nectar-vslam            # = ros2 launch nectar/launch/isaac_vslam_realsense.launch.py
```

2. Consumer (SDK container or host), pick the transport you fly with:

```bash
# MAVROS transport
ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600

# direct pymavlink transport (no MAVROS)
ros2 launch nectar vision_pose.launch.py backend:=mavlink mavlink_url:=udp:127.0.0.1:14551
```

## FCU setup

ArduPilot Non-GPS position estimation expects the vision feed at >= 4 Hz with
EKF3 external-nav sources, e.g. `EK3_SRC1_POSXY=6` (ExternalNav),
`EK3_SRC1_YAW=6`. See
[ArduPilot non-GPS position estimation](https://ardupilot.org/dev/docs/mavlink-nongps-position-estimation.html).

## Backends

- `mavros`: `MavrosVisionRelay` republishes the VSLAM `PoseWithCovarianceStamped`
  (ENU) onto `/mavros/vision_pose/pose_cov`; MAVROS converts to NED for the FCU.
- `mavlink`: `nectar.control.mavlink.VisionPoseBridge` converts ENU->NED and
  sends `VISION_POSITION_ESTIMATE` over a dedicated pymavlink link.

## References

- [Isaac ROS Visual SLAM (isaac_ros_visual_slam)](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_visual_slam/isaac_ros_visual_slam/index.html)
- [Isaac ROS Development Environment](https://nvidia-isaac-ros.github.io/v/release-3.2/concepts/docker_devenv/index.html)
