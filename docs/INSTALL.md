# Installation Guide

## Choose your setup

Start from the row that matches your machine:

| Starting point | Do this |
|---|---|
| Fresh machine, no ROS 2 | [From Scratch](#from-scratch-no-ros-2) — one bootstrap command installs ROS 2 + the SDK |
| ROS 2 installed, SDK not cloned | clone into `~/ros2_ws/src`, then [`make setup`](#existing-ros-2-workspace) |
| SDK cloned, nothing installed | `make setup` (opens the setup menu) |
| Deps installed, just no venv yet | re-run `make python-all` (or your modules) — it creates `$WORKSPACE/.venv` |
| Want zero host setup | [Docker](#docker): `make docker-build && make docker-run` |

`make setup` (or `./scripts/setup.sh` with no args) opens an interactive menu — **nothing installs until you choose**. From it: a *Quick setup* (system deps + pick modules + build + verify), *Python modules*, *Drone driver* (mavros / px4 / px4-dds / crazyflie / bebop), *System packages* (skipped when already installed), *ROS 2 environment*, *Build*, *Verify*, *RealSense*. System packages are idempotent, and the MAVROS geoid datasets (GeographicLib) install only with the `mavros` driver — not on every run.

### Then add what your mission needs

| Goal | Commands |
|---|---|
| ArduPilot / PX4 over direct MAVLink (simplest) | `make setup` (pick `control`) then `make drone-mavros` |
| ArduPilot / PX4 over MAVROS | `make setup` (pick `control`) then `make drone-mavros` |
| PX4 over uXRCE-DDS + detection | `make setup` (pick `control ai`) then `make drone-px4-dds` |
| Crazyflie / Bebop | `make drone-crazyflie` / `make drone-bebop` |
| GUI app only | `make python-interface` |
| Simulation (SITL + Gazebo) | [`make sim-install`](#simulation-gazebo--ardupilot--px4-sitl) |

### Flying real hardware

Examples run with `start_driver=False`, so the driver/bridge your mission connects to runs in its own terminal — started with `make driver` (the real-world counterpart of `make sim-bridge`). `make driver-stop` tears them all down. Connection overrides via env: `FCU_URL` / `DEV` / `BAUD` / `PORT` / `IP`.

| Drone | Start the driver/bridge |
|---|---|
| `mavlink` / `px4_mavlink` (direct) | outdoor: nothing — the mission connects itself; indoor: `make driver DRONE=mavlink ENV=indoor` |
| `mavros` / `px4` | `make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600` |
| `px4-dds` | `make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600` (or `PORT=8888` for UDP) |
| `bebop` | `make driver-bebop IP=192.168.42.1` |
| `crazyflie` | `make driver-crazyflie` |

#### Worked example: ArduPilot/PX4 over direct MAVLink — a 2 m square

Direct MAVLink is the simplest path: the mission opens the link itself, so **outdoor needs no separate bridge**.

```bash
make setup                 # guided — choose: control
make drone-mavros          # MAVROS + GeographicLib (provides the mavlink deps + geoid)
nectar-activate            # enter the SDK Python env

# Outdoor (GPS): takeoff, fly a 2 m position square, land.
python3 nectar/nectar/examples/control/basic.py \
    --drone mavlink --mode position --side 2.0 --env outdoor \
    --connection serial:///dev/ttyUSB0:921600

# Indoor (GPS-denied): start the vision-pose bridge first, then fly the same square.
make driver DRONE=mavlink ENV=indoor          # Terminal 1: VISION_POSITION_ESTIMATE -> FCU
python3 nectar/nectar/examples/control/basic.py \
    --drone mavlink --mode position --side 2.0 --env indoor    # Terminal 2
```

#### Worked example: Crazyflie — a 0.6 m square

```bash
make drone-crazyflie       # Crazyswarm2 + radio udev rules (set your URI in crazyflies.yaml)
make driver-crazyflie      # Terminal 1: Crazyflie server
nectar-activate            # Terminal 2:
python3 nectar/nectar/examples/control/basic.py \
    --drone crazyflie --mode position --height 0.5 --side 0.6
```

#### Worked example: PX4 (uXRCE-DDS) + an object detector

```bash
make setup                 # guided — choose: control ai   (installs PyTorch too)
make drone-px4-dds         # px4_msgs + Micro XRCE-DDS Agent (real hardware; no SITL)
make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # Terminal 1: DDS bridge to the FCU
nectar-activate            # Terminal 2:
python3 nectar/nectar/examples/control/basic.py --drone px4_dds
#   in code: from nectar.ai.detection import Detector; Detector("yolov8n.pt")
```

Prefer no host setup? Use the container image instead:

```bash
make docker-build-full     # SDK + PyTorch + AI
make docker-run            # GPU/cameras/USB auto-wired
```

## From Scratch (no ROS 2)

A standalone bootstrap script installs everything on a fresh Ubuntu/Debian machine: system packages, ROS 2, MAVROS, GeographicLib, git/SSH, the SDK itself, Python dependencies, and builds the workspace.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)
```

The bootstrap prompts for workspace path (default `~/ros2_ws`) and branch (main or dev), then clones the repo and delegates to `./scripts/setup.sh full-install`.

For CI/Docker (non-interactive):

```bash
NON_INTERACTIVE=true ROS2_WORKSPACE=~/ros2_ws bash scripts/bootstrap.sh
```

### Setup menu

Running the setup script with no arguments opens the same interactive menu as `make setup` (configure modules, drivers, system packages, ROS env, build, verify — nothing runs until you pick):

```bash
./scripts/setup.sh
```

## Existing ROS 2 Workspace

Clone into your workspace and open the setup menu:

```bash
cd ~/ros2_ws/src
git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
make setup
```

The menu's **Quick setup** runs: `system` (idempotent) → `git-lfs` → **module selection** (`cmd_python` for the modules you pick; PyTorch first if you choose AI) → `rosdep-init` → `ros2-deps` → `build-pkg` → `verify`. GeographicLib is not part of this — it installs with the `mavros` driver. Non-interactively (`NON_INTERACTIVE=true`, e.g. CI) `make setup` skips the menu and runs Quick setup with `all`.

## Python Environment

Python dependencies install into a single shared virtual environment, managed by [uv](https://github.com/astral-sh/uv), at `$WORKSPACE/.venv` (e.g. `~/ros2_ws/.venv`). `uv` is installed automatically if missing.

- **Created automatically** on the first `make python*` / `make setup`, with `--system-site-packages` so ROS 2 (`rclpy`, message bindings, `colcon`) stays visible inside it.
- **Activation is opt-in.** The SDK's own commands (`make build`, `make verify`, `make python*`, `make pytorch`) use the venv internally, so they always work. For your interactive shell it is **not** force-activated — that keeps it out of the way of your other projects and workspaces. `make ros2-env` installs a `nectar-activate` command for when you want it.
- **Reused by the whole workspace.** Every package under `src/` — the SDK and your own mission/competition code — shares this one venv, so you install once and `import nectar` from anywhere. No per-project venv needed.

Enter it when you need it (e.g. to run `ros2 run nectar <node>` or your own scripts); the prompt then shows `(nectar)`:

```bash
nectar-activate            # enter the SDK env (command added by `make ros2-env`)
deactivate                 # leave it (shell built-in)
uv pip install <package>   # add a package (fast); plain `pip install` also works
```

Prefer it always active? Add one line to `~/.bashrc`:

```bash
source ~/ros2_ws/.venv/bin/activate
```

Override the location with `NECTAR_VENV=/path` (an already-active `VIRTUAL_ENV` is respected). One caveat: always let the SDK create the venv (it pins it to the ROS `python3`); a manual `uv venv` may pick a newer Python without wheels for some deps (e.g. `mediapipe`).

## Install by Module

Install only the modules you need (dependencies defined in `nectar/pyproject.toml`):

```bash
make python-control    # GPS, PID, MAVROS navigation
make python-vision     # Camera drivers, ArUco, color, line detection
make python-ai         # YOLO, DETR, RF-DETR (requires PyTorch)
make python-interface  # Qt6 / PySide6 GUI
make python-sensors    # pyserial + pymavlink (TF-Luna driver, MAVLink bridge)
```

Or via the setup script directly:

```bash
./scripts/setup.sh python              # Core only (numpy, opencv, scipy)
./scripts/setup.sh python control      # + GPS, PID, navigation
./scripts/setup.sh python vision       # + ArUco, color, line detection
./scripts/setup.sh python ai           # + YOLO, Transformers, RF-DETR
./scripts/setup.sh python interface    # + PySide6 GUI
./scripts/setup.sh python sensors      # + pyserial / pymavlink
./scripts/setup.sh python all          # All modules
./scripts/setup.sh python full         # All + camera hardware drivers
```

## Install by Drone Driver

Each drone type needs its own driver; install only the ones you use (defined in `scripts/lib/drones.sh`):

```bash
make drone-mavros      # MAVROS (ArduPilot) + GeographicLib datasets
make drone-px4         # PX4 over MAVROS (reuses MAVROS, launched with px4.launch)
make drone-crazyflie   # Crazyswarm2 (apt when available, else source) + rowan
make drone-bebop       # Parrot Bebop 2: ros2_parrot_arsdk + ros2_bebop_driver (source build)
make drone-all         # all of the above
```

## PyTorch (required for AI module)

Installed via uv's native PyTorch integration (`--torch-backend`), which detects your CUDA driver and pulls torch plus its `nvidia-*` CUDA wheels from the correct `download.pytorch.org` index:

```bash
make pytorch                           # auto-detect GPU (CUDA 13 -> cu130; no GPU -> cpu)
./scripts/setup.sh pytorch cpu         # force CPU
./scripts/setup.sh pytorch cu128       # force a backend (cpu/cu118/cu126/cu128/cu130/...)
```

A known-good `torch`/`torchvision` pair is pinned by default in [`scripts/lib/config.sh`](../scripts/lib/config.sh) for reproducibility; override with `TORCH_VERSION` / `TORCHVISION_VERSION` (set both together). Large CUDA wheels on slow links can stall — the per-request timeout is raised to 600s (`UV_HTTP_TIMEOUT`); on very flaky networks also `export UV_CONCURRENT_DOWNLOADS=1`. See [PyTorch Get Started](https://pytorch.org/get-started/locally/) and the [uv PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/).

## RealSense

Builds librealsense from source with optional CUDA and installs realsense-ros:

```bash
make realsense
```

Interactive menu with custom steps, CUDA auto-detection, and verification.

Per-distro `realsense-ros` / `librealsense` versions are auto-selected from `scripts/lib/config.sh`; the table and Docker RealSense options live in [`docker/README.md`](../docker/README.md#realsense). Override for a specific camera (e.g. the discontinued T265):

```bash
# T265 tracking camera (last supported: Humble only)
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense
```

On NVIDIA GPUs librealsense builds with CUDA automatically (detected via `nvcc`); disable with `REALSENSE_CUDA=false make realsense`.

### Indoor navigation (D435i + Isaac ROS Visual SLAM)

Indoor (GPS-denied) navigation is built into the SDK's [localization module](../nectar/nectar/control/localization/README.md): RealSense + Isaac ROS Visual SLAM (Jetson) feeding the FCU via MAVROS or direct MAVLink. The Isaac container is managed by [`docker/isaac_vslam`](../docker/isaac_vslam) (`make isaac-run`); see [`docker/README.md`](../docker/README.md#isaac-ros-visual-slam-jetson) for the producer container and the localization README for the full pipeline.

## Simulation (Gazebo + ArduPilot / PX4 SITL)

One install command per firmware. ArduPilot pulls ArduCopter SITL + Gazebo +
the `ros_gz` bridge + the ArduPilot Gazebo plugin (auto-selecting the Gazebo
version per ROS distro; per-distro table in
[`docker/README.md`](../docker/README.md#gazebo)). PX4 pulls PX4-Autopilot +
Gazebo and symlinks the Nectar shared assets into the PX4 tree.

```bash
make sim-install FIRMWARE=ardupilot   # ArduCopter SITL + Gazebo + plugin
make sim-install FIRMWARE=px4          # PX4 SITL + Gazebo + Nectar assets
make sim-install FIRMWARE=all          # both
```

### Docker with Gazebo

```bash
INSTALL_GAZEBO=true make docker-build
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

See [`docker/README.md`](../docker/README.md) for more options.

### Running the simulation

Two terminals, the same pattern for both firmwares: the simulator (terminal 1)
+ the ROS stack (terminal 2). Choose `FIRMWARE`/`ENV`/`PROTOCOL`
(defaults: `ardupilot` / `outdoor` / `mavros`):

```bash
# ArduPilot outdoor over MAVROS (the default)
make sim-start   ;  make sim-bridge
# ArduPilot outdoor over direct MAVLink
make sim-start FIRMWARE=ardupilot ENV=outdoor ; make sim-bridge FIRMWARE=ardupilot ENV=outdoor PROTOCOL=mavlink
# ArduPilot indoor (vision)
make sim-start FIRMWARE=ardupilot ENV=indoor  ; make sim-bridge FIRMWARE=ardupilot ENV=indoor
# PX4 outdoor over MAVROS
make sim-start FIRMWARE=px4 ENV=outdoor       ; make sim-bridge FIRMWARE=px4 ENV=outdoor
# PX4 indoor (onboard VIO)
make sim-start FIRMWARE=px4 ENV=indoor        ; make sim-bridge FIRMWARE=px4 ENV=indoor
make sim-stop                                  # stop everything (both firmwares)
```

See the [Simulation guide](../nectar/simulation/README.md) for the full matrix, the vision pipeline, and the automated test suite.

## Real-hardware drivers

The real-world counterpart of `sim-bridge`: start the driver/bridge your mission connects to (examples run with `start_driver=False`), then run the mission in a second terminal. `make driver-stop` stops them all.

```bash
make driver DRONE=mavros ENV=outdoor FCU_URL=serial:///dev/ttyUSB0:921600   # ArduPilot/PX4 MAVROS
make driver DRONE=px4    ENV=outdoor FCU_URL=udp://:14540@127.0.0.1:14580   # PX4 over MAVROS
make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # PX4 uXRCE-DDS agent (or PORT=8888 for UDP)
make driver DRONE=mavlink ENV=indoor               # direct-MAVLink indoor vision-pose bridge
make driver-bebop IP=192.168.42.1                  # Bebop driver
make driver-crazyflie                              # Crazyflie server (Crazyswarm2)
make driver-stop                                   # stop all drivers/bridges
```

Per-type shortcuts exist for each (`make driver-mavros`, `driver-px4`, ...). Connection overrides: `FCU_URL` (MAVROS / vision-pose), `DEV`/`BAUD` or `PORT` (px4-dds agent), `IP` (Bebop). Direct-MAVLink outdoor needs no bridge — the mission opens the link itself. See the [flying real hardware](#flying-real-hardware) worked examples above.

## System Setup (individual steps)

```bash
./scripts/setup.sh system          # apt packages
./scripts/setup.sh ros2            # ROS2 + MAVROS
./scripts/setup.sh geographiclib   # GeographicLib datasets
./scripts/setup.sh ros2-env        # Configure ~/.bashrc
./scripts/setup.sh rosdep-init     # Initialize rosdep
./scripts/setup.sh git-ssh         # Configure git and SSH keys
```

## Build & Verify

```bash
make build              # Build entire workspace
make build-pkg          # Build SDK packages only
make verify             # Check installation (presence/imports)
make doctor             # Environment report (ROS, modules, devices, CUDA)
make clean              # Remove build artifacts
make verify-functional  # Functional regression tests (pytest; MODULE="vision control")
make test               # colcon test (functional suite + cmake/xml lint)
```

## Docker

| Tag | Command | What's included |
|-----|---------|----------------|
| `:humble` | `make docker-build` | All modules except AI/torch (~5 min) |
| `:humble-full-cpu` | `make docker-build-full` | Everything + PyTorch CPU + AI (~15 min) |
| `:jetson` / `:jetson-full` | `make docker-build` / `-full` on a Jetson | L4T build, CUDA wheels; auto-detected |

```bash
make docker-build           # SDK (no AI)
make docker-build-full      # Full (+ AI)
make docker-run             # Run with X11, cameras, USB
make docker-exec            # Extra terminal in running container
```

On a Jetson, these auto-select [`Dockerfile.jetson`](../docker/Dockerfile.jetson) and `--runtime nvidia`. See [`docker/README.md`](../docker/README.md) for GPU, RealSense, and advanced options.

## All Commands

```bash
./scripts/setup.sh help
# or
make help
```

## Changing Versions

All versions and package lists are defined in a single file:

```
scripts/lib/config.sh
```

Edit this file to update ROS distro, PyTorch version, librealsense version, apt package lists, etc. All scripts, Makefile, and Dockerfile read from this file.

## Troubleshooting

### ROS2 not found

```bash
source /opt/ros/humble/setup.bash
```

### Package not found after build

```bash
source ~/ros2_ws/install/local_setup.bash
```

### Camera permission denied

```bash
sudo usermod -a -G video $USER
# Logout and login
```

### MAVROS connection issues

```bash
sudo usermod -a -G dialout $USER
# Logout and login
```
