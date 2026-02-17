# Installation Guide

## Quick Install (from zero)

For a fresh Ubuntu/Debian machine without ROS2:

```bash
git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
./scripts/setup.sh full-install
```

Or use the interactive menu:

```bash
./scripts/setup.sh
```

The full install covers: system packages, ROS2 Humble, MAVROS, GeographicLib, Python dependencies, workspace build, and bashrc configuration.

## Already Have ROS2 + Workspace

If you already cloned the repo inside a ROS2 workspace (`<workspace>/src/nectar-sdk`):

```bash
# Install Python dependencies (all modules)
./scripts/setup.sh python all

# Build
./scripts/setup.sh build
```

Or via Make:

```bash
make install-all
make build
```

## Module-Specific Installation

Install only the modules you need (dependencies defined in `nectar/pyproject.toml`):

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
# Auto-detect GPU:
./scripts/setup.sh pytorch

# Or explicitly:
./scripts/setup.sh pytorch-cpu         # CPU only
./scripts/setup.sh pytorch-cuda        # CUDA 12.4
```

See [PyTorch Get Started](https://pytorch.org/get-started/locally/) for other configurations.

## RealSense

Builds librealsense from source with optional CUDA, installs realsense-ros and vision_to_mavros:

```bash
./scripts/setup.sh realsense
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
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 ./scripts/setup.sh realsense
```

### CUDA build

On systems with NVIDIA GPU, librealsense is built with CUDA automatically (detected via `nvcc`). Disable with:

```bash
REALSENSE_CUDA=false ./scripts/setup.sh realsense
```

### D435i + Isaac ROS Visual SLAM

For indoor navigation with D435i on Jetson Orin, the SDK includes [vision_to_mavros](https://github.com/Black-Bee-Drones/vision_to_mavros) which bridges NVIDIA Isaac ROS Visual SLAM with MAVROS. See the [VSLAM setup guide](https://www.andrewbernas.com/docs/tutorials/robots/vslam/setup) for the full workflow.

## System Setup (individual steps)

```bash
./scripts/setup.sh system          # apt packages
./scripts/setup.sh ros2            # ROS2 Humble + MAVROS
./scripts/setup.sh geographiclib   # GeographicLib datasets
./scripts/setup.sh ros2-env        # Configure ~/.bashrc
./scripts/setup.sh rosdep-init     # Initialize rosdep
```

## Build & Verify

```bash
./scripts/setup.sh build           # Build entire workspace
./scripts/setup.sh build-pkg       # Build SDK packages only
./scripts/setup.sh verify          # Check installation
./scripts/setup.sh clean           # Remove build artifacts
```

## Docker

| Tag | Command | What's included |
|-----|---------|----------------|
| `:latest` | `make docker-build` | All modules except AI/torch (fast, ~5 min) |
| `:full` | `make docker-build-full` | Everything + PyTorch CPU + AI (~15 min) |

```bash
# Build
make docker-build           # SDK (no AI)
make docker-build-full      # Full (+ AI)

# Run (X11, cameras, USB auto-mounted)
make docker-run
make docker-run-full
```

See [`docker/README.md`](../docker/README.md) for Jetson, CUDA, Docker Hub.

## All Commands

```bash
./scripts/setup.sh help
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
