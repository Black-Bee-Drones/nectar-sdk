# Compatibility matrix

What of the SDK is known to work on each ROS 2 distribution and platform. The SDK
is modular: a core install pulls only ROS base + the SDK packages + core Python
deps. Everything else (control backends, AI, RealSense, OAK-D, simulation) is an
opt-in group, so an empty cell means "not part of that install", not "broken".

## Method

Evidence is **build + verify**, not hardware-functional testing:

- Build the Docker image for the distro (`docker/Dockerfile`, or `Dockerfile.jetson` on Jetson).
- Run `setup.sh verify` (imports, package presence, node executables) and, where RealSense is built, `setup.sh realsense-verify`.

A cell states whether the dependency stack installs and imports and whether the
SDK nodes are present, not that a camera streamed or a drone flew. Hardware
behaviour is marked separately.

Legend:

- `OK`  built and `verify` passed on this setup
- `opt` optional add-on; installs on demand (apt or source build), not in the core/published image
- `hw`  builds and imports, but exercising it needs the physical device/display
- `n/a` not available for that distro/platform
- `n/t` not tested here

Columns are the setups validated on this machine (aarch64). `amd64` is built and
verified in CI (GitHub Actions) and is not re-run here. Versions are pinned per
distro in [`scripts/lib/config.sh`](../scripts/lib/config.sh).

## Matrix

| Feature | Humble | Jazzy | Kilted | Jetson (JetPack 6.2) |
|---|---|---|---|---|
| SDK build (`nectar`, `nectar_interfaces`) | OK | OK | OK | OK |
| Core Python (numpy, opencv, scipy, cv_bridge) | OK | OK | OK | OK |
| Vision: ArUco / line / color (opencv-contrib) | OK | OK | OK | OK |
| Vision: RealSense camera (librealsense from source) | OK | OK | OK | OK |
| Vision: OAK-D camera (`depthai`) | hw | hw | hw | hw |
| Control core (vehicle, factory, PID) | OK | OK | OK | OK |
| Control: MAVROS backend (ArduPilot / PX4) | opt | opt | opt | opt |
| Control: MAVLink backend (`pymavlink`) | OK | OK | OK | OK |
| Control: PX4 native uXRCE-DDS | opt | opt | opt | opt |
| Control: Crazyflie / Crazyswarm2 | opt | opt | opt | opt |
| Control: Bebop driver (source) | opt | n/t | n/t | n/t |
| Localization: Isaac ROS Visual SLAM | n/a | n/a | n/a | OK |
| Sensors: rangefinder (serial -> MAVLink) | OK | OK | OK | OK |
| Interface: Qt6 / PySide6 GUI | hw | hw | hw | hw |
| AI: detection / segmentation / `nectar-ai` | n/t | n/t | n/t | OK |
| Simulation: Gazebo + SITL | opt | opt | opt | n/a |

RealSense versions actually built and verified: Humble v2.55.1 / 4.55.1, Jazzy
v2.56.5 / 4.56.4, Kilted v2.57.6 / 4.57.2, Jetson v2.55.1 / 4.55.1 (CUDA).
Each `sdk` image above reported `verify` = 45 passed, 0 failed (Jetson `jetson-full`
= 59 passed, including torch CUDA + GPU tensor).

Notes:

- Control backends are opt-in. The core install ships MAVLink (`pymavlink`) only;
  MAVROS, Crazyflie and Bebop install on demand (`make drone-mavros` /
  `drone-crazyflie` / `drone-bebop`; PX4 over MAVROS needs `mavros`; PX4 native
  uXRCE-DDS via `make sim-install FIRMWARE=px4 ARGS=--native`). The published
  Docker images add `mavros` + `crazyflie` via the `INSTALL_DRONE` build arg;
  Bebop is never a default (source build, Humble-only). Verified on a core
  (no-backend) build: no `mavros` present and `verify` passes (mavros is an
  optional warning, `nectar.control` still imports). RealSense no longer pulls
  `mavros` (the SDK's `control.localization` replaces `vision_to_mavros`).
- RealSense is built from source (RSUSB backend), versions pinned per distro; on
  Jetson it is built with CUDA. RSUSB is required for the D435i IMU on JetPack 6.
- Isaac ROS Visual SLAM runs only in the Jetson Isaac container (`make isaac-run`),
  JetPack 6.2 / Humble. It is a separate image, not the SDK image.
- `hw` rows (OAK-D, Qt GUI) install and import (`depthai`, `PySide6` present) but
  need the device/display to exercise.
- AI is verified on Jetson (`jetson-full`: torch CUDA + GPU tensor). The
  Humble/Jazzy/Kilted images here use the `sdk` target (no AI), so the AI stack
  was not exercised on generic arm64 (`n/t`); CPU-torch on amd64/arm64 is untested.

## Not covered

- amd64: built and verified by CI on every push/release; not re-tested on this machine.
- ROS 2 Lyrical (Ubuntu 26.04): not supported yet. At time of writing the `mavros`
  deb is not published for Lyrical and the scientific-Python stack lacks Python 3.14
  wheels. The ROS/C++ layer and Gazebo Jetty build; revisit when both land.
