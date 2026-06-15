# Installation Guide

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

### Interactive menu

Run the setup script with no arguments for a guided menu where you can pick individual steps or customize the install:

```bash
./scripts/setup.sh
```

## Existing ROS 2 Workspace

Clone into your workspace and run a single command — it installs system dependencies, GeographicLib, Python packages, rosdep, and builds the SDK packages:

```bash
cd ~/ros2_ws/src
git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
make setup
```

This is equivalent to:

```bash
./scripts/setup.sh setup
```

Which runs: `system` → `geographiclib` → `git-lfs` → `python all` → `rosdep-init` → `ros2-deps` → `build-pkg` → `verify`.

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
make drone-mavros      # MAVROS (ArduPilot/PX4) + GeographicLib datasets
make drone-crazyflie   # Crazyswarm2 (apt when available, else source) + rowan
make drone-bebop       # Parrot Bebop 2: ros2_parrot_arsdk + ros2_bebop_driver (source build)
make drone-all         # all of the above
```

## PyTorch (required for AI module)

```bash
make pytorch                           # Auto-detect GPU
./scripts/setup.sh pytorch cpu         # Force CPU
./scripts/setup.sh pytorch cu124       # Force CUDA 12.4
```

See [PyTorch Get Started](https://pytorch.org/get-started/locally/) for other configurations.

## RealSense

Builds librealsense from source with optional CUDA, installs realsense-ros and vision_to_mavros:

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

## Simulation (Gazebo + ArduPilot SITL)

### ArduPilot SITL

```bash
make sim-install           # Clone ArduPilot, build ArduCopter SITL binary
```

### Gazebo

Installs Gazebo, the `ros_gz` bridge, and the ArduPilot Gazebo plugin. The script
auto-selects the correct Gazebo version and install method per ROS distro (per-distro
table in [`docker/README.md`](../docker/README.md#gazebo)):

```bash
make sim-install-gazebo    # Native install (auto-detects distro)
```

### Docker with Gazebo

```bash
INSTALL_GAZEBO=true make docker-build
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

See [`docker/README.md`](../docker/README.md) for more options.

### Running the simulation

Two terminals: physics (terminal 1) + Gazebo world & ROS stack (terminal 2). Pair the matching row:

```bash
# Outdoor (GPS)
make sim-start-outdoor   ;  make sim-outdoor          # MAVROS
make sim-start-outdoor   ;  make sim-outdoor-direct   # direct MAVLink
# Indoor (no GPS, vision)
make sim-start-indoor    ;  make sim-indoor           # MAVROS
make sim-start-indoor    ;  make sim-indoor-direct    # direct MAVLink
# Headless (no Gazebo)
make sim-start           ;  make sim-mavros
make sim-stop                                          # stop everything
```

See the [Simulation guide](../nectar/simulation/README.md) for the full matrix, the vision pipeline, and the automated test suite.

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
make verify             # Check installation
make clean              # Remove build artifacts
make test               # Run tests
```

## Docker

| Tag | Command | What's included |
|-----|---------|----------------|
| `:humble` | `make docker-build` | All modules except AI/torch (~5 min) |
| `:humble-full-cpu` | `make docker-build-full` | Everything + PyTorch CPU + AI (~15 min) |

```bash
make docker-build           # SDK (no AI)
make docker-build-full      # Full (+ AI)
make docker-run             # Run with X11, cameras, USB
make docker-exec            # Extra terminal in running container
```

See [`docker/README.md`](../docker/README.md) for GPU, RealSense, and advanced options.

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
