# Simulation (Gazebo + ArduPilot / PX4 SITL)

Fly the same missions you run on hardware, in Gazebo with ArduPilot or PX4 SITL — no vehicle
required. Install once per firmware, then start the simulator and the ROS bridge in two terminals.

## Install

One install command per firmware. ArduPilot pulls ArduCopter SITL, Gazebo, the `ros_gz` bridge,
and the ArduPilot Gazebo plugin (auto-selecting the Gazebo version per ROS distro; per-distro
table in the [Docker guide](../../docker/README.md)). PX4 pulls PX4-Autopilot and Gazebo and
symlinks the Nectar shared assets into the PX4 tree.

```bash
make sim-install FIRMWARE=ardupilot   # ArduCopter SITL + Gazebo + plugin
make sim-install FIRMWARE=px4          # PX4 SITL + Gazebo + Nectar assets
make sim-install FIRMWARE=all          # both
```

### Docker with Gazebo

```bash
INSTALL_GAZEBO=true make docker-build
INSTALL_GAZEBO=true ROS_DISTRO=jazzy make docker-build
```

See the [Docker guide](../../docker/README.md) for more options.

## Running the simulation

Two terminals, the same pattern for both firmwares: the simulator (terminal 1) plus the
ROS stack (terminal 2). Choose `FIRMWARE`/`ENV`/`PROTOCOL` (defaults: `ardupilot` /
`outdoor` / `mavros`):

| Setup | Terminal 1 (simulator) | Terminal 2 (ROS stack) |
|---|---|---|
| ArduPilot outdoor / MAVROS (default) | `make sim-start` | `make sim-bridge` |
| ArduPilot outdoor / direct MAVLink | `make sim-start FIRMWARE=ardupilot ENV=outdoor` | `make sim-bridge FIRMWARE=ardupilot ENV=outdoor PROTOCOL=mavlink` |
| ArduPilot indoor (vision) | `make sim-start FIRMWARE=ardupilot ENV=indoor` | `make sim-bridge FIRMWARE=ardupilot ENV=indoor` |
| PX4 outdoor / MAVROS | `make sim-start FIRMWARE=px4 ENV=outdoor` | `make sim-bridge FIRMWARE=px4 ENV=outdoor` |
| PX4 indoor (onboard VIO) | `make sim-start FIRMWARE=px4 ENV=indoor` | `make sim-bridge FIRMWARE=px4 ENV=indoor` |

Stop everything (both firmwares) with `make sim-stop`.

Then run a mission against it, e.g.:

```bash
nectar-activate
python3 nectar/nectar/examples/control/basic.py --drone mavros --mode position --side 2.0
```

See the [Simulation module](../../nectar/simulation/README.md) for the full matrix, the vision pipeline, and the automated test suite.
