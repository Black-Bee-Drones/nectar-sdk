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
| Humble / Iron | 4.55.1 | v2.55.1 | D435, D435i, D455 |
| Jazzy | [4.56.4](https://github.com/realsenseai/realsense-ros/releases/tag/4.56.4) | [v2.56.5](https://github.com/realsenseai/librealsense/releases/tag/v2.56.5) | D435, D435i, D455 |
| Kilted | [4.57.2](https://github.com/realsenseai/realsense-ros/releases/tag/4.57.2) | v2.56.5 | D435, D435i, D455 |

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
