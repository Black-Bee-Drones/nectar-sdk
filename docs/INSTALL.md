# Installation Guide

## From Scratch (no ROS 2)

A standalone bootstrap script installs everything on a fresh Ubuntu/Debian machine: system packages, ROS 2, MAVROS, GeographicLib, git/SSH, the SDK itself, Python dependencies, and builds the workspace.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)
```

The bootstrap prompts for workspace path (default `~/ros2_ws`) and branch (main or dev), then clones the repo and delegates to `./scripts/setup.sh full-install`.

For CI/Docker (non-interactive):

```bash
NON_INTERACTIVE=true ROS2_WORKSPACE=~/ros2_ws bash bootstrap.sh
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

Which runs: `system` → `geographiclib` → `python all` → `rosdep-init` → `ros2-deps` → `build-pkg` → `verify`.

## Install by Module

Install only the modules you need (dependencies defined in `nectar/pyproject.toml`):

```bash
make python-control    # GPS, PID, MAVROS navigation
make python-vision     # Camera drivers, ArUco, color, line detection
make python-ai         # YOLO, DETR, RF-DETR (requires PyTorch)
make python-interface  # Qt6 / PySide6 GUI
```

Or via the setup script directly:

```bash
./scripts/setup.sh python              # Core only (numpy, opencv, scipy)
./scripts/setup.sh python control      # + GPS, PID, navigation
./scripts/setup.sh python vision       # + ArUco, color, line detection
./scripts/setup.sh python ai           # + YOLO, Transformers, RF-DETR
./scripts/setup.sh python interface    # + PySide6 GUI
./scripts/setup.sh python all          # All modules
./scripts/setup.sh python full         # All + camera hardware drivers
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

### Version compatibility

Versions are auto-selected per ROS distro (defined in `scripts/lib/config.sh`):

| ROS 2 Distro | realsense-ros | librealsense | Cameras |
|---|---|---|---|
| Humble | 4.55.1 | v2.55.1 | D435, D435i, D455 |
| Jazzy | [4.56.4](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4) | [v2.56.5](https://github.com/realsenseai/librealsense/releases/tag/v2.56.5) | D435, D435i, D455 |
| Kilted | [4.57.2](https://github.com/realsenseai/realsense-ros/releases/tag/4.57.2) | [v2.57.6](https://github.com/realsenseai/librealsense/releases/tag/v2.57.6) | D435, D435i, D455 |

Override for specific cameras:

```bash
# T265 tracking camera (last supported: Humble/Foxy only)
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense
```

### CUDA build

On systems with NVIDIA GPU, librealsense is built with CUDA automatically (detected via `nvcc`). Disable with:

```bash
REALSENSE_CUDA=false make realsense
```

### D435i + Isaac ROS Visual SLAM

For indoor navigation with D435i on Jetson Orin, the SDK includes [vision_to_mavros](https://github.com/Black-Bee-Drones/vision_to_mavros) which bridges NVIDIA Isaac ROS Visual SLAM with MAVROS. See the [VSLAM setup guide](https://www.andrewbernas.com/docs/tutorials/robots/vslam/setup) for the full workflow.

## Simulation (Gazebo + ArduPilot SITL)

### ArduPilot SITL

```bash
make sim-install           # Clone ArduPilot, build ArduCopter SITL binary
```

### Gazebo

Installs Gazebo, the `ros_gz` bridge, and the ArduPilot Gazebo plugin. The script
auto-selects the correct Gazebo version and install method per ROS distro:

```bash
make sim-install-gazebo    # Native install (auto-detects distro)
```

| ROS 2 Distro | Gazebo | ros_gz | Notes |
|---|---|---|---|
| Humble | Harmonic | built from source | apt binary links against Fortress |
| Jazzy | Harmonic | binary | native support |
| Kilted | Ionic | binary | native support |

### Docker with Gazebo

```bash
INSTALL_GAZEBO=true make docker-build
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

See [`docker/README.md`](../docker/README.md) for more options.

### Running the simulation

```bash
make sim-start-outdoor     # Start SITL in Gazebo mode (outdoor, terminal 1)
make sim-outdoor           # Launch Gazebo outdoor world + MAVROS (terminal 2)
```

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
