# Docker

## Images

x86_64 images (`Dockerfile`) are tagged by ROS distro (`nectar-sdk:<distro>`), e.g. `:humble`, `:jazzy`, `:kilted`; AI variants append `-full-<torch>`. Jetson images (`Dockerfile.jetson`) are tagged `:jetson` / `:jetson-full` — see [Jetson (Orin)](#jetson-orin).

| Tag | Contents | PyTorch |
|-----|----------|---------|
| `:humble` | core + control + vision + interface + realsense + oakd + mavros + crazyflie | None |
| `:humble-t265` | All above + librealsense v2.53.1 + T265 support | None |
| `:humble-full-cpu` | All above + AI packages | CPU |
| `:humble-full-cu124` | All above + AI packages | CUDA 12.4 |
| `:jetson` | all non-AI modules (L4T base) | None |
| `:jetson-full` | All above + AI + RealSense (RSUSB) | CUDA 12.6 (Jetson wheels) |

## Quick Start

```bash
make docker-build       # SDK (no AI, ~5 min)
make docker-run         # auto-selects image, GPU auto-detected
make docker-exec        # open more terminals
```

On Jetson, these auto-target `Dockerfile.jetson` (`:jetson` tags) and `--runtime nvidia` — see [Jetson (Orin)](#jetson-orin).

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
| Jetson (Orin) | `make docker-build-full` (auto-detected → `Dockerfile.jetson`) |
| No AI needed | `make docker-build` |

GPU passthrough is added automatically at run time: `--gpus all` on x86_64 when `nvidia-smi` is found, `--runtime nvidia` on Jetson.
See [Docker GPU docs](https://docs.docker.com/desktop/features/gpu/) for setup.

You can also install CUDA torch inside a running CPU container:
```bash
./scripts/setup.sh pytorch cu124
./scripts/setup.sh python ai
```

## Jetson (Orin)

`make docker-build` / `docker-build-full` auto-detect Jetson (Tegra) and build
[`Dockerfile.jetson`](Dockerfile.jetson): an `l4t-jetpack` base with ROS 2 Humble and the SDK;
`-full` adds PyTorch from the [Jetson AI Lab index](https://pypi.jetson-ai-lab.io/jp6/cu126)
(CUDA 12.6) plus the AI stack. Images are tagged `:jetson` / `:jetson-full`.

```bash
make docker-build        # nectar-sdk:jetson
make docker-build-full   # nectar-sdk:jetson-full
make docker-run          # auto-uses --runtime nvidia (Tegra rejects --gpus all)
```

Requires the NVIDIA Container Toolkit. Override the base image or torch index with
`L4T_TAG=` / `TORCH_INDEX=`. This is the SDK image (control/vision/AI); the GPS-denied
VSLAM producer is a separate container — see [Isaac ROS Visual SLAM](#isaac-ros-visual-slam-jetson).

RealSense is opt-in here too (RSUSB backend, required for the D435i IMU on
JetPack 6; CUDA optional). It builds librealsense from source, so the build takes
~40-50 min on an Orin Nano:

```bash
INSTALL_REALSENSE=true REALSENSE_CUDA=true make docker-build-full
```

### Publishing the Jetson image

The x86 CI cannot build the Jetson (L4T) image, so it is published manually from
a Jetson on release. `make docker-publish-jetson` verifies the local image on
this hardware (SDK + `torch.cuda` + RealSense) and pushes only if that passes:

```bash
docker login                                                       # Docker Hub account
INSTALL_REALSENSE=true REALSENSE_CUDA=true make docker-build-full  # complete image
make docker-publish-jetson JETSON_NAMESPACE=blackbeedrones VERSION=v1.1.0
```

This pushes three tags: `:jetson-full-<VERSION>`, `:jetson-full-jp6.2` (JetPack
line — the image only runs on matching JetPack), and `:jetson-full`. Pass
`JETSON_TARGET=sdk` to publish the no-AI image instead.

## Control backends

Control backends are opt-in via the `INSTALL_DRONE` build arg (a space-separated
list of `make drone-<x>` targets). The core image ships MAVLink (`pymavlink`)
only; the published images add `mavros` + `crazyflie`:

```bash
# published set (MAVROS + Crazyflie)
INSTALL_DRONE="mavros crazyflie" make docker-build

# MAVLink/pymavlink only (default)
make docker-build
```

Bebop is not a default (source build, Humble-only); add it with
`INSTALL_DRONE="mavros crazyflie bebop"`, or `make drone-bebop` at runtime.
PX4 over MAVROS needs `mavros`; PX4 native uXRCE-DDS is part of the simulation install.

## RealSense

RealSense support is opt-in (builds librealsense from source, adds ~15-20 min and ~500 MB).
It is installed in the `sdk` stage, so both the base (`:<distro>`) and full (`:<distro>-full-*`) images include it.

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
from `:humble`, installs librealsense v2.53.1 + realsense-ros 4.51.1,
rebuilds the workspace, and commits the result.

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

# Relay the camera pose to the FCU with the SDK vision-pose bridge (replaces the
# external vision_to_mavros). Point input_topic at the T265 pose topic; see
# nectar/nectar/control/localization/README.md.
ros2 launch nectar vision_pose.launch.py backend:=mavros
```

**Host-side udev rule** (optional, for consistent USB permissions):
```bash
# Copy the rules file to the host
sudo cp docker/realsense/99-realsense-libusb-custom.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

> **Note:** If `realsense-viewer` fails with OpenGL errors, set
> `LIBGL_ALWAYS_SOFTWARE=1` inside the container for software rendering.

## Isaac ROS Visual SLAM (Jetson)

The localization pipeline's **producer** (RealSense + Isaac ROS Visual SLAM) runs
in the Isaac ROS dev container. It is separate from the main SDK image because
Isaac ROS is only supported inside its own dev environment (which carries the
NVIDIA Isaac apt repository and the correct CUDA/TensorRT/VPI versions). The SDK
image or host runs the **consumer** side (MAVROS + vision-pose bridge), sharing
`ROS_DOMAIN_ID`.

[`docker/isaac_vslam`](isaac_vslam) is a self-contained wrapper around NVIDIA's
official [`isaac_ros_common/run_dev.sh`](https://nvidia-isaac-ros.github.io/v/release-3.2/concepts/docker_devenv/index.html).
A single command clones `isaac_ros_common` (`release-3.2`) and builds the image
key `ros2_humble.realsense.nectar` bottom-up: the prebuilt NVCR base →
`realsense` (isaac_ros_common's [`Dockerfile.realsense`](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common):
librealsense `v2.55.1` built from source with the **RSUSB/libuvc backend** +
realsense-ros `4.51.1-isaac`) → `nectar`
([`Dockerfile.nectar`](isaac_vslam/Dockerfile.nectar): Visual SLAM + the
`nectar-vslam` helper). The RSUSB backend is **required for the D435i IMU on
JetPack 6**, which removed the `hiddraw` kernel support that the apt
`realsense2-camera` build relies on (otherwise: `No HID info provided, IMU is
disabled`). **First build compiles librealsense (~40-50 min on Orin Nano); later runs
are cached.** Do not apt-install `realsense2-camera` in `Dockerfile.nectar` — it
would pull the broken kernel-HID build over the source one.

`run_dev.sh` supplies all device/GPU/X11/Jetson config (`--privileged`,
`--runtime nvidia`, tegra mounts, `-e ROS_DOMAIN_ID`). The wrapper additionally
bind-mounts `-v /dev/bus/usb:/dev/bus/usb` so the RealSense is visible (the RSUSB
librealsense backend reaches the camera and IMU over libusb). With `--privileged`
alone the container's `/dev` is a static snapshot taken at creation, so the
camera's nodes — (re)created on USB enumeration/reset after the container starts
— never appear; the directory bind mount is a live view of the host that
survives re-enumerations. **Do not mount all of `/dev` (`-v /dev:/dev`):** it
shadows the GPU device nodes `--runtime nvidia` injects, and since `run_dev.sh`
runs cuVSLAM as the non-root `admin` user, the CUDA memory-pool init then fails
with `cudaErrorNotSupported` / `setCUDAMemoryPoolSize Error: GXF_FAILURE` and the
visual_slam container aborts (works as root, fails as `admin`).

```bash
# Producer (Isaac container) - clone + build (if needed) + enter
make isaac-run        # or: ./docker/isaac_vslam/run_docker.sh

# inside the container, start the producer with the baked helper:
nectar-vslam          # = ros2 launch nectar/launch/isaac_vslam_realsense.launch.py
```

Run **only one** cuVSLAM/Isaac container at a time. The container uses `--ipc=host`
+ `--pid=host`, so if cuVSLAM crashes, the dead GXF process leaves a robust
mutex in shared memory that aborts the next launch with `cudaErrorNotSupported`
/ `setCUDAMemoryPoolSize Error` and a `pthread ... ESRCH` assertion. Recover by
removing the container (which `run_dev.sh` would otherwise re-attach to):

```bash
make isaac-stop       # docker rm -f the nectar (and old isaac) containers
make isaac-run        # fresh container; cuVSLAM initializes cleanly
```

Consumer side (SDK image or host), same `ROS_DOMAIN_ID`:

```bash
ros2 launch nectar vision_pose.launch.py backend:=mavros fcu_url:=/dev/ttyTHS1:921600
```

Requirements on the Jetson: Docker (non-root), `git-lfs`, and the NVIDIA Container
Toolkit. For RealSense USB permissions on the host, install the udev rules in
[`docker/realsense`](realsense).

### Hardware requirements (cuVSLAM)

Isaac ROS Visual SLAM (cuVSLAM) has a hard GPU floor, per the official
[compute setup](https://nvidia-isaac-ros.github.io/v/release-3.2/getting_started/hardware_setup/compute/index.html)
and [Visual SLAM](https://nvidia-isaac-ros.github.io/v/release-3.2/repositories_and_packages/isaac_ros_visual_slam/index.html)
pages (release-3.2):

- Jetson: Orin family on JetPack 6.1 / 6.2.
- x86_64: discrete NVIDIA GPU, **Ampere architecture or newer**, **>= 8 GB VRAM**
  (12 GB+ recommended), driver **560+**, CUDA 12.6+, Ubuntu 22.04+.

Pre-Ampere GPUs are **not** compatible with the cuVSLAM library (the maintainers
confirm this for older architectures in
[isaac_ros_visual_slam#117](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_visual_slam/issues/117)).
A GTX 16-series (Turing) or earlier card cannot run the Visual SLAM node. The
container image still **builds and launches** on such hardware (useful to validate
the SDK's Docker wiring), but the cuVSLAM node itself will not run -- test the
localization pipeline via the indoor Gazebo sim instead (see
[simulation/README.md](../nectar/simulation/README.md)), which exercises the same
bridges and topics with no cuVSLAM/Jetson required.

### Version and ROS distro

Isaac ROS ties each release line to one ROS 2 distro and one JetPack, per the
[release notes](https://nvidia-isaac-ros.github.io/releases/index.html):

| Isaac ROS | ROS 2 | Ubuntu | JetPack | CUDA | Build method |
|---|---|---|---|---|---|
| **3.2** (SDK default) | Humble | 22.04 | 6.1 / 6.2 | 12.6 | `isaac_ros_common/run_dev.sh` (this wrapper) |
| 4.x (latest, 4.4) | Jazzy | 24.04 | 7.x | 13.0 | Isaac ROS APT repo + `isaac-ros` CLI |

The SDK pins **`ISAAC_ROS_VERSION=release-3.2`** ([scripts/lib/config.sh](../scripts/lib/config.sh))
because the target Jetson runs JetPack 6.2 (Humble). Isaac ROS 4.x is **not** a
config bump: it requires a JetPack 7 re-flash (Ubuntu 24.04 / Jazzy) and uses a
different toolchain.

#### Migrating to Isaac ROS 4.x (future, requires JetPack 7)

4.x replaces `run_dev.sh` with the [`isaac-ros` CLI](https://github.com/NVIDIA-ISAAC-ROS/isaac-ros-cli)
over an APT repository ([getting started](https://nvidia-isaac-ros.github.io/getting_started/)):

```bash
# 1. Add the Isaac ROS APT repo (noble = Ubuntu 24.04; use noble-jetpack on Jetson)
#    deb https://isaac.download.nvidia.com/isaac-ros/release-4 noble main
sudo apt-get install isaac-ros-cli
sudo isaac-ros init docker        # modes: docker | venv | baremetal
isaac-ros activate
sudo apt-get install ros-jazzy-isaac-ros-visual-slam ros-jazzy-isaac-ros-examples ros-jazzy-isaac-ros-realsense
```

When the team moves to JetPack 7, the producer side (`docker/isaac_vslam`) would
switch to this CLI-based flow with `ros-jazzy-*` packages; the SDK's consumer side
(`vision_pose_node`, launches, configs) is distro-agnostic and unaffected. Note:
the release notes flag RealSense stability issues on JetPack 7 (nvbugs/5561995),
mitigated via the RealSense setup tutorial.

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

### SITL (flight in simulation)

`INSTALL_SIM` builds the autopilot SITL stack (`ardupilot`, `px4`, or `all`) into
the image — heavy, since the autopilots build from source (~1-2 h cold). To
actually fly you also need the matching control backend (`INSTALL_DRONE`):

```bash
# ArduPilot SITL image (MAVROS + direct MAVLink)
INSTALL_SIM=ardupilot INSTALL_DRONE=mavros make docker-build
```

Run the flight suite headless (no GPU needed — uses Mesa software GL):

```bash
docker run --rm --shm-size=1g -e LIBGL_ALWAYS_SOFTWARE=1 nectar-sdk:<distro> \
  bash -lc 'source /opt/ros/$ROS_DISTRO/setup.bash; \
            source /home/ros2_ws/install/local_setup.bash; \
            make verify-sitl FIRMWARE=ardupilot'
```

PX4 needs no mavros (use `INSTALL_SIM=px4`; for uXRCE-DDS add `INSTALL_DRONE=px4-dds`).
On a host you don't need an image at all — `make sim-install` then `make verify-sitl`.

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
