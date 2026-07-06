# Drone drivers

Each drone needs its own driver or bridge, started in its own terminal before the mission
connects (examples default to `start_driver=False`). This is the real-world counterpart of the
[simulation](simulation.md) bridge.

Pick your drone below for the install, the driver command, and a worked flight. Targets are
defined in `scripts/lib/drones.sh`.

## Pick your drone

=== "ArduPilot · MAVROS"

    Installs MAVROS and the GeographicLib geoid datasets.

    ```bash
    make setup                 # pick: control
    make drone-mavros
    ```

    Start the driver, then fly a 2 m square:

    ```bash
    make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600   # terminal 1
    nectar-activate                                                 # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone mavros --mode position --side 2.0
    ```

=== "ArduPilot · MAVLink"

    No separate install: `pymavlink` ships with the core SDK, so the mission opens the link
    itself. `make drone-mavros` adds the geoid data used for GPS altitude.

    Outdoor needs no bridge; fly directly:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone mavlink --mode position --side 2.0 --env outdoor \
        --connection serial:///dev/ttyUSB0:921600
    ```

    Indoor (GPS-denied) starts the vision-pose bridge first:

    ```bash
    make driver DRONE=mavlink ENV=indoor          # terminal 1: VISION_POSITION_ESTIMATE -> FCU
    python3 nectar/nectar/examples/control/basic.py \
        --drone mavlink --mode position --side 2.0 --env indoor    # terminal 2
    ```

=== "PX4 · MAVROS"

    Reuses MAVROS, launched with `px4.launch`.

    ```bash
    make setup                 # pick: control
    make drone-px4
    ```

    ```bash
    make driver DRONE=px4 FCU_URL=udp://:14540@127.0.0.1:14580   # terminal 1
    nectar-activate                                              # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone px4 --mode position --side 2.0
    ```

=== "PX4 · MAVLink"

    No separate install: `pymavlink` ships with the core SDK. Outdoor the mission opens the
    link itself; indoor starts the vision-pose bridge (`make driver DRONE=px4_mavlink ENV=indoor`).

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py --drone px4_mavlink --mode position --side 2.0
    ```

=== "PX4 · uXRCE-DDS"

    Installs `px4_msgs` and the Micro XRCE-DDS Agent (real hardware; no SITL).

    ```bash
    make setup                 # pick: control
    make drone-px4-dds
    ```

    ```bash
    make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # terminal 1 (PORT=8888 for UDP)
    nectar-activate                                    # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone px4_dds
    ```

    To add an object detector to the same mission, install `ai` too (`make setup` → `control ai`)
    and use `from nectar.ai.detection import Detector`.

=== "Crazyflie"

    Installs Crazyswarm2 (apt when available, else source) plus radio udev rules. Set your URI
    in `crazyflies.yaml`.

    ```bash
    make drone-crazyflie
    ```

    ```bash
    make driver-crazyflie      # terminal 1: Crazyflie server
    nectar-activate            # terminal 2
    python3 nectar/nectar/examples/control/basic.py \
        --drone crazyflie --mode position --height 0.5 --side 0.6
    ```

=== "Bebop"

    Installs `ros2_parrot_arsdk` and `ros2_bebop_driver` (source build, Humble-only).

    ```bash
    make drone-bebop
    ```

    ```bash
    make driver-bebop IP=192.168.42.1   # terminal 1
    nectar-activate                     # terminal 2
    python3 nectar/nectar/examples/control/basic.py --drone bebop
    ```

!!! note "Manage drivers"
    - Install every driver at once with `make drone-all`.
    - Stop all running drivers and bridges with `make driver-stop`.
    - Override connections with the `FCU_URL`, `DEV`, `BAUD`, `PORT`, and `IP` env vars.
    - Per-type shortcuts exist (`make driver-mavros`, `driver-px4`, ...).

For the full backend matrix and configuration, see the [Control module](../../nectar/nectar/control/README.md).
