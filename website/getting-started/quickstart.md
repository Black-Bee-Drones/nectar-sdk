# Quickstart

Get from a fresh clone to a flying drone (in simulation or on hardware) in a few minutes.
For the full matrix of options see the [Installation guide](../project/installation.md)
and the tested [compatibility matrix](../project/compatibility.md).

## 1. Install

You need [ROS 2](https://docs.ros.org/) (Humble, Jazzy, or Kilted) on Ubuntu. Pick the row
that matches where you're starting from:

=== "Have ROS 2"

    ```bash
    cd ~/ros2_ws/src # your workspace path
    git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
    cd nectar-sdk
    make setup          # interactive menu — nothing installs until you choose
    ```

=== "Fresh machine"

    ```bash
    bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)
    ```

=== "Docker"

    ```bash
    make docker-build && make docker-run        # add docker-build-full for AI/PyTorch
    ```

The setup menu installs only what you choose. Add the control backend your vehicle uses,
e.g. `make drone-mavros` for ArduPilot/PX4 over MAVROS or direct MAVLink.

## 2. Fly in simulation

Two terminals — the simulator, then the ROS stack (defaults: `ardupilot` / `outdoor` /
`mavros`):

```bash
make sim-install FIRMWARE=ardupilot    # one-time
make sim-start                         # terminal 1: SITL + Gazebo
make sim-bridge                        # terminal 2: ROS bridge
```

Then run a mission against it:

```bash
nectar-activate    # enter the SDK Python environment
python3 nectar/nectar/examples/control/basic.py --drone mavros --mode position --side 2.0
```

## 3. Your first mission

```python
import nectar
from nectar.control import DroneFactory, MavrosConfig, PoseSource

nectar.init()
drone = DroneFactory.create("mavros", MavrosConfig(pose_source=PoseSource.GPS))

drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3)
drone.move_to_gps(lat=-22.413, lon=-45.449, alt=15.0)
drone.land()

nectar.shutdown()
```

The same script runs on a different vehicle or transport by changing only the factory key
and config — `"mavlink"`, `"px4"`, `"px4_dds"`, `"crazyflie"`, `"bebop"`. See the
[Control module](../modules/control/index.md) for the full drone/transport matrix.

## 4. Fly real hardware

Examples run with `start_driver=False`, so start the driver/bridge your mission connects
to in its own terminal, then run the mission:

```bash
make driver DRONE=mavros FCU_URL=serial:///dev/ttyUSB0:921600   # terminal 1
python3 nectar/nectar/examples/control/basic.py --drone mavros  # terminal 2
```

See the [Installation guide](../project/installation.md#flying-real-hardware) for worked
examples (direct-MAVLink square, Crazyflie, PX4-DDS + detection, indoor VSLAM).

## 5. See and detect

Here a webcam stream is run through a YOLO detector — swap `"webcam"` for `realsense`, `oakd`, or a ROS topic, and
`"yolov8n.pt"` for a DETR or RF-DETR model, without changing the rest:

```python
import nectar
from nectar.ai.detection import Detector
from nectar.vision.camera import ImageHandler

nectar.init()
detector = Detector("yolov8n.pt")
detector.load()

def on_frame(frame):
    for det in detector.detect(frame):
        print(det.class_name, round(det.confidence, 2))

ImageHandler(image_source="webcam", image_processing_callback=on_frame).run()
nectar.spin()        # Ctrl+C to stop
nectar.shutdown()
```

Each module is independent and shares one runtime, so you mix control, vision, and AI in a
single mission — fly, see, detect — by composing the pieces you need.

## Next steps

- [Control](../modules/control/index.md) — drones, transports, navigation, obstacles, PID
- [Vision](../modules/vision.md) — cameras, ArUco, color/line, distance, MediaPipe
- [AI](../modules/ai/index.md) — detection, training, evaluation, the `nectar-ai` CLI
- [Architecture](../concepts/architecture.md) — how the pieces fit together
