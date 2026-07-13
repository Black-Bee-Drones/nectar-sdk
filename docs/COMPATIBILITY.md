# Compatibility matrix

What the Nectar SDK supports, and how far each part has been verified, across ROS 2
distributions and platforms. The SDK is modular: a core install pulls ROS base, the
SDK packages, and core Python deps; everything else (control backends, AI, RealSense,
OAK-D, simulation) is an opt-in group. Each module table states how to install it.

This is a living document. Status reflects the most thorough check performed so far;
cells advance as more setups are exercised

## Legend

Each cell's symbol reflects the deepest verification tier reached (see [How it's verified](#how-its-verified)). Rows with a footnote marker carry a caveat at the bottom of the page.

| Symbol | Meaning |
|:---:|---|
| `●` | **Functional** — a `verify-functional` check, a SITL run, or a hardware run exercised it (a real operation, not just an import). |
| `◐` | **Build** — the image builds and `make verify` passes (package present, imports, nodes); the functional check has not been recorded on that distribution yet. |
| `○` | **Not yet tested**. |
| `—` | **Not applicable** (the feature or its dependency is not available there). |

ROS 2 distribution implies its Ubuntu base: **Humble** = 22.04, **Jazzy** / **Kilted** =
24.04. The **Jetson** column is JetPack 6.x (L4T, arm64, CUDA), built from
[`docker/Dockerfile.jetson`](../docker/Dockerfile.jetson) on a Humble base.

## Platforms

Base SDK (`nectar`, `nectar_interfaces`, core Python) — builds and `make verify`:

| Platform | Humble | Jazzy | Kilted |
|---|:---:|:---:|:---:|
| Ubuntu amd64 (CI) | ● | ● | ● |
| Ubuntu arm64 (CI) | ◐ | ◐ | ◐ |
| Jetson JetPack 6.x (arm64) | ● | — | — |
| Windows (WSL2 / Docker Desktop) | ● | ● | ● |

## Core runtime

Always installed. ROS 2 executor, custom messages, cv_bridge interop.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| rclpy executor + `nectar_interfaces` round-trip | ● | ● | ● | ● |
| cv_bridge ↔ numpy (`<2.0` ABI) | ● | ● | ● | ● |

## Vision

Install: `make python-vision` (algorithms) / camera extras as needed.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| ArUco / color / line / distance (algorithms) | ● | ● | ● | ● |
| ROS-topic camera (`CameraFactory`) | ● | ● | ● | ● |
| USB / OpenCV camera[^usb] | ● | ● | ● | ● |
| RealSense D4xx (librealsense from source)[^realsense] | ● | ● | ◐ | ● |
| OAK-D (`depthai`)[^oakd] | ● | ● | ◐ | ● |
| MediaPipe hand / face[^mediapipe] | ● | ● | ● | ◐ |

## Control

Install: `make python-control`; backends are opt-in (`make drone-<x>`).

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Vehicle core (PID, navigator, frame transforms) | ● | ● | ● | ● |
| Direct MAVLink (`pymavlink`) transport[^mavlink] | ● | ● | ● | ● |
| MAVROS backend (ArduPilot / PX4)[^mavros] | ◐ | ● | ● | ◐ |
| PX4 native uXRCE-DDS[^px4dds] | ● | ● | ● | ◐ |
| Crazyflie / Crazyswarm2[^crazyflie] | ● | ● | ● | ○ |
| Bebop driver[^bebop] | ● | ◐ | ◐ | — |

## Localization (indoor / GPS-denied)

Install: `make python-control`; Isaac container is Jetson-only.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Vision-pose bridge — MAVROS backend | ● | ● | ● | ● |
| Vision-pose bridge — MAVLink backend | ● | ● | ● | ● |
| Isaac ROS Visual SLAM (producer)[^isaac] | — | — | — | ● |

## Sensors

Install: `make python-sensors`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Obstacle-mask filter | ● | ● | ● | ● |
| Rangefinder → MAVLink `DISTANCE_SENSOR` | ● | ● | ● | ● |
| TF-Luna UART driver[^tfluna] | ● | ● | ● | ● |

## AI / detection

Install: `make python-ai && make pytorch`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| `nectar-ai` CLI | ● | ● | ● | ● |
| Detection inference (YOLO / DETR / RF-DETR)[^detect] | ● | ● | ◐ | ● |
| Classification inference (YOLO-cls / ViT) | ● | ● | ◐ | ● |
| PyTorch CUDA (GPU tensor)[^torchcuda] | ● | ● | ● | ● |
| Training / segmentation / classification | ● | ● | ◐ | ◐ |

## Interface

Install: `make python-interface`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Qt6 / PySide6 GUI (offscreen construct) | ● | ● | ● | ● |
| Full GUI on a display[^gui] | ● | ● | ● | ● |

## Simulation

Install: `make sim-install`. Not part of any published image.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Gazebo + `ros_gz` bridge[^gazebo] | ● | ● | ● | ○ |
| ArduPilot SITL — MAVROS[^sitl] | ● | ● | ● | — |
| ArduPilot SITL — MAVLink[^sitl] | ● | ● | ● | — |
| PX4 SITL — MAVROS[^sitl] | ◐ | ● | ● | — |
| PX4 SITL — MAVLink[^sitl] | ◐ | ● | ● | — |
| PX4 SITL — uXRCE-DDS[^sitl] | ● | ● | ● | — |

## Pinned versions

Per-distro versions live in [`scripts/lib/config.sh`](../scripts/lib/config.sh).

| | Humble | Jazzy | Kilted | Jetson |
|---|---|---|---|---|
| librealsense / realsense-ros | v2.55.1 / 4.55.1 | v2.56.5 / 4.56.4 | v2.57.6 / 4.57.2 | v2.55.1 / 4.55.1 (CUDA, RSUSB) |
| Micro-XRCE-DDS-Agent | v2.4.2 | v2.4.3 | v3.0.1 | (same as Humble) |
| Gazebo (`ros_gz`) | Harmonic (source) | Harmonic (binary) | Ionic (binary) | — |
| PyTorch | uv `--torch-backend` (CPU/CUDA) | same | same | JetPack wheels (CUDA) |

## How it's verified

Three commands back this matrix; a cell's symbol reflects the deepest tier reached. CI runs tiers 1-2 across distros/arches and the cells above are updated by hand from those results.

| Tier | Command | What it proves |
|------|---------|----------------|
| 1 — Build | `make verify` | The image builds, packages are present, modules import, and node executables are installed. (`make doctor` gives a read-only environment/device/CUDA report.) |
| 2 — Functional | `make verify-functional` | The **pytest** suite under [`nectar/test/`](../nectar/test) (also run by `colcon test`). Each test performs a *real operation* — detect a synthetic ArUco marker, run a PID step response, complete a MAVLink handshake over loopback, relay a VSLAM pose, open the Qt window offscreen, run a nano-model inference. Tests self-skip when a device/GPU/sim/dependency is absent. Subset with `MODULE="vision control"`; hardware/GPU tests opt in via `make verify-hardware`; reproduce per-distro with `make ci-local`. |
| 3 — SITL / integration | `make verify-sitl` | The suite under [`nectar/test/sitl/`](../nectar/test/sitl): a real headless flight (connect, takeoff, move, land) per firmware/protocol. |

## Not covered yet

- **ROS 2 Lyrical (Ubuntu 26.04)**: not supported yet. At time of writing the `mavros` deb is not published for Lyrical and the scientific-Python stack lacks Python 3.14 wheels; the ROS/C++ layer and Gazebo build. Revisit when both land.
