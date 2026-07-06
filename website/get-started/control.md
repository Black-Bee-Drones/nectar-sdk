# Fly a drone

Take off, fly a square, and land with the same code on any supported platform. You pick a
**backend** (a firmware plus a transport), start its **driver** (or a simulator), set a **pose
source**, and run a mission. Only the factory key and its config change between platforms; the
flight calls stay identical.

Pick your backend in the tab below and it stays selected through install, driver, and mission
code. New to the workspace? Do the [Installation](../setup/index.md) first.

## 1. Install the backend

Install `control`, then add the driver your vehicle uses:

```bash
make setup           # pick: control
```

=== "ArduPilot · MAVROS"

    ```bash
    make drone-mavros
    ```

=== "ArduPilot · MAVLink"

    No extra install: `pymavlink` ships with the core SDK. `make drone-mavros` adds the
    geoid data used for GPS altitude.

=== "PX4 · MAVROS"

    ```bash
    make drone-px4
    ```

=== "PX4 · MAVLink"

    No extra install: `pymavlink` ships with the core SDK. `make drone-mavros` adds the
    geoid data used for GPS altitude.

=== "PX4 · uXRCE-DDS"

    ```bash
    make drone-px4-dds
    ```

=== "Crazyflie"

    ```bash
    make drone-crazyflie
    ```

=== "Bebop"

    ```bash
    make drone-bebop
    ```

## 2. Set the pose source

For ArduPilot and PX4 the **environment** selects the pose source on the config:

| Environment | Pose source | Config argument |
|-------------|-------------|-----------------|
| Outdoor | GPS | `pose_source=PoseSource.GPS` |
| Indoor (GPS-denied) | Vision (VSLAM) | `pose_source=PoseSource.VISION` |

!!! note "Indoor flight"
    A vision-pose feed into the FCU's EKF is required indoors; see
    [Localization](../modules/control/localization.md). Bebop and Crazyflie fly indoors
    without GPS and ignore this setting.

## 3. Start the driver

Start the driver or bridge your mission connects to **before** running it (examples default
to `start_driver=False`). Connection overrides go through env vars (`FCU_URL`, `DEV`, `BAUD`,
`IP`).

=== "ArduPilot · MAVROS"

    ```bash
    make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600
    ```

=== "ArduPilot · MAVLink"

    Outdoor needs no bridge; the mission opens the link itself. Indoor starts the
    vision-pose bridge:

    ```bash
    make driver DRONE=mavlink ENV=indoor
    ```

=== "PX4 · MAVROS"

    ```bash
    make driver DRONE=px4 FCU_URL=udp://:14540@127.0.0.1:14580
    ```

=== "PX4 · MAVLink"

    Outdoor needs no bridge; the mission opens the link itself. Indoor starts the
    vision-pose bridge:

    ```bash
    make driver DRONE=px4_mavlink ENV=indoor
    ```

=== "PX4 · uXRCE-DDS"

    ```bash
    make driver-px4-dds DEV=/dev/ttyUSB0 BAUD=921600   # PORT=8888 for UDP
    ```

=== "Crazyflie"

    ```bash
    make driver-crazyflie
    ```

=== "Bebop"

    ```bash
    make driver-bebop IP=192.168.42.1
    ```

!!! tip "No hardware yet? Fly in simulation"
    ```bash
    make sim-install FIRMWARE=ardupilot   # one-time (use FIRMWARE=px4 for PX4)
    make sim-start                        # terminal 1
    make sim-bridge                       # terminal 2
    ```
    For direct MAVLink or uXRCE-DDS add `PROTOCOL=mavlink` / `PROTOCOL=dds` on `sim-bridge`. Full
    matrix: [Simulation](../setup/simulation.md).

## 4. Write the mission

Build the drone with your backend's factory key and config. The flight calls after it are the
same for every backend.

=== "ArduPilot · MAVROS"

    ```python
    import nectar
    from nectar.control import DroneFactory, MavrosConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("mavros", MavrosConfig(pose_source=PoseSource.GPS))
    ```

=== "ArduPilot · MAVLink"

    ```python
    import nectar
    from nectar.control import DroneFactory, MavlinkConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("mavlink", MavlinkConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · MAVROS"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4MavrosConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4", Px4MavrosConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · MAVLink"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4MavlinkConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4_mavlink", Px4MavlinkConfig(pose_source=PoseSource.GPS))
    ```

=== "PX4 · uXRCE-DDS"

    ```python
    import nectar
    from nectar.control import DroneFactory, Px4DdsConfig, PoseSource

    nectar.init()
    drone = DroneFactory.create("px4_dds", Px4DdsConfig(pose_source=PoseSource.GPS))
    ```

=== "Crazyflie"

    ```python
    import nectar
    from nectar.control import DroneFactory, CrazyflieConfig

    nectar.init()
    drone = DroneFactory.create("crazyflie", CrazyflieConfig())
    ```

=== "Bebop"

    ```python
    import nectar
    from nectar.control import DroneFactory, BebopConfig

    nectar.init()
    drone = DroneFactory.create("bebop", BebopConfig())
    ```

Fly a 2 m square, then land:

```python
drone.takeoff(altitude=2.0)
drone.move_to(x=2.0, y=0.0, z=0.0)
drone.move_to(x=2.0, y=2.0, z=0.0)
drone.move_to(x=0.0, y=2.0, z=0.0)
drone.move_to(x=0.0, y=0.0, z=0.0)
drone.land()
nectar.shutdown()
```

The bundled examples fly the same box on any backend, flown by the PID navigator where the
backend supports it. Each tab is the exact command for that platform (outdoor GPS shown; for
indoor flight swap `--mode indoor` on `navigation.py` or `--env indoor` on `basic.py` to the
vision pose source):

=== "ArduPilot · MAVROS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone mavros --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

=== "ArduPilot · MAVLink"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone mavlink --connection tcp:127.0.0.1:5762 \
        --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

    On hardware, pass your serial link instead, e.g. `--connection /dev/ttyUSB0`.

=== "PX4 · MAVROS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/navigation.py \
        --drone px4 --mode outdoor --strategy pid \
        --test rectangle --altitude 2.0 --distance 2.0 --precision 0.15
    ```

=== "PX4 · MAVLink"

    `navigation.py` does not cover this backend; the position box in `basic.py` does:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone px4_mavlink --mode position \
        --height 2.0 --side 2.0 --precision 0.15 --env outdoor
    ```

=== "PX4 · uXRCE-DDS"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone px4_dds --mode position \
        --height 2.0 --side 2.0 --precision 0.15 --env outdoor
    ```

=== "Crazyflie"

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py \
        --drone crazyflie --mode position \
        --height 0.5 --side 0.6 --precision 0.15
    ```

=== "Bebop"

    Bebop has no onboard position control, so it flies the velocity box:

    ```bash
    nectar-activate
    python3 nectar/nectar/examples/control/basic.py --drone bebop --mode velocity
    ```

!!! success "Expected result"
    The drone arms, climbs to the target altitude, flies a 2 m box (0.6 m for Crazyflie) with
    0.15 m arrival precision, then lands and disarms.

<figure class="nectar-shot">
  <div class="nectar-shot__media" data-src="../assets/media/basic-square.mp4">
    <video class="nectar-autoplay" muted loop playsinline preload="metadata">
      <source src="../assets/media/basic-square.mp4" type="video/mp4">
    </video>
  </div>
  <figcaption>Our drone flying the square example on real hardware. Click to enlarge.</figcaption>
</figure>

## Go deeper

- [Control reference](../modules/control/index.md): the factory, the `Drone` protocol,
  capabilities, and the full backend matrix.
- [Vehicle core](../modules/control/vehicle.md) · [Transports](../modules/control/mavlink.md) ·
  [PID tuning](../modules/control/pid.md) · [Obstacles](../modules/control/obstacles.md) ·
  [Localization](../modules/control/localization.md).
- [Control examples](../modules/examples/control.md): navigation suite, interactive REPL,
  servo test.
