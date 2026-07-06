# Compatibility matrix

What the Nectar SDK supports, and how far each part has been verified, across ROS 2
distributions and platforms. The SDK is modular: a core install pulls ROS base, the
SDK packages, and core Python deps; everything else (control backends, AI, RealSense,
OAK-D, simulation) is an opt-in group. Each module table states how to install it.

This is a living document. Status reflects the most thorough check performed so far;
cells advance as more setups are exercised (e.g. arm64 CI functional, a Windows/WSL2 machine).

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

amd64 is built, `verify`-checked, and **functionally verified** on all three distros
(the [`_build-verify.yml`](../.github/workflows/_build-verify.yml) harness; reproduced
locally with `make ci-local` on the `sdk` image). arm64 is built and `verify`-checked in
CI, with functional coverage on Humble via the Jetson; arm64-CI functional is not yet
recorded. Windows is only targeted via WSL2 (Ubuntu) or the published Linux image under
Docker Desktop; native Windows is not a target.

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
| USB / OpenCV camera[^usb] | ◐ | ◐ | ◐ | ◐ |
| RealSense D4xx (librealsense from source)[^realsense] | ● | ◐ | ◐ | ● |
| OAK-D (`depthai`)[^oakd] | ● | ◐ | ◐ | ● |
| MediaPipe hand / face[^mediapipe] | ◐ | ◐ | ◐ | ◐ |

## Control

Install: `make python-control`; backends are opt-in (`make drone-<x>`).

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Vehicle core (PID, navigator, frame transforms) | ● | ● | ● | ● |
| Direct MAVLink (`pymavlink`) transport | ● | ● | ● | ● |
| MAVROS backend (ArduPilot / PX4)[^mavros] | ◐ | ● | ◐ | ◐ |
| PX4 native uXRCE-DDS[^mavros] | ◐ | ● | ◐ | ◐ |
| Crazyflie / Crazyswarm2[^crazyflie] | ○ | ○ | ○ | ○ |
| Bebop driver[^bebop] | ◐ | — | — | — |

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
| TF-Luna UART driver[^tfluna] | ◐ | ◐ | ◐ | ◐ |

## AI / detection

Install: `make python-ai && make pytorch`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| `nectar-ai` CLI | ● | ● | ● | ● |
| Detection inference (YOLO / DETR / RF-DETR)[^detect] | ● | ● | ◐ | ● |
| PyTorch CUDA (GPU tensor)[^torchcuda] | ○ | ● | ○ | ● |
| Training / segmentation | ◐ | ◐ | ◐ | ◐ |

## Interface

Install: `make python-interface`.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Qt6 / PySide6 GUI (offscreen construct) | ● | ● | ● | ● |
| Full GUI on a display[^gui] | ◐ | ◐ | ◐ | ◐ |

## Simulation

Install: `make sim-install`. Not part of any published image.

| Feature | Humble | Jazzy | Kilted | Jetson |
|---|:---:|:---:|:---:|:---:|
| Gazebo + `ros_gz` bridge[^gazebo] | ○ | ● | ○ | ○ |
| ArduPilot SITL flight[^sitl] | ○ | ● | ○ | — |
| PX4 SITL flight[^sitl] | ○ | ● | ○ | — |

## Pinned versions

Per-distro versions live in [`scripts/lib/config.sh`](../scripts/lib/config.sh).

| | Humble | Jazzy | Kilted | Jetson |
|---|---|---|---|---|
| librealsense / realsense-ros | v2.55.1 / 4.55.1 | v2.56.5 / 4.56.4 | v2.57.6 / 4.57.2 | v2.55.1 / 4.55.1 (CUDA, RSUSB) |
| Gazebo (`ros_gz`) | Harmonic (source) | Harmonic (binary) | Ionic (binary) | — |
| PyTorch | uv `--torch-backend` (CPU/CUDA) | same | same | JetPack wheels (CUDA) |

## How it's verified

Three commands back this matrix; a cell's symbol reflects the deepest tier reached. CI runs tiers 1-2 across distros/arches and the cells above are updated by hand from those results.

| Tier | Command | What it proves |
|------|---------|----------------|
| 1 — Build | `make verify` | The image builds, packages are present, modules import, and node executables are installed. (`make doctor` gives a read-only environment/device/CUDA report.) |
| 2 — Functional | `make verify-functional` | The **pytest** suite under [`nectar/test/`](../nectar/test) (also run by `colcon test`). Each test performs a *real operation* — detect a synthetic ArUco marker, run a PID step response, complete a MAVLink handshake over loopback, relay a VSLAM pose, open the Qt window offscreen, run a nano-model inference. Tests self-skip when a device/GPU/sim/dependency is absent. Subset with `MODULE="vision control"`; hardware/GPU tests opt in via `make verify-hardware`; reproduce per-distro with `make ci-local`. |
| 3 — SITL / integration | `make verify-sitl` | The suite under [`nectar/test/sitl/`](../nectar/test/sitl): a real headless flight (connect, takeoff, move, land) per firmware/protocol (ArduPilot/PX4 over MAVROS, MAVLink, uXRCE-DDS; Crazyflie sim). Opt-in; run where the sim stack is installed (`make sim-install`), not in CI (from-source simulators take ~45-70 min). Backs the Simulation / MAVROS / PX4-DDS rows. |

## Not covered yet

- **ROS 2 Lyrical (Ubuntu 26.04)**: not supported yet. At time of writing the `mavros` deb is not published for Lyrical and the scientific-Python stack lacks Python 3.14 wheels; the ROS/C++ layer and Gazebo build. Revisit when both land.

[^usb]: **USB / OpenCV camera**: driver builds and imports; exercising it needs a camera, so it is not run by the harness.
[^realsense]: **RealSense** (Humble, Jetson): librealsense is built from source (RSUSB backend) at the pinned version; on Jetson it is built with CUDA (RSUSB is required for the D435i IMU on JetPack 6). The `RealSense device` check passes only with a camera attached; package-level state is covered by `make realsense-verify`.
[^oakd]: **OAK-D**: the `depthai` stack installs and a device enumerates; it has been exercised both natively and in Docker. The harness check needs an OAK-D attached to report `●`.
[^mediapipe]: **MediaPipe**: installs and imports; a functional hand/face run needs a sample image and is not part of the harness.
[^mavros]: **MAVROS / PX4-DDS**: the transport layer is covered (MAVLink handshake is functional). Full SITL flights are verified on Jazzy/amd64: ArduPilot-over-MAVROS (`sitl_test.py`: sensors, takeoff, PID nav, RTL ~0.1 m, land) and PX4 over both MAVROS and native uXRCE-DDS (`basic.py`: takeoff, hover, AUTO.LAND). MAVROS and `px4_msgs` install on demand (`make drone-mavros` / `make drone-px4-dds`).
[^crazyflie]: **Crazyflie / Crazyswarm2**: opt-in (`make drone-crazyflie`). The factory/config wiring is covered by the `control` marker (`make verify-functional control`); a full sim flight needs `crazyflie_server` with its simulation backend and is run manually.
[^bebop]: **Bebop**: source build, Humble-only (the upstream driver targets Humble); flown on a real Bebop 2 historically. Not available on Jazzy/Kilted/Jetson.
[^isaac]: **Isaac ROS Visual SLAM**: runs only in the Jetson Isaac container (`make isaac-run`, JetPack 6.x / Humble) — a separate image, not the SDK image. The SDK side is the vision-pose bridge above.
[^tfluna]: **TF-Luna**: UART driver builds and imports; reading needs the sensor on a serial port. The filter and the rangefinder→MAVLink path are functionally verified without hardware.
[^detect]: **Detection inference** (Humble): a `yolov8n` inference runs end to end (CUDA on Jetson, and on a local Jazzy/amd64 GPU). The first run fetches the model weights; offline runs self-skip.
[^torchcuda]: **PyTorch CUDA**: exercised on Jazzy/amd64 with a local GPU (GTX 1650); CI has no GPU runner, and Humble/Kilted amd64 are not yet exercised on a GPU.
[^gui]: **Full GUI on a display**: the window is constructed offscreen by the harness; a real display/X session is needed to drive it interactively.
[^gazebo]: **Gazebo**: `ros_gz` packages are present where built; the harness steps a headless world only when `gz` is installed (`make sim-install`). Recorded on Jazzy/amd64 (headless step passes); other distros not yet.
[^sitl]: **SITL flight**: a full autonomous flight is the `examples/simulation/sitl_test.py` suite (and `examples/control/basic.py` for PX4), which needs the two-terminal simulation running (`make sim-start` + `make sim-bridge`); it is not auto-run by the harness. Recorded on Jazzy/amd64 for ArduPilot (PID nav, RTL) and PX4 over MAVROS + uXRCE-DDS (takeoff, hover, land).
