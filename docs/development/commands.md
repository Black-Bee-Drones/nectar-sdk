# Commands & Makefile

The [`Makefile`](../../Makefile) is a thin wrapper over [`scripts/setup.sh`](../../scripts/setup.sh):
every `make <target>` runs `./scripts/setup.sh <command>`. List everything at any time with:

```bash
make help          # or: ./scripts/setup.sh help
```

## Setup & system

| Command | Does |
|---|---|
| `make setup` | Interactive setup menu (nothing installs until you choose) |
| `make system` | Install apt system packages |
| `make ros2` | Install ROS 2 + MAVROS |
| `make geographiclib` | Install GeographicLib geoid datasets |
| `make ros2-env` | Configure `~/.bashrc` (adds `nectar-activate`) |
| `make rosdep-init` | Initialize rosdep |
| `make full-install` | Full setup from zero (used by the bootstrap) |
| `make update` | Update system packages (apt upgrade) |

## Python modules

| Command | Installs |
|---|---|
| `make python` | Core only (numpy, opencv, scipy) |
| `make python-control` | + GPS, PID, MAVROS navigation |
| `make python-vision` | + camera drivers, ArUco, color, line |
| `make python-ai` | + YOLO, DETR, RF-DETR (needs PyTorch) |
| `make python-interface` | + Qt6 / PySide6 GUI |
| `make python-sensors` | + pyserial / pymavlink |
| `make python-all` | All modules |
| `make python-full` | All + camera hardware drivers |
| `make python-dev` | Test/dev tooling (pytest) |
| `make pytorch` | PyTorch (auto-detects CUDA / CPU) |

See [Installation](../setup/index.md) for details.

## Drone drivers

| Command | Installs |
|---|---|
| `make drone-mavros` | MAVROS (ArduPilot) + GeographicLib |
| `make drone-px4` | PX4 over MAVROS |
| `make drone-px4-dds` | PX4 over uXRCE-DDS |
| `make drone-crazyflie` | Crazyswarm2 |
| `make drone-bebop` | Parrot Bebop 2 |
| `make drone-all` | all of the above |

Start a driver/bridge for real hardware with `make driver DRONE=<type> ...`; see [Drone drivers](../setup/drivers.md).

## Build, verify & quality

| Command | Does |
|---|---|
| `make build` | Build the entire workspace |
| `make build-pkg` | Build SDK packages only |
| `make clean` | Remove build artifacts |
| `make verify` | Check installation (presence/imports) |
| `make verify-functional` | Functional pytest suite (`MODULE="vision control"` for a subset) |
| `make verify-hardware` | Device-gated tests (cameras, rangefinder) |
| `make verify-sitl` | SITL/integration flight tests (`FIRMWARE=`, `PROTOCOL=`) |
| `make doctor` | Read-only environment report (ROS, modules, devices, CUDA) |
| `make test` | colcon test (functional suite + cmake/xml lint) |
| `make ci-local` | Cross-distro CI in Docker (`DISTROS=`, `FULL=`) |
| `make check` | All pre-commit checks (lint/format, same as CI) |
| `make lint` / `make lint-fix` / `make format` | Python ruff check / fix / format |

## Simulation

Choose `FIRMWARE` (`ardupilot`/`px4`), `ENV` (`outdoor`/`indoor`), `PROTOCOL` (`mavros`/`mavlink`/`dds`).

| Command | Does |
|---|---|
| `make sim-install FIRMWARE=..` | Install SITL + Gazebo (also `all`) |
| `make sim-start FIRMWARE=.. ENV=..` | Terminal 1: the simulator |
| `make sim-bridge FIRMWARE=.. ENV=.. PROTOCOL=..` | Terminal 2: the ROS stack |
| `make sim-stop` | Stop everything |

See [Simulation](../setup/simulation.md).

## Real-hardware drivers

| Command | Does |
|---|---|
| `make driver DRONE=.. ENV=.. FCU_URL=..` | Start the driver/bridge the mission connects to |
| `make driver-mavros` / `driver-px4` / `driver-px4-dds` / `driver-bebop` / `driver-crazyflie` | Per-type shortcuts |
| `make driver-stop` | Stop all drivers/bridges |

Connection overrides via env: `FCU_URL` / `DEV` / `BAUD` / `PORT` / `IP`.

## RealSense & Isaac VSLAM

| Command | Does |
|---|---|
| `make realsense` | Build librealsense + realsense-ros |
| `make realsense-verify` | Verify the RealSense install |
| `make isaac-run` | Launch the Isaac ROS Visual SLAM container (Jetson) |
| `make isaac-stop` | Tear down Isaac containers |
| `make vslam-viz` | VSLAM RViz check (`VSLAM_PROFILE=light` or `full`) |

## Docker

| Command | Does |
|---|---|
| `make docker-build` | SDK image (no AI) |
| `make docker-build-full` | Full image (+ PyTorch/AI) |
| `make docker-build-t265` | Image with T265 support |
| `make docker-run` | Run with X11, cameras, USB |
| `make docker-exec` | Extra terminal in a running container |
| `make docker-publish-jetson` | Build + push the Jetson image (run on the Jetson) |

See [Docker](../../docker/README.md).

## Documentation site

| Command | Does |
|---|---|
| `make docs-install` | Create `.venv-docs` and install the doc toolchain |
| `make docs-sync` | Assemble `build/docs/` from `website/` + READMEs + `docs/*.md` |
| `make docs` | Sync, then build the HTML into `build/site/` |
| `make docs-serve` | Sync, then live-preview at `http://localhost:8000` |

Edit the authored pages under `website/`, the module READMEs, and `docs/*.md`; everything under
`build/` is generated. Conventions are in [Contributing](../CONTRIBUTING.md).
