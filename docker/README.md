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
- Mounts X11, cameras (`/dev/video*`), USB
- Enables host networking for ROS2

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
| Jazzy | [4.56.4](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4) | [v2.56.5](https://github.com/realsenseai/librealsense/releases/tag/v2.56.5) | D435, D435i, D455 |
| Kilted | [4.57.2](https://github.com/realsenseai/realsense-ros/releases/tag/4.57.2) | [v2.57.6](https://github.com/realsenseai/librealsense/releases/tag/v2.57.6) | D435, D435i, D455 |

Override versions for specific needs:
```bash
# T265 tracking camera (Humble only, last supported versions)
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 \
  INSTALL_REALSENSE=true make docker-build
```

udev rules and hotplug scripts for D435/D435i/D455 are included for
runtime device access (following the
[VSLAM-UAV](https://github.com/bandofpv/VSLAM-UAV) Docker pattern).

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
