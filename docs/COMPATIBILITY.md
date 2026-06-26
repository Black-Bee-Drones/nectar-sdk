# Compatibility matrix

What the Nectar SDK supports, and how far each part has been verified, across ROS 2
distributions and platforms. The SDK is modular: a core install pulls ROS base, the
SDK packages, and core Python deps; everything else (control backends, AI, RealSense,
OAK-D, simulation) is an opt-in group. Each module table states how to install it.

This is a living document. Status reflects the most thorough check performed so far;
cells advance as more setups are exercised (e.g. amd64 in CI, a Windows/WSL2 machine).

## How to read it

Two kinds of evidence back this matrix, produced by two commands:

- `make verify` (tier 1) — the image builds, packages are present, modules import, and
  node executables are installed.
- `make verify-functional` (tier 2) — a per-module harness that performs a *real
  operation*: it detects a synthetic ArUco marker, runs a PID step response to
  convergence, completes a MAVLink heartbeat handshake over a loopback, relays a VSLAM
  pose to the FCU, opens the Qt window offscreen, runs a nano-model inference, etc.
  Checks self-skip when a device, GPU, simulator, or optional dependency is absent, so
  the same harness runs in Docker CI and on real hardware. Run a subset with
  `make verify-functional MODULE="vision control"`.

### Legend

| Symbol | Meaning |
|:---:|---|
| `●` | **Functional** — a `verify-functional` check, a SITL run, or a hardware run exercised it (a real operation, not just an import). |
| `◐` | **Build** — the image builds and `make verify` passes (package present, imports, nodes); the functional check has not been recorded on that distribution yet. |
| `○` | **Not yet tested**. |
| `—` | **Not applicable** (the feature or its dependency is not available there). |
| `!` | **Known issue** — see [Notes](#notes). |

ROS 2 distribution implies its Ubuntu base: **Humble** = 22.04, **Jazzy** / **Kilted** =
24.04. The **Jetson** column is JetPack 6.x (L4T, arm64, CUDA), built from
[`docker/Dockerfile.jetson`](../docker/Dockerfile.jetson) on a Humble base.

## Platforms

Base SDK (`nectar`, `nectar_interfaces`, core Python) — builds and `make verify`:

| Platform | Humble | Jazzy | Kilted |
|---|:---:|:---:|:---:|
| Ubuntu amd64 (CI) | ◐ | ◐ | ◐ |
| Ubuntu arm64 (CI) | ◐ | ◐ | ◐ |
| Jetson JetPack 6.x (arm64) | ● | — | — |
| Windows (WSL2 / Docker Desktop) | ○ | ○ | ○ |

amd64 and arm64 are built and `verify`-checked in GitHub Actions
([`_build-verify.yml`](../.github/workflows/_build-verify.yml)), which now also runs the
functional harness; those cells advance to `●` as the runs are recorded. Windows is only
targeted via WSL2 (Ubuntu) or the published Linux image under Docker Desktop; native
Windows is not a target.

## Core runtime

Always installed. ROS 2 executor, custom messages, cv_bridge interop.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| rclpy executor + `nectar_interfaces` round-trip | ● | ◐ | ◐ | ● |
| cv_bridge ↔ numpy (`<2.0` ABI) | ● | ◐ | ◐ | ● |

## Vision

Install: `make python-vision` (algorithms) / camera extras as needed.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| ArUco / color / line / distance (algorithms) | ● | ◐ | ◐ | ● |
| ROS-topic camera (`CameraFactory`) | ● | ◐ | ◐ | ● |
| USB / OpenCV camera | ◐ (1) | ◐ (1) | ◐ (1) | ◐ (1) |
| RealSense D4xx (librealsense from source) | ● (2) | ◐ | ◐ | ● (2) |
| OAK-D (`depthai`) | ● (3) | ◐ (3) | ◐ (3) | ● (3) |
| MediaPipe hand / face | ◐ (4) | ◐ (4) | ◐ (4) | ◐ (4) |

## Control

Install: `make python-control`; backends are opt-in (`make drone-<x>`).

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Vehicle core (PID, navigator, frame transforms) | ● | ◐ | ◐ | ● |
| Direct MAVLink (`pymavlink`) transport | ● | ◐ | ◐ | ● |
| MAVROS backend (ArduPilot / PX4) | ◐ (5) | ◐ (5) | ◐ (5) | ◐ (5) |
| PX4 native uXRCE-DDS | ◐ (5) | ◐ (5) | ◐ (5) | ◐ (5) |
| Crazyflie / Crazyswarm2 | ○ (6) | ○ (6) | ○ (6) | ○ (6) |
| Bebop driver | ◐ (7) | — | — | — |

## Localization (indoor / GPS-denied)

Install: `make python-control`; Isaac container is Jetson-only.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Vision-pose bridge — MAVROS backend | ● | ◐ | ◐ | ● |
| Vision-pose bridge — MAVLink backend | ● | ◐ | ◐ | ● |
| Isaac ROS Visual SLAM (producer) | — | — | — | ● (8) |

## Sensors

Install: `make python-sensors`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Obstacle-mask filter | ● | ◐ | ◐ | ● |
| Rangefinder → MAVLink `DISTANCE_SENSOR` | ● | ◐ | ◐ | ● |
| TF-Luna UART driver | ◐ (9) | ◐ (9) | ◐ (9) | ◐ (9) |

## AI / detection

Install: `make python-ai && make pytorch`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| `nectar-ai` CLI | ● | ◐ | ◐ | ● |
| Detection inference (YOLO / DETR / RF-DETR) | ● (10) | ◐ | ◐ | ● |
| PyTorch CUDA (GPU tensor) | ○ (11) | ○ (11) | ○ (11) | ● |
| Training / segmentation | ◐ | ◐ | ◐ | ◐ |

## Interface

Install: `make python-interface`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Qt6 / PySide6 GUI (offscreen construct) | ● | ◐ | ◐ | ● |
| Full GUI on a display | ◐ (12) | ◐ (12) | ◐ (12) | ◐ (12) |

## Simulation

Install: `make sim-install`. Not part of any published image.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Gazebo + `ros_gz` bridge | ○ (13) | ○ (13) | ○ (13) | ○ (13) |
| ArduPilot SITL flight | ○ (14) | ○ (14) | ○ (14) | — |
| PX4 SITL flight | ○ (14) | ○ (14) | ○ (14) | — |

## Pinned versions

Per-distro versions live in [`scripts/lib/config.sh`](../scripts/lib/config.sh).

| | Humble | Jazzy | Kilted | Jetson |
|---|---|---|---|---|
| librealsense / realsense-ros | v2.55.1 / 4.55.1 | v2.56.5 / 4.56.4 | v2.57.6 / 4.57.2 | v2.55.1 / 4.55.1 (CUDA, RSUSB) |
| Gazebo (`ros_gz`) | Harmonic (source) | Harmonic (binary) | Ionic (binary) | — |
| PyTorch | uv `--torch-backend` (CPU/CUDA) | same | same | JetPack wheels (CUDA) |

## Notes

1. **USB / OpenCV camera**: driver builds and imports; exercising it needs a camera, so it is not run by the harness.
2. **RealSense**: librealsense is built from source (RSUSB backend) at the pinned version; on Jetson it is built with CUDA (RSUSB is required for the D435i IMU on JetPack 6). The `RealSense device` check passes only with a camera attached; package-level state is covered by `make realsense-verify`.
3. **OAK-D**: the `depthai` stack installs and a device enumerates; it has been exercised both natively and in Docker. The harness check needs an OAK-D attached to report `●`.
4. **MediaPipe**: installs and imports; a functional hand/face run needs a sample image and is not part of the harness.
5. **MAVROS / PX4-DDS**: the transport layer is covered (MAVLink handshake is functional); full flight is validated through SITL — see Simulation and `examples/simulation/sitl_test.py`. MAVROS and `px4_msgs` install on demand (`make drone-mavros` / `make drone-px4-dds`).
6. **Crazyflie / Crazyswarm2**: opt-in (`make drone-crazyflie`). Run `make verify-functional crazyflie` after installing; a full sim flight needs `crazyflie_server` with its simulation backend.
7. **Bebop**: source build, Humble-only (the upstream driver targets Humble); flown on a real Bebop 2 historically. Not available on Jazzy/Kilted/Jetson.
8. **Isaac ROS Visual SLAM**: runs only in the Jetson Isaac container (`make isaac-run`, JetPack 6.x / Humble) — a separate image, not the SDK image. The SDK side is the vision-pose bridge above.
9. **TF-Luna**: UART driver builds and imports; reading needs the sensor on a serial port. The filter and the rangefinder→MAVLink path are functionally verified without hardware.
10. **Detection inference**: a `yolov8n` inference runs end to end (CUDA on Jetson). The first run fetches the model weights; offline runs self-skip.
11. **PyTorch CUDA on amd64/arm64**: not yet exercised (no GPU runner in CI); CPU PyTorch on those arches is untested.
12. **Full GUI on a display**: the window is constructed offscreen by the harness; a real display/X session is needed to drive it interactively.
13. **Gazebo**: `ros_gz` packages are present where built; the harness steps a headless world only when `gz` is installed (`make sim-install`). Not yet recorded on any distribution.
14. **SITL flight**: a full autonomous flight is the `examples/simulation/sitl_test.py` suite, which needs the two-terminal simulation running (`make sim-start` + `make sim-bridge`); it is not auto-run by the harness.

## Not covered yet

- **Windows (WSL2 / Docker Desktop)**: not yet exercised.
- **ROS 2 Lyrical (Ubuntu 26.04)**: not supported yet. At time of writing the `mavros` deb is not published for Lyrical and the scientific-Python stack lacks Python 3.14 wheels; the ROS/C++ layer and Gazebo build. Revisit when both land.
- **amd64 functional**: the harness runs in CI on amd64 and arm64; results will replace the `◐` build cells as they are recorded.
