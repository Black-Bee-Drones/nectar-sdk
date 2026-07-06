# RealSense & indoor navigation

Intel RealSense depth and tracking cameras drive both the vision depth features and GPS-denied
(indoor) flight. This page installs librealsense and realsense-ros; the indoor VSLAM pipeline
builds on top of them.

## Install

Builds librealsense from source and installs realsense-ros. The interactive menu offers custom
steps, CUDA auto-detection, and verification.

```bash
make realsense
```

Per-distro `realsense-ros` / `librealsense` versions are auto-selected from
`scripts/lib/config.sh`; see [COMPATIBILITY.md](../COMPATIBILITY.md#pinned-versions).

!!! tip "CUDA"
    On NVIDIA GPUs librealsense builds with CUDA automatically (detected via `nvcc`). Disable
    it with `REALSENSE_CUDA=false make realsense`.

!!! note "T265 tracking camera (discontinued)"
    The T265 needs the last supporting **librealsense** / **realsense-ros** versions, on Humble
    only:

    ```bash
    LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense
    ```

    That source build also provides matching **pyrealsense2** for T265 direct mode. The pip extra
    `nectar-sdk[realsense]` (PyPI pyrealsense2 ≥2.55) is for D4xx direct mode only — see
    [Cameras](../../nectar/nectar/vision/camera/README.md#t265-tracking-camera).

## Indoor navigation

Indoor (GPS-denied) navigation is built into the SDK's
[Localization module](../../nectar/nectar/control/localization/README.md): a RealSense feeds
Isaac ROS Visual SLAM on a Jetson, which feeds pose to the FCU over MAVROS or direct MAVLink.

The Isaac producer runs in its own container (`make isaac-run`). See the
[Docker guide](../../docker/README.md) for the container and the
[Localization module](../../nectar/nectar/control/localization/README.md) for the full pipeline.
