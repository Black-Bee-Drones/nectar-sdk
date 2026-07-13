
# Nectar SDK

<div align="center">

<img align="left" width="35" height="35" src="https://images.emojiterra.com/google/noto-emoji/unicode-15/animated/1f41d.gif" alt="Bee">

ROS 2 software development kit for autonomous aerial systems. Unified interfaces for flight control, computer vision, and AI — one mission across vehicles, sensors, and simulators.

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/Apache-2.0-D22128?style=flat&labelColor=black&logo=apache&logoColor=D22128" alt="Apache License" /></a>
  <a href="https://github.com/Black-Bee-Drones/nectar-sdk/releases/latest"><img src="https://img.shields.io/github/v/release/Black-Bee-Drones/nectar-sdk?sort=semver" alt="Latest release"></a>
  <a href="https://github.com/Black-Bee-Drones/nectar-sdk/compare/main...dev"><img src="https://img.shields.io/github/commits-since/Black-Bee-Drones/nectar-sdk/main/dev?label=commits%20since" alt="Commits since"></a>
  <a href="https://github.com/Black-Bee-Drones/nectar-sdk/stargazers"><img src="https://img.shields.io/github/stars/Black-Bee-Drones/nectar-sdk?style=social" alt="Stars"></a>
</p>

| ROS 2 Distro | Build & Test | Docker |
|:---:|:---:|:---:|
| **Humble** | [![Build Humble](https://img.shields.io/github/actions/workflow/status/Black-Bee-Drones/nectar-sdk/build-test-humble.yml?branch=main&label=Humble)](https://github.com/Black-Bee-Drones/nectar-sdk/actions/workflows/build-test-humble.yml) | [![Docker](https://img.shields.io/badge/Docker-humble-blue)](https://hub.docker.com/r/blackbeedrones/nectar-sdk/tags?name=humble) |
| **Jazzy** | [![Build Jazzy](https://img.shields.io/github/actions/workflow/status/Black-Bee-Drones/nectar-sdk/build-test-jazzy.yml?branch=main&label=Jazzy)](https://github.com/Black-Bee-Drones/nectar-sdk/actions/workflows/build-test-jazzy.yml) | [![Docker](https://img.shields.io/badge/Docker-jazzy-blue)](https://hub.docker.com/r/blackbeedrones/nectar-sdk/tags?name=jazzy) |
| **Kilted** | [![Build Kilted](https://img.shields.io/github/actions/workflow/status/Black-Bee-Drones/nectar-sdk/build-test-kilted.yml?branch=main&label=Kilted)](https://github.com/Black-Bee-Drones/nectar-sdk/actions/workflows/build-test-kilted.yml) | [![Docker](https://img.shields.io/badge/Docker-kilted-blue)](https://hub.docker.com/r/blackbeedrones/nectar-sdk/tags?name=kilted) |

</div>

## Documentation

Please visit the **[Nectar SDK documentation](https://black-bee-drones.github.io/nectar-sdk/)** for installation, tutorials, module reference, Python API, simulation, and Docker.

## Features

ArduPilot and PX4 over MAVROS, direct MAVLink, or uXRCE-DDS, plus Bebop and Crazyflie — modular install via [uv](https://github.com/astral-sh/uv). Depth for each area lives on the docs site:

- **[Control](https://black-bee-drones.github.io/nectar-sdk/modules/control/)** — firmware-agnostic flight interface, navigation, PID, obstacles, GPS
- **[Vision](https://black-bee-drones.github.io/nectar-sdk/modules/vision/)** — cameras, ArUco, color, line, distance, optical flow, MediaPipe
- **[AI](https://black-bee-drones.github.io/nectar-sdk/modules/ai/)** — detection, segmentation, and classification (YOLO, DETR, RF-DETR, ViT), training, evaluation
- **[Sensors](https://black-bee-drones.github.io/nectar-sdk/modules/sensors/)** — companion rangefinders and MAVLink bridges
- **[Localization](https://black-bee-drones.github.io/nectar-sdk/modules/control/localization/)** — indoor VSLAM and vision-pose integration
- **[Interface](https://black-bee-drones.github.io/nectar-sdk/modules/interface/)** — Qt6 operator GUI
- **[Simulation](https://black-bee-drones.github.io/nectar-sdk/setup/simulation/)** — ArduPilot/PX4 SITL with Gazebo

End-to-end architecture and design patterns: [Architecture](https://black-bee-drones.github.io/nectar-sdk/concepts/architecture/).

## Quick start

| Your starting point | Run |
|---|---|
| Fresh machine, no ROS 2 | `bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)` |
| Have ROS 2, no SDK yet | `cd ~/ros2_ws/src && git clone git@github.com:Black-Bee-Drones/nectar-sdk.git && cd nectar-sdk && make setup` |
| Have the SDK cloned | `make setup` |
| Want zero host setup | `make docker-build && make docker-run` |

Full install paths, drivers, and compatibility: **[Installation guide](https://black-bee-drones.github.io/nectar-sdk/setup/)**.

## Example

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

More examples: [Get started](https://black-bee-drones.github.io/nectar-sdk/get-started/)

## Contributing

We welcome contributions. See the [Contributing guide](docs/CONTRIBUTING.md) for setup, code style, and the PR process.

1. Check [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) for existing discussions
2. Follow [Conventional Commits](https://www.conventionalcommits.org) for commit messages
3. Read our [Code of Conduct](docs/CODE_OF_CONDUCT.md)

<div align="center">
<a href="https://github.com/Black-Bee-Drones/nectar-sdk/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Black-Bee-Drones/nectar-sdk&max=100" alt="Contributors" />
</a>
</div>

## Black Bee Drones

[Black Bee Drones](https://github.com/Black-Bee-Drones) is Latin America's first academic autonomous drone team, founded at the [Federal University of Itajubá](https://unifei.edu.br/) (UNIFEI) in 2014. The team competes nationally and internationally — including [IMAV](https://www.imavs.org/) (3rd place indoor 2023 and 2025), [CBR RoboCup Flying Robots](https://cbr.robocup.org.br/), and [SAE Eletroquad](https://saebrasil.org.br/programas-estudantis/eletroquad/).

Nectar SDK started in 2023 as shared infrastructure for competition missions and is now open source under Apache 2.0.

## Acknowledgments

Built on open source across robotics, perception, and AI:

- **Robotics & flight:** [ROS 2](https://docs.ros.org/), [ArduPilot](https://ardupilot.org/), [PX4](https://px4.io/), [MAVLink](https://mavlink.io/), [MAVROS](https://github.com/mavlink/mavros)
- **Perception & AI:** [OpenCV](https://opencv.org/), [PyTorch](https://pytorch.org/), [Ultralytics](https://docs.ultralytics.com/), [HuggingFace](https://huggingface.co/), [Roboflow](https://roboflow.com/), [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions)
- **Localization & sensors:** [NVIDIA Isaac ROS](https://nvidia-isaac-ros.github.io/), [Intel RealSense](https://github.com/realsenseai/librealsense), [Luxonis](https://docs.luxonis.com/)

## License

This project is licensed under the Apache-2.0 License — see the [`LICENSE`](LICENSE) file for details.
