# Docker

## Images

x86_64 images (`Dockerfile`) are tagged by ROS distro (`nectar-sdk:<distro>`), e.g. `:humble`, `:jazzy`, `:kilted`; AI variants append `-full-<torch>`. Jetson images (`Dockerfile.jetson`) are tagged `:jetson` / `:jetson-full` — see [Jetson (Orin)](#jetson-orin).

| Tag | Contents | PyTorch |
|-----|----------|---------|
| `:humble` | core + control + vision + interface + realsense + oakd + mavros + crazyflie | None |
| `:humble-t265` | All above + librealsense v2.53.1 + T265 support | None |
| `:humble-full-cpu` | All above + AI packages | CPU |
| `:humble-full-cu126` | All above + AI packages | CUDA 12.6 |
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
TORCH_VARIANT=cu126 make docker-build-full     # + AI with PyTorch CUDA 12.6
TORCH_VARIANT=auto  make docker-build-full     # auto-detect CUDA from nvidia-smi
```

### Different ROS distro

```bash
ROS_DISTRO=jazzy make docker-build
ROS_DISTRO=jazzy TORCH_VARIANT=cu126 make docker-build-full
```

### Pinning a specific PyTorch version (advanced)

By default pip resolves the latest torch compatible with the chosen CUDA index.
Override with environment variables:

```bash
TORCH_VERSION=2.9.1 TORCHVISION_VERSION=0.24.1 TORCH_VARIANT=cu126 make docker-build-full
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
.\docker\run_docker_win.ps1 build jazzy full-cu126 -Realsense   # + librealsense (~15-20 min)
.\docker\run_docker_win.ps1 test jazzy full-cu126
.\docker\run_docker_win.ps1 run jazzy full-cu126                # GUI + GPU + USB bus
.\docker\run_docker_win.ps1 exec
```

The script supports:

- ROS 2 distros: `humble`, `jazzy`, `kilted`
- Build variants: `full-cpu`, `full-cu126` (for full builds; `cu126` matches default torch 2.9.x pins)
- `-Realsense` on `build` — sets `INSTALL_REALSENSE=true` (librealsense + realsense-ros from source)
- Automatic GPU detection (requires Docker Desktop with NVIDIA Container Toolkit)
- GUI via [VcXsrv](https://sourceforge.net/projects/vcxsrv/) / XLaunch (`DISPLAY=host.docker.internal:0.0`)
- USB via [usbipd-win](https://github.com/dorssel/usbipd-win) (`usb` subcommand; see below)

#### GUI (VcXsrv)

1. Install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) and run **XLaunch**.
2. **Multiple windows**, display **0**, **Start no client**.
3. Enable **Disable access control** (required).
4. Start XLaunch **before** `run`. Uncheck **Native opengl** if the Qt window is blank.

```powershell
.\docker\run_docker_win.ps1 run jazzy full-cu126
# inside container:
ros2 run nectar app.py
```

#### USB cameras and RealSense

Docker Desktop does not pass USB devices through natively ([Docker FAQ](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/general/#can-i-pass-through-a-usb-device-to-a-container)). Use **usbipd-win** to share devices with the `docker-desktop` WSL VM, then mount `/dev/bus/usb` into the container (the `run` command does this by default).

**Install usbipd-win** ([releases](https://github.com/dorssel/usbipd-win/releases)), then:

```powershell
.\docker\run_docker_win.ps1 usb list
```

| Device | Windows Docker | Notes |
|--------|----------------|-------|
| **Intel RealSense D435i** | Supported (with setup) | Uses libusb (RSUSB); does **not** need `/dev/video*`. Rebuild with `-Realsense`. |
| **Built-in / USB webcam** | Limited | USB attaches and `lsusb` sees the device, but the Docker Desktop WSL kernel often lacks the UVC driver — `/dev/video0` may not appear, so OpenCV `webcam` / `VideoCapture(0)` fails. Use RealSense or native Linux for webcam workflows. |

**RealSense workflow:**

```powershell
# 1) One-time bind (admin PowerShell) — or use: .\run_docker_win.ps1 usb bind realsense
usbipd bind --busid <BUSID>    # from: .\run_docker_win.ps1 usb list

# 2) Attach before each session (re-attach after unplug with -AutoAttach)
.\docker\run_docker_win.ps1 usb attach realsense -AutoAttach

# 3) Rebuild image with RealSense stack (once, ~15-20 min extra)
.\docker\run_docker_win.ps1 build jazzy full-cu126 -Realsense

# 4) Probe inside container
.\docker\run_docker_win.ps1 -Command usb -UsbAction check -Distro jazzy -Variant full-cu126

# 5) Run and test
.\docker\run_docker_win.ps1 run jazzy full-cu126
```

Inside the container:

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
source /home/ros2_ws/install/local_setup.bash
rs-enumerate-devices
ros2 launch realsense2_camera rs_launch.py
```

While a device is attached to WSL it is **exclusive** — Windows apps cannot use it until `usbipd detach`.

**Webcam (experimental):** `usb attach webcam` shares the device, but without `/dev/video*` OpenCV cannot open it. If video nodes appear (`usb list` shows them under docker-desktop), `run` auto-adds `--device` flags.

Pass `-NoUsb` on `run` to skip USB volume mounts.

**Note:** For GUI applications on Windows, ensure VcXsrv is running with access control disabled.

## GPU

| Hardware | Build command |
|----------|-------------|
| No GPU | `make docker-build-full` |
| NVIDIA GPU | `TORCH_VARIANT=cu126 make docker-build-full` |
| Auto-detect | `TORCH_VARIANT=auto make docker-build-full` |
| Jetson (Orin) | `make docker-build-full` (auto-detected → `Dockerfile.jetson`) |
| No AI needed | `make docker-build` |

GPU passthrough is added automatically at run time: `--gpus all` on x86_64 when `nvidia-smi` is found, `--runtime nvidia` on Jetson.
See [Docker GPU docs](https://docs.docker.com/desktop/features/gpu/) for setup.

You can also install CUDA torch inside a running CPU container:

```bash
./scripts/setup.sh pytorch cu126
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

**Published set** (MAVROS + Crazyflie):

```bash
INSTALL_DRONE="mavros crazyflie" make docker-build
```

**MAVLink/pymavlink only** (default):

```bash
make docker-build
```

Bebop is not a default (source build, Humble-only); add it with
`INSTALL_DRONE="mavros crazyflie bebop"`, or `make drone-bebop` at runtime.
PX4 over MAVROS needs `mavros`; PX4 native uXRCE-DDS is part of the simulation install.

## RealSense

RealSense support is opt-in (builds librealsense from source, adds ~15-20 min and ~500 MB).
It is installed in the `sdk` stage, so both the base (`:<distro>`) and full (`:<distro>-full-*`) images include it.

**SDK with RealSense** (no AI):

```bash
INSTALL_REALSENSE=true make docker-build
```

**Full with RealSense + AI + GPU**:

```bash
INSTALL_REALSENSE=true TORCH_VARIANT=cu126 make docker-build-full
```

**With CUDA-accelerated librealsense**:

```bash
INSTALL_REALSENSE=true REALSENSE_CUDA=true TORCH_VARIANT=cu126 make docker-build-full
```

Versions are auto-selected per ROS distro (`scripts/lib/config.sh`). Default D4xx
librealsense / realsense-ros pins per distro are in
[COMPATIBILITY.md](../docs/COMPATIBILITY.md#pinned-versions).

**T265 (Humble only, discontinued):** librealsense **v2.53.1** and realsense-ros **4.51.1**.
Override at build time:

```bash
# T265 tracking camera (Humble only, last supported versions)
LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 \
  INSTALL_REALSENSE=true make docker-build
```

udev rules and hotplug scripts for D435/D435i/D455/T265 are included for
runtime device access (following the
[VSLAM-UAV](https://github.com/bandofpv/VSLAM-UAV) Docker pattern).

### T265 Tracking Camera (Docker)

Uses the T265 override versions above. The build uses `FORCE_RSUSB_BACKEND=true` (libusb
user-space), so any host kernel works including 6.x. Docker keeps those legacy versions isolated
from newer librealsense on the host.

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

> **Note:** If `realsense-viewer` fails with OpenGL errors, set `LIBGL_ALWAYS_SOFTWARE=1` inside the
> container for software rendering.

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
`nectar-vslam` helper). `run_dev.sh` supplies all device/GPU/X11/Jetson config
(`--privileged`, `--runtime nvidia`, tegra mounts, `-e ROS_DOMAIN_ID`); the wrapper adds
`-v /dev/bus/usb:/dev/bus/usb` so the RealSense stays visible across USB re-enumerations.

> **Note — First build takes ~40-50 min on an Orin Nano:** It compiles librealsense from source;
> later runs are cached.
> **Note — Why the RSUSB backend (do not apt-install `realsense2-camera`):** The RSUSB backend is
> required for the D435i IMU on JetPack 6, which removed the `hiddraw` kernel support the apt
> `realsense2-camera` build relies on (otherwise `No HID info provided, IMU is disabled`).
> Apt-installing `realsense2-camera` in `Dockerfile.nectar` would pull that broken kernel-HID build
> over the source one.
> **Warning — Device mounts: bind `/dev/bus/usb`, never all of `/dev`:** With `--privileged` alone
> the container's `/dev` is a static snapshot taken at creation, so the camera's nodes — recreated on
> USB enumeration/reset after the container starts — never appear; the `/dev/bus/usb` bind mount is
> a live view of the host that survives re-enumerations. Do not mount all of `/dev` (`-v /dev:/dev`):
> it shadows the GPU device nodes `--runtime nvidia` injects, and since `run_dev.sh` runs cuVSLAM as
> the non-root `admin` user, the CUDA memory-pool init then fails with `cudaErrorNotSupported` /
> `setCUDAMemoryPoolSize Error: GXF_FAILURE` (works as root, fails as `admin`).

**Start (or enter) the Isaac container** — clone + build (if needed) + enter:

```bash
make isaac-run        # or: ./docker/isaac_vslam/run_docker.sh
```

**Inside the container, start the producer** with the baked helper:

```bash
nectar-vslam          # = ros2 launch nectar/launch/isaac_vslam_realsense.launch.py
```

> **Warning — Run only one cuVSLAM container at a time:** The container uses `--ipc=host` and
> `--pid=host`, so if cuVSLAM crashes the dead GXF process leaves a robust mutex in shared memory
> that aborts the next launch with `cudaErrorNotSupported` / `setCUDAMemoryPoolSize Error` and a
> `pthread ... ESRCH` assertion. Recover by removing the container (which `run_dev.sh` would
> otherwise re-attach to):
>
> ```bash
> make isaac-stop       # docker rm -f the nectar (and old isaac) containers
> make isaac-run        # fresh container; cuVSLAM initializes cleanly
> ```

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
localization pipeline via the indoor Gazebo sim instead (see the
[Simulation module](../nectar/simulation/README.md)), which exercises the same
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

**SDK with Gazebo** (no AI):

```bash
INSTALL_GAZEBO=true make docker-build
```

**Different ROS distro**:

```bash
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

**Combined with RealSense + AI + GPU**:

```bash
INSTALL_GAZEBO=true INSTALL_REALSENSE=true TORCH_VARIANT=cu126 make docker-build-full
```

Per-distro Gazebo versions and `ros_gz` install method (source vs binary) are pinned in
[`config.sh`](../scripts/lib/config.sh) and summarized in
[COMPATIBILITY.md](../docs/COMPATIBILITY.md#pinned-versions).

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

4. For GUI in Docker, install [VcXsrv](https://sourceforge.net/projects/vcxsrv/) (XLaunch: disable access control). For USB cameras / RealSense, install [usbipd-win](https://github.com/dorssel/usbipd-win/releases) — see [Windows USB](#usb-cameras-and-realsense) in this guide.

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
