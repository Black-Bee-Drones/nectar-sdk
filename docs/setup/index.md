# Installation

Install the SDK itself here, then add the pieces your mission needs: [drone drivers](drivers.md),
[simulation](simulation.md), [RealSense & indoor](realsense.md), or [Docker](../../docker/README.md). The
tested platform matrix is on the [Compatibility](../COMPATIBILITY.md) page.

## Choose your setup

Start from the row that matches your machine:

| Starting point | Do this |
|---|---|
| Fresh machine, no ROS 2 | [**From scratch** tab](#from-scratch-no-ros-2) — one bootstrap command installs ROS 2 + the SDK |
| ROS 2 installed, SDK not cloned | clone into `~/ros2_ws/src`, then [**Existing workspace** tab](#existing-ros-2-workspace) → `make setup` |
| SDK cloned, nothing installed | `make setup` (opens the setup menu) |
| Deps installed, just no venv yet | re-run `make python-all` (or your modules) — it creates `$WORKSPACE/.venv` |
| Want zero host setup | [Docker](../../docker/README.md): `make docker-build && make docker-run` |

`make setup` (or `./scripts/setup.sh` with no args) opens an interactive menu. Its entries:

- **Quick setup** — system deps + pick modules + build + verify
- **Python modules** — install only the modules you choose
- **Drone driver** — mavros / px4 / px4-dds / crazyflie / bebop
- **System packages** — skipped when already installed
- **ROS 2 environment**, **Build**, **Verify**, **RealSense**

!!! note "Nothing installs until you choose"
    System packages are idempotent. **MAVROS** (`ros-*-mavros`) is opt-in — run
    `make drone-mavros` when you use the MAVROS backend. **GeographicLib** geoid
    datasets install with `make full-install` / bootstrap (idempotent) or with
    `make drone-mavros`; they are not pulled on every menu run.

### Then add what your mission needs

| Goal | Commands |
|---|---|
| ArduPilot / PX4 over direct MAVLink | `make setup` (pick `control`) — `pymavlink` ships with the core SDK; optional `make drone-mavros` for geoid data |
| ArduPilot / PX4 over MAVROS | `make setup` (pick `control`) then `make drone-mavros` |
| PX4 over uXRCE-DDS + detection | `make setup` (pick `control ai`) then `make drone-px4-dds` |
| Crazyflie / Bebop | `make drone-crazyflie` / `make drone-bebop` |
| GUI app only | `make python-interface` |
| Simulation (SITL + Gazebo) | [`make sim-install`](simulation.md) |

Full details: [Drone drivers](drivers.md) (install + fly real hardware), [Simulation](simulation.md), and [RealSense & indoor](realsense.md).

<span id="from-scratch-no-ros-2"></span>
<span id="existing-ros-2-workspace"></span>

=== "From scratch (no ROS 2)"

    A standalone bootstrap script installs everything on a fresh Ubuntu/Debian machine: system packages, ROS 2 (ros-base), GeographicLib geoid data, Git LFS, the SDK itself, Python dependencies (`python all`), and builds the workspace. MAVROS and other drone drivers remain opt-in — add them from the setup menu or with `make drone-mavros` after bootstrap.

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

=== "Existing ROS 2 workspace"

    Clone into your workspace and open the setup menu:

    ```bash
    cd ~/ros2_ws/src
    git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
    cd nectar-sdk
    make setup
    ```

    The menu's **Quick setup** runs: `system` (idempotent) → `git-lfs` → **module selection** (`cmd_python` for the modules you pick; PyTorch first if you choose AI) → `rosdep-init` → `ros2-deps` → `build-pkg` → `verify`. GeographicLib is not part of Quick setup — it installs with `make full-install` / bootstrap or with `make drone-mavros` (idempotent). Non-interactively (`NON_INTERACTIVE=true`, e.g. CI) `make setup` skips the menu and runs Quick setup with `all`.

=== "Docker"

    Skip host ROS/Python setup — build and enter the dev container:

    ```bash
    make docker-build
    make docker-run
    ```

    For Isaac / VSLAM / RealSense workflows, see the [Docker guide](../../docker/README.md) (`make isaac-run`, device mounts, Jetson notes).

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

Override the location with `NECTAR_VENV=/path` (an already-active `VIRTUAL_ENV` is respected); see [Configuration](configuration.md#python-environment-location) for the venv caveat.

## Install by Module

Install only the modules you need (dependencies defined in `nectar/pyproject.toml`). Each
`make` target is a thin wrapper over the setup script, so both columns do the same thing:

| `make` target | Setup script | Installs |
|---|---|---|
| `make python` | `./scripts/setup.sh python` | Core only (numpy, opencv, scipy) |
| `make python-control` | `./scripts/setup.sh python control` | + GPS/PID navigation, pymavlink (direct MAVLink) |
| `make python-vision` | `./scripts/setup.sh python vision` | + Camera drivers, ArUco, color, line detection |
| `make python-ai` | `./scripts/setup.sh python ai` | + YOLO, DETR, RF-DETR (requires PyTorch) |
| `make python-interface` | `./scripts/setup.sh python interface` | + Qt6 / PySide6 GUI |
| `make python-sensors` | `./scripts/setup.sh python sensors` | + pyserial / pymavlink (TF-Luna driver, MAVLink bridge) |
| `make python-all` | `./scripts/setup.sh python all` | All modules |
| `make python-full` | `./scripts/setup.sh python full` | All + camera hardware drivers |

## PyTorch (required for AI module)

Installed via uv's native PyTorch integration (`--torch-backend`), which detects your CUDA driver and pulls torch plus its `nvidia-*` CUDA wheels from the correct `download.pytorch.org` index:

| Command | Effect |
|---|---|
| `make pytorch` | Auto-detect GPU (CUDA 13 -> cu130; no GPU -> cpu) |
| `./scripts/setup.sh pytorch cpu` | Force CPU |
| `./scripts/setup.sh pytorch cu128` | Force a backend (cpu/cu118/cu126/cu128/cu130/...) |

A known-good `torch`/`torchvision` pair is pinned by default in [`scripts/lib/config.sh`](../../scripts/lib/config.sh) for reproducibility; override with `TORCH_VERSION` / `TORCHVISION_VERSION` (set both together). Large CUDA wheels on slow links can stall — the per-request timeout is raised to 600s (`UV_HTTP_TIMEOUT`); on very flaky networks also `export UV_CONCURRENT_DOWNLOADS=1`. See [PyTorch Get Started](https://pytorch.org/get-started/locally/) and the [uv PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/).

## Build & Verify

| Command | Does |
|---|---|
| `make build` | Build entire workspace |
| `make build-pkg` | Build SDK packages only |
| `make verify` | Check installation (presence/imports) |
| `make doctor` | Environment report (ROS, modules, devices, CUDA) |
| `make clean` | Remove build artifacts |
| `make verify-functional` | Functional regression tests (pytest; `MODULE="vision control"`) |
| `make test` | colcon test (functional suite + cmake/xml lint) |

The full command list is on the [Commands & Makefile](../development/commands.md) reference.

## System Setup (individual steps)

| Command | Step |
|---|---|
| `./scripts/setup.sh system` | apt packages |
| `./scripts/setup.sh ros2` | ROS 2 base packages (ros-base, rviz2, cv_bridge, …) |
| `./scripts/setup.sh geographiclib` | GeographicLib geoid datasets (also run by `full-install` and `make drone-mavros`) |
| `./scripts/setup.sh ros2-env` | Configure `~/.bashrc` |
| `./scripts/setup.sh rosdep-init` | Initialize rosdep |
| `./scripts/setup.sh git-ssh` | Configure git and SSH keys |

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
