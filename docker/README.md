# Docker

## Images

| Tag | Contents | PyTorch |
|-----|----------|---------|
| `:latest` | core + control + vision + interface + realsense + oakd | None |
| `:full-cpu` | All above + AI packages | CPU |
| `:full-cu124` | All above + AI packages | CUDA 12.4 |

## Quick Start

```bash
make docker-build       # SDK (no AI, ~5 min)
make docker-run         # auto-selects image, GPU auto-detected
make docker-exec        # open more terminals
```

## Build

```bash
make docker-build                              # SDK (no AI)
make docker-build-full                         # + AI with PyTorch CPU (default)
TORCH_VARIANT=cu124 make docker-build-full     # + AI with PyTorch CUDA 12.4
TORCH_VARIANT=auto  make docker-build-full     # auto-detect CUDA from nvidia-smi
```

### Different ROS distro

```bash
ROS_DISTRO=jazzy make docker-build
ROS_DISTRO=jazzy TORCH_VARIANT=cu124 make docker-build-full
```

### Pinning a specific PyTorch version (advanced)

By default pip resolves the latest torch compatible with the chosen CUDA index.
Override with environment variables:

```bash
TORCH_VERSION=2.7.1 TORCHVISION_VERSION=0.22.1 TORCH_VARIANT=cu124 make docker-build-full
```

## Run

```bash
make docker-run         # shows menu if multiple images exist
make docker-exec        # extra terminal in running container
```

`docker-run` automatically:
- Detects available images (shows menu if multiple)
- Adds `--gpus all` when NVIDIA GPU detected
- Mounts local project into the container (live code editing)
- Mounts X11, cameras (`/dev/video*`), USB, `/dev`
- Enables host networking for ROS2

The local project mount means edits to Python files on the host appear
instantly inside the container (via `--symlink-install`). For C++ or
message changes, run `colcon build` inside the container.

To run with only the baked-in code (no local mount):
```bash
DOCKER_NO_MOUNT=true make docker-run
```

### Windows

**Note:** Windows users cannot use `make` commands or the bash `setup.sh` script. Use the PowerShell helper script instead.

**PowerShell:**
```powershell
.\docker\run_docker_win.ps1 build humble              # Build SDK image
.\docker\run_docker_win.ps1 build jazzy full-cpu      # Build full image with CPU PyTorch
.\docker\run_docker_win.ps1 run humble                 # Run container
.\docker\run_docker_win.ps1 exec                       # Attach to running container
```

The script supports:
- ROS 2 distros: `humble`, `jazzy`, `kilted`
- Build variants: `full-cpu`, `full-cu124` (for full builds)
- Automatic GPU detection (requires Docker Desktop with NVIDIA Container Toolkit)
- Windows X11 display setup for GUI applications

**Note:** For GUI applications on Windows, ensure Docker Desktop is configured to allow X11 forwarding. The script uses `host.docker.internal:0.0` for display.

## GPU

| Hardware | Build command |
|----------|-------------|
| No GPU | `make docker-build-full` |
| NVIDIA GPU | `TORCH_VARIANT=cu124 make docker-build-full` |
| Auto-detect | `TORCH_VARIANT=auto make docker-build-full` |
| Jetson | Use `Dockerfile.jetson` (planned) |
| No AI needed | `make docker-build` |

GPU passthrough (`--gpus all`) is added automatically at run time when `nvidia-smi` is found.
See [Docker GPU docs](https://docs.docker.com/desktop/features/gpu/) for setup.

You can also install CUDA torch inside a running CPU container:
```bash
./scripts/setup.sh pytorch cu124
./scripts/setup.sh python ai
```

## RealSense

RealSense support is opt-in (builds librealsense from source, adds ~15-20 min and ~500 MB).
It is installed in the `sdk` stage, so both `:latest` and `:full` images include it.

```bash
# SDK with RealSense (no AI)
INSTALL_REALSENSE=true make docker-build

# Full with RealSense + AI + GPU
INSTALL_REALSENSE=true TORCH_VARIANT=cu124 make docker-build-full

# With CUDA-accelerated librealsense
INSTALL_REALSENSE=true REALSENSE_CUDA=true TORCH_VARIANT=cu124 make docker-build-full
```

Versions are auto-selected per ROS distro (`scripts/lib/config.sh`):

| ROS 2 Distro | realsense-ros | librealsense | Cameras |
|---|---|---|---|
| Humble | 4.55.1 | v2.55.1 | D435, D435i, D455 |
| Humble (T265) | [4.51.1](https://github.com/realsenseai/realsense-ros/releases/tag/4.51.1) | [v2.53.1](https://github.com/realsenseai/librealsense/releases/tag/v2.53.1) | T265 (discontinued) |
| Jazzy | [4.56.4](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4) | [v2.56.5](https://github.com/realsenseai/librealsense/releases/tag/v2.56.5) | D435, D435i, D455 |
| Kilted | [4.57.2](https://github.com/realsenseai/realsense-ros/releases/tag/4.57.2) | [v2.57.6](https://github.com/realsenseai/librealsense/releases/tag/v2.57.6) | D435, D435i, D455 |

Override versions for specific needs:
```bash
# T265 tracking camera (Humble only, last supported versions)
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 \
  INSTALL_REALSENSE=true make docker-build
```

udev rules and hotplug scripts for D435/D435i/D455/T265 are included for
runtime device access (following the
[VSLAM-UAV](https://github.com/bandofpv/VSLAM-UAV) Docker pattern).

### T265 Tracking Camera (Docker)

The Intel RealSense T265 is discontinued. The last supporting versions are
**librealsense v2.53.1** and **realsense-ros 4.51.1** (Humble only).
Those versions list kernel support for 4.x/5.x, but the build uses
`FORCE_RSUSB_BACKEND=true` (libusb user-space), so **any host kernel works**
including 6.x. Docker provides a clean isolated environment with the
correct library versions without conflicting with newer librealsense on the
host.

**Build** (requires `:humble` base image — built automatically if missing):
```bash
make docker-build-t265
```

This produces `nectar-sdk:humble-t265`. Internally it starts a container
from `:humble`, installs librealsense v2.53.1 + realsense-ros 4.51.1 +
vision_to_mavros, rebuilds the workspace, and commits the result.

**Run** (plug in the T265 first):
```bash
make docker-run   # select the humble-t265 image from the menu
```

The `docker-run` command already passes `--privileged`, `--device=/dev/bus/usb`,
and X11 forwarding, which is sufficient for USB camera access and GUI tools.

**Test inside the container:**
```bash
# Check if the T265 is detected
rs-enumerate-devices

# GUI viewer (requires X11 forwarding)
realsense-viewer

# ROS 2 launch
source /home/ros2_ws/install/setup.bash
ros2 launch realsense2_camera rs_launch.py device_type:=t265

# Full T265 + MAVROS pipeline (vision_to_mavros)
ros2 launch vision_to_mavros t265_all_nodes_launch.py
```

**Host-side udev rule** (optional, for consistent USB permissions):
```bash
# Copy the rules file to the host
sudo cp docker/realsense/99-realsense-libusb-custom.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> **Note:** If `realsense-viewer` fails with OpenGL errors, set
> `LIBGL_ALWAYS_SOFTWARE=1` inside the container for software rendering.

## Gazebo

Gazebo simulation support is opt-in. Installs Gazebo, the `ros_gz` bridge, and the
ArduPilot Gazebo plugin. The correct Gazebo version and install method are selected
automatically per ROS distro (`scripts/lib/config.sh`).

```bash
# SDK with Gazebo (no AI)
INSTALL_GAZEBO=true make docker-build

# Different ROS distro
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build

# Combined with RealSense + AI + GPU
INSTALL_GAZEBO=true INSTALL_REALSENSE=true TORCH_VARIANT=cu124 make docker-build-full
```

Per-distro Gazebo versions:

| ROS 2 Distro | Gazebo | ros_gz method | Notes |
|---|---|---|---|
| Humble | Harmonic | source | apt binary links against Fortress |
| Jazzy | Harmonic | binary | native support |
| Kilted | Ionic | binary | native support |

## Dependency strategy

PyTorch is **not** listed in `pyproject.toml` dependencies. This is intentional:

1. `setup.sh pytorch <variant>` installs torch + torchvision from the correct
   wheel index (CPU or CUDA) and saves a constraints file.
2. `setup.sh python ai` installs the `[ai]` extra **with** that constraints
   file and `--extra-index-url`, so pip never replaces the CUDA wheels with
   generic PyPI ones.

### numpy < 2.0

`numpy>=1.26,<2.0` is enforced in `pyproject.toml` for compatibility with
ROS 2 `cv_bridge` / `vision_opencv` binaries across Humble, Jazzy, and Kilted.
See [vision_opencv#535](https://github.com/ros-perception/vision_opencv/issues/535).

## Docker Installation

### Windows

1. Download the [Docker Desktop installer](https://docs.docker.com/desktop/setup/install/windows-install/#install-from-the-command-line).
2. Open the folder containing the installer in Command Prompt (run as Administrator).
3. Install Docker Desktop using the command line for greater control over installation options:

    ```bash
    start /w "" "Docker Desktop Installer.exe" install -accept-license --installation-dir="D:\Docker\Docker" --wsl-default-data-root="D:\Docker\wsl" --windows-containers-default-data-root="D:\Docker"
    ```

    - This setup allows customization of the installation directory and the default location for WSL (Docker images).
    - Customizing these paths is especially useful if your primary drive (e.g., `C:`) has limited space.

4. Optionally, install [XLaunch](https://sourceforge.net/projects/vcxsrv/) to enable GUI applications in Docker. Configure the `DISPLAY` environment variable in Docker and launch applications with GUI support.

### Linux (Ubuntu)

1. Add Docker’s official GPG key and repository:

    ```bash
    sudo apt-get update
    sudo apt-get install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    ```

2. Download the latest `.deb` file for Docker Desktop from the [official release notes](https://docs.docker.com/desktop/release-notes/).
3. Install Docker Desktop and Docker Engine:

    ```bash
    sudo apt-get update
    sudo apt-get install ./docker-desktop-amd64.deb
    sudo apt-get install docker-ce
    ```
