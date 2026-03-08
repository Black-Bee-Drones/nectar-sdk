
# Nectar SDK

<div align="center">

<img align="left" width="35" height="35" src="https://images.emojiterra.com/google/noto-emoji/unicode-15/animated/1f41d.gif" alt="Bee">

ROS 2 software development kit for autonomous aerial systems. Provides unified interfaces for flight control, computer vision, and object detection through a modular, extensible architecture.

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


## Table of Contents

- [Features](#features)
  - [Drone Control](#drone-control)
  - [Computer Vision](#computer-vision)
  - [AI / Detection](#ai--detection)
  - [Interface](#interface)
  - [Nectar Interfaces](#nectar-interfaces)
- [Installation](#installation)
  - [From Scratch](#from-scratch)
  - [Existing ROS 2 Workspace](#existing-ros-2-workspace)
  - [Install by Module](#install-by-module)
  - [Docker](#docker)
- [Architecture](#architecture)
  - [Design Patterns](#design-patterns)
- [Documentation](#documentation)
- [ROS 2 Nodes](#ros-2-nodes)
- [Examples](#examples)
- [Directory Structure](#directory-structure)
- [Contributing](#contributing)
- [Black Bee Drones](#black-bee-drones)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Features

### [Drone Control](nectar/nectar/control/README.md)

Protocol-based drone interface with factory instantiation. `DroneFactory` creates drone implementations by key — currently [MAVROS](https://github.com/mavlink/mavros) ([ArduPilot](https://ardupilot.org/)/[PX4](https://docs.px4.io/)) and Parrot Bebop 2, extensible to any platform. All drones implement the same `Drone` protocol: takeoff, land, move_to, move_to_gps, move_velocity, rtl, obstacle management.

- Position navigation via PID control or FCU setpoints, in body, world, or takeoff reference frames
- GPS waypoint missions with [EGM96](https://en.wikipedia.org/wiki/EGM96) geoid correction for AMSL altitude
- Event-based obstacle detection with strategy-based avoidance (pause, axis disable, custom sequences)
- Return-to-launch with PID or ArduPilot-native RTL modes
- Per-axis PID tuning via YAML with runtime updates

```python
from nectar.control import DroneFactory, MavrosConfig, BebopConfig, PoseSource

# Same interface, different platforms
drone = DroneFactory.create("mavros", MavrosConfig(pose_source=PoseSource.GPS), node)
# drone  = DroneFactory.create("bebop", BebopConfig(), node)

drone.takeoff(altitude=2.0)
drone.move_to(x=5.0, y=0.0, z=0.0, precision=0.3)
drone.move_to_gps(lat=-22.413, lon=-45.449, alt=15.0)
drone.land()
```

[Control overview](nectar/nectar/control/README.md) · [MAVROS details](nectar/nectar/control/mavros/README.md) · [Obstacles](nectar/nectar/control/obstacles/README.md) · [PID](nectar/nectar/control/pid/README.md) · [Bebop](nectar/nectar/control/bebop/README.md)

### [Computer Vision](nectar/nectar/vision/README.md)

Camera abstraction and image processing. `CameraFactory` auto-detects the source type from a string identifier and returns the matching driver. `ImageHandler` wraps any camera in a ROS 2 timer loop with frame callbacks and optional OpenCV display.

- Camera drivers: USB ([OpenCV](https://opencv.org/)), Intel [RealSense](https://github.com/IntelRealSense/librealsense) D4xx, Luxonis [OAK-D](https://docs.luxonis.com/), ROS 2 topics, Raspberry Pi Camera v2
- [ArUco](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html) marker detection with 6-DOF pose estimation
- Color detection with HSV/LAB calibration and interactive trackbars
- Line detection with five estimation methods (Hough, RANSAC, rotated rect, fit ellipse, adaptive Hough)
- Distance estimation via six regression models (linear, polynomial, exponential, logarithmic, inverse power, robust)
- Hand and face tracking via [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions)

```python
from nectar.vision import CameraFactory, ImageHandler, OpenCVConfig, Aruco

# One factory, any camera
camera = CameraFactory.from_source("webcam", config=OpenCVConfig(width=1280, height=720))
camera = CameraFactory.from_source("realsense")
camera = CameraFactory.from_source("/camera/image_raw", node=node)  # ROS 2 topic

# Timer-based capture with processing callback
aruco = Aruco(marker_dict=5, tag_size=0.05)

handler = ImageHandler(
    node=self, image_source="webcam",
    image_processing_callback=lambda frame: aruco.pose_estimate(frame, draw=True),
    show_result="Camera",
)
handler.run()
```

[Vision overview](nectar/nectar/vision/README.md) — camera classes, algorithm API, node parameters, calibration, module structure

### [AI / Detection](nectar/nectar/ai/README.md)

Object detection across three frameworks through `Detector`, a single factory-based entry point. Auto-detects the framework from the model path or accepts explicit selection. Models load from local files, Ultralytics Hub, or HuggingFace Hub.

- [Ultralytics YOLO](https://docs.ultralytics.com/) (YOLOv8, YOLOv10, YOLO11), [HuggingFace Transformers](https://huggingface.co/docs/transformers/) (DETR, Conditional DETR), [RF-DETR](https://github.com/roboflow/RF-DETR)
- Training with per-framework config dataclasses, [TensorBoard](https://www.tensorflow.org/tensorboard) logging, [HuggingFace Hub](https://huggingface.co/docs/hub/) push
- Slicing inference for high-resolution images with four post-processing strategies (NMS, Soft-NMS, WBF, NMM)
- Model evaluation with mAP, precision, recall via [supervision](https://github.com/roboflow/supervision)
- CLI tools for predict, train, and evaluate workflows

```python
from nectar.ai.detection import Detector

detector = Detector("yolov8n.pt")                         # Ultralytics YOLO
detector = Detector("facebook/detr-resnet-50")             # HuggingFace DETR
detector = Detector("rf-detr-nano.pth")                    # RF-DETR

detector.load()
result = detector.detect(image, conf=0.5)

for det in result:
    print(f"{det.class_name}: {det.confidence:.2f} at {det.bbox}")

annotated = detector.draw_detections(image, result)
```

[AI overview](nectar/nectar/ai/README.md) · [Detection details](nectar/nectar/ai/detection/README.md) — class diagram, core types, framework configs, slicing, CLI, extension guide

### [Interface](nectar/nectar/interface/README.md)

[Qt6 / PySide6](https://doc.qt.io/qtforpython-6/) desktop application for testing and operating the SDK without writing code. Three tabs: **Control** (drone connection, arm/takeoff/land, keyboard velocity control, position navigation), **Vision** (camera streaming with 20+ real-time filters including ArUco detection and MediaPipe tracking), and **ROS** (topic browser/subscriber/publisher, service caller, parameter viewer, image subscriber).

[Interface overview](nectar/nectar/interface/README.md) — architecture, tabs, widgets, threading model, camera integration, theming

### [Nectar Interfaces](nectar_interfaces/README.md)

Custom ROS 2 messages connecting vision output to control decisions:

| Message | Fields | Published By |
|---------|--------|--------------|
| `ArucoTransforms` | marker ID, translation vector, yaw | `ArucoNode` |
| `LineInfo` | center XY, angle, width, height | `LineDetectionNode` |
| `PhotoInfo` | coordinate array, photo identifier | Vision nodes |

[Interfaces overview](nectar_interfaces/README.md) — message definitions, usage examples (Python/C++), building, verification

## Installation

### From Scratch

A standalone bootstrap script handles everything: ROS 2, system packages, MAVROS, GeographicLib, git/SSH, cloning, Python dependencies, workspace build, and verification.

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Black-Bee-Drones/nectar-sdk/main/scripts/bootstrap.sh)
```

### Existing ROS 2 Workspace

```bash
cd ~/ros2_ws/src
git clone git@github.com:Black-Bee-Drones/nectar-sdk.git
cd nectar-sdk
make setup
```

### Install by Module

```bash
make python-control    # GPS, PID, MAVROS navigation
make python-vision     # Camera drivers, ArUco, color, line detection
make python-ai         # YOLO, DETR, RF-DETR (requires PyTorch)
make python-interface  # Qt6 / PySide6 GUI
make pytorch           # PyTorch (auto-detects CUDA)
```

### Interactive Menu

Run the setup script with no arguments for a guided menu where you can pick individual steps:

```bash
./scripts/setup.sh
```

### Docker

**Linux:**
```bash
make docker-build       # SDK image (no AI)
make docker-build-full  # Full image (+ PyTorch + AI)
make docker-run         # Run with X11 + cameras + USB
```

**Windows:**
```powershell
.\docker\run_docker_win.ps1 build humble              # Build SDK image
.\docker\run_docker_win.ps1 build jazzy full-cpu      # Build full image
.\docker\run_docker_win.ps1 run humble                # Run container
```

| Tag | Contents | PyTorch |
|-----|----------|---------|
| `:humble` | control + vision + interface + realsense + oakd | None |
| `:humble-full-cpu` | All above + AI | CPU |
| `:humble-full-cu124` | All above + AI | CUDA 12.4 |

See [`docker/README.md`](docker/README.md) for GPU, RealSense, and advanced options.

All versions and package lists live in [`scripts/lib/config.sh`](scripts/lib/config.sh). See [`docs/INSTALL.md`](docs/INSTALL.md) for the full guide.

## Architecture

*High-level architecture diagram showing main components and relationships. For detailed class diagrams, see module-specific READMEs: [Control](nectar/nectar/control/README.md), [Vision](nectar/nectar/vision/README.md), [AI](nectar/nectar/ai/README.md), [Interface](nectar/nectar/interface/README.md).*

```mermaid
classDiagram
    namespace Control {
        class DroneFactory {
            <<singleton>>
            +create(type, config, node)$ BaseDrone
            +register(type, factory_func)$
            +available_types()$ List~str~
        }
        class Drone {
            <<protocol>>
            +connect() bool
            +arm() bool
            +takeoff(altitude) bool
            +land() bool
            +move_to(x, y, z, yaw, reference, strategy) bool
            +move_to_gps(lat, lon, alt, heading, strategy) bool
            +move_velocity(vx, vy, vz, vyaw, reference)
            +rtl(altitude, strategy, land) bool
            +emergency_stop()
        }
        class BaseDrone {
            <<abstract>>
            +add_obstacle_detector(name, detector, strategy)
            +start_driver_process() bool
            +delay(seconds)
            +cleanup()
        }
        class MavrosDrone {
            -_navigator MavrosNavigator
            -_pose_source PoseSource
            +set_mode(mode) bool
            +get_altitude(source) Optional~float~
            +set_pid_config(config)
        }
        class BebopDrone {
            +flip(direction)
            +camera_control(tilt, pan)
        }
        class DroneConfig {
            <<dataclass>>
            +name str
            +start_driver bool
        }
        class MavrosConfig {
            <<dataclass>>
            +pose_source PoseSource
            +expect_lidar bool
            +connection_string str
        }
        class BebopConfig {
            <<dataclass>>
            +ip str
            +namespace str
        }
        class MavrosNavigator {
            +navigate_pid(target, precision, altitude_source) bool
            +navigate_setpoint(target, precision) bool
        }
        class PIDController {
            +update(current_value) float
            +reset()
            +tune(kp, ki, kd)
        }
        class GPSUtils {
            <<static>>
            +geoid_height(lat, lon)$ float
            +create_gps_setpoint(lat, lon, alt, heading)$ GeoPoseStamped
            +check_reached(cur, tgt, precision)$ tuple
        }
        class ObstacleManager {
            +should_continue_navigation(drone) bool
            +get_axis_control() tuple~bool,bool,bool~
            +add(name, handler)
            +enable(name)
        }
        class ObstacleHandler {
            -_detector ObstacleDetector
            -_strategy AvoidanceStrategy
            +should_continue(drone) bool
            +get_axis_modifiers() tuple~bool,bool,bool~
        }
        class ObstacleDetector {
            <<protocol>>
            +is_enabled bool
            +update() ObstacleInfo
            +enable()
            +disable()
        }
        class AvoidanceStrategy {
            <<abstract>>
            +execute(drone, info) bool
            +reset()
        }
        class PauseStrategy
        class DisableAxisStrategy {
            +disable_x bool
            +disable_y bool
            +disable_z bool
        }
        class SequenceStrategy {
            -_sequence_func Callable
        }
    }

    namespace Vision {
        class CameraFactory {
            <<singleton>>
            +from_source(source, config, node)$ AbstractCam
            +register(key, builder)$
        }
        class AbstractCam {
            <<abstract>>
            +name str
            +is_running bool
            +start()
            +get_frame() Optional~ndarray~
            +close()
        }
        class DepthCam {
            <<abstract>>
            +get_depth_frame() Optional~ndarray~
            +get_distance(u, v) Optional~float~
        }
        class OpenCVCam
        class RealsenseCam
        class OakdCam
        class ROSCam
        class ROSDepthCam {
            -_color_cam ROSCam
        }
        class ImageHandler {
            +node Node
            +camera AbstractCam
            +run()
            +take_photo() ndarray
            +cleanup()
        }
        class Aruco {
            +detect(img, draw) tuple
            +pose_estimate(img, draw) tuple
        }
        class ColorDetector {
            +filterColor(img)
            +initTrackbars()
            +saveColorValues()
        }
        class LineDetector {
            -color_detector ColorDetector
            -estimation_method ILineEstimationMethod
            +detect_line(img, region) tuple
        }
        class ILineEstimationMethod {
            <<abstract>>
            +estimate(img) tuple
        }
        class DistanceEstimator {
            -_model EstimationModel
            +estimate(value) float
            +compare_methods(value) Dict
        }
        class EstimationModel {
            <<abstract>>
            +estimate(value) float
            +fit(x, y) Dict
        }
        class HandTracker {
            +detect(frame, draw) ndarray
            +get_hands() List~HandResult~
            +raised_fingers(hand_idx) List~int~
        }
        class FaceMeshTracker {
            +detect(frame, draw) ndarray
            +get_faces() List~FaceResult~
            +get_eye_aspect_ratio(eye) float
        }
    }

    namespace AI {
        class Detector {
            +model_source str
            +framework Framework
            +is_loaded bool
            +load() bool
            +detect(image, conf) DetectionResult
            +detect_batch(images) List~DetectionResult~
            +train(config) TrainingResult
            +evaluate(config) EvaluationMetrics
            +draw_detections(image, result) ndarray
            +register(framework, builder)$
            +enable_slicing(config)
        }
        class Framework {
            <<enum>>
            ULTRALYTICS
            TRANSFORMERS
            RFDETR
        }
        class BaseDetectionModel {
            <<abstract>>
            +model_name str
            +is_loaded bool
            +load_model(path)
            +detect(image, conf) DetectionResult
            +train(config) TrainingResult
            +save(path) str
            +evaluate(config) EvaluationMetrics
        }
        class UltralyticsModel
        class TransformersModel
        class RFDETRModel
        class Detection {
            <<dataclass>>
            +xyxy ndarray
            +confidence float
            +class_id int
            +class_name str
        }
        class DetectionResult {
            <<dataclass>>
            +detections List~Detection~
            +inference_time float
            +filter_by_confidence(threshold) DetectionResult
            +filter_by_class_id(class_ids) DetectionResult
            +to_supervision() sv.Detections
        }
        class TrainingConfig {
            <<dataclass>>
            +dataset_path str
            +epochs int
            +batch_size int
            +push_to_hub bool
        }
        class EvaluationConfig {
            <<dataclass>>
            +model_path str
            +dataset_path str
            +conf_threshold float
        }
        class SlicingInference {
            -config SlicingConfig
            +run_sliced_inference(image, callback) sv.Detections
        }
        class BaseMergingStrategy {
            <<abstract>>
            +merge_boxes(detections) Tuple
        }
        class NMSStrategy
        class SoftNMSStrategy
        class WBFStrategy
        class NMMStrategy
        class ObjectDetectionEvaluator {
            +evaluate() EvaluationMetrics
        }
    }

    namespace Interface {
        class NectarApp {
            -_ros_executor ROSExecutor
            -_control_tab ControlTab
            -_vision_tab VisionTab
            -_ros_tab ROSTab
            +main()$
        }
        class ROSExecutor {
            +node Node
            +start(node_name) bool
            +shutdown()
        }
        class ControlTab {
            +set_node(node)
            +cleanup()
        }
        class VisionTab {
            +set_node(node)
            +cleanup()
        }
        class ROSTab {
            +set_node(node)
            +cleanup()
        }
    }

    namespace Utils {
        class GPSCalculate {
            <<static>>
            +haversine(lat1, lon1, lat2, lon2)$ float
            +bearing(lat1, lon1, lat2, lon2)$ float
            +calculate_gps_offset(x, y, z, lat, lon, alt, heading)$ tuple
            +interp_geo(start, end, frac)$ tuple
        }
        class PositionUtils {
            <<static>>
            +get_body_distance(target, current, heading)$ tuple
            +get_yaw_from_pose(pose)$ float
            +transform_takeoff_to_body_velocities(vx, vy, vz, current_yaw, takeoff_yaw)$ tuple
        }
        class ProcessUtils {
            <<static>>
            +start_process(command, name) bool
            +kill_process(name) bool
            +is_node_running(node_pattern) bool
            +wait_for_node(node_pattern, timeout) bool
        }
    }

    %% Control
    Drone <|.. BaseDrone : implements
    BaseDrone <|-- MavrosDrone
    BaseDrone <|-- BebopDrone
    DroneFactory ..> BaseDrone : creates
    DroneConfig <|-- MavrosConfig
    DroneConfig <|-- BebopConfig
    BaseDrone o-- DroneConfig
    MavrosDrone *-- MavrosNavigator
    MavrosNavigator ..> PIDController : creates
    MavrosNavigator ..> GPSUtils : uses
    MavrosNavigator ..> PositionUtils : uses
    BaseDrone o-- ObstacleManager
    ObstacleManager o-- ObstacleHandler
    ObstacleHandler *-- ObstacleDetector
    ObstacleHandler *-- AvoidanceStrategy
    AvoidanceStrategy <|-- PauseStrategy
    AvoidanceStrategy <|-- DisableAxisStrategy
    AvoidanceStrategy <|-- SequenceStrategy

    %% Vision
    AbstractCam <|-- DepthCam
    AbstractCam <|-- OpenCVCam
    AbstractCam <|-- ROSCam
    DepthCam <|-- RealsenseCam
    DepthCam <|-- OakdCam
    DepthCam <|-- ROSDepthCam
    ROSDepthCam *-- ROSCam
    CameraFactory ..> AbstractCam : creates
    ImageHandler o-- AbstractCam
    ImageHandler ..> CameraFactory : uses
    LineDetector o-- ILineEstimationMethod
    LineDetector o-- ColorDetector
    DistanceEstimator o-- EstimationModel

    %% AI
    Detector --> Framework
    Detector ..> BaseDetectionModel : creates
    BaseDetectionModel <|-- UltralyticsModel
    BaseDetectionModel <|-- TransformersModel
    BaseDetectionModel <|-- RFDETRModel
    BaseDetectionModel ..> DetectionResult : returns
    DetectionResult o-- Detection
    BaseDetectionModel ..> SlicingInference : uses
    SlicingInference ..> BaseMergingStrategy : uses
    BaseMergingStrategy <|-- NMSStrategy
    BaseMergingStrategy <|-- SoftNMSStrategy
    BaseMergingStrategy <|-- WBFStrategy
    BaseMergingStrategy <|-- NMMStrategy
    BaseDetectionModel ..> ObjectDetectionEvaluator : uses

    %% Interface
    NectarApp *-- ROSExecutor
    NectarApp *-- ControlTab
    NectarApp *-- VisionTab
    NectarApp *-- ROSTab
```

### Design Patterns

The codebase uses the same patterns across all modules, making it predictable to navigate and extend:

| Pattern | Where | What It Does |
|---------|-------|--------------|
| **Factory + Registry** | `DroneFactory`, `CameraFactory`, `Detector` | Decouples creation from usage. New types are registered at runtime and instantiated by key. |
| **Protocol** | `Drone`, `ObstacleDetector` | Defines interfaces via structural typing (duck typing). Any class matching the signature is accepted. |
| **Strategy** | `AvoidanceStrategy`, `ILineEstimationMethod`, `EstimationModel`, `BaseMergingStrategy` | Encapsulates interchangeable algorithms behind a common interface. |
| **Abstract Base Class** | `BaseDrone`, `AbstractCam`, `DepthCam`, `BaseDetectionModel` | Shares common logic and enforces method contracts for concrete implementations. |
| **Dataclass Config** | `MavrosConfig`, `OpenCVConfig`, `TrainingConfig`, `EvaluationConfig` | Type-safe configuration with defaults, validation, and YAML serialization. |

Every factory supports runtime registration, so adding a new drone type, camera driver, or detection framework follows the same pattern:

```python
# New drone
DroneFactory.register("custom", lambda cfg, node: MyDrone(cfg, node))
drone = DroneFactory.create("custom", config, node)

# New camera
CameraFactory.register("thermal", ThermalCamera)
camera = CameraFactory.from_source("thermal")

# New detection framework
Detector.register("custom", lambda name, **kw: CustomModel(name, **kw))
detector = Detector("model.bin", framework="custom")
```

## Documentation

| Document | Contents |
|----------|----------|
| [Installation Guide](docs/INSTALL.md) | Bootstrap, workspace setup, module install, PyTorch, RealSense, Docker, troubleshooting |
| [Control Module](nectar/nectar/control/README.md) | Drone protocol, factory, configuration, movement API, obstacle system |
| [MAVROS Implementation](nectar/nectar/control/mavros/README.md) | MAVLink, flight modes, coordinate frames, altitude types, PID vs setpoint, GPS utilities, ROS 2 topics/services |
| [Bebop Implementation](nectar/nectar/control/bebop/README.md) | Bebop 2 control, velocity, acrobatics |
| [Obstacle Detection](nectar/nectar/control/obstacles/README.md) | Detector protocol, avoidance strategies, handler configuration |
| [PID Controller](nectar/nectar/control/pid/README.md) | Tuning guide, YAML config, runtime updates, default indoor/outdoor configs |
| [Vision Module](nectar/nectar/vision/README.md) | Camera drivers, ArUco, color, line, distance, MediaPipe, nodes, calibration |
| [AI Module](nectar/nectar/ai/README.md) | Detector API, training, evaluation, device management |
| [Detection Module](nectar/nectar/ai/detection/README.md) | Class diagram, core types, framework configs, slicing, CLI, extension guide |
| [Interface Module](nectar/nectar/interface/README.md) | GUI tabs, widgets, threading model, camera integration, theming |
| [Nectar Interfaces](nectar_interfaces/README.md) | ROS 2 message definitions, Python/C++ usage |
| [Docker Guide](docker/README.md) | Build variants, GPU, RealSense, dependency strategy |
| [Contributing](docs/CONTRIBUTING.md) | Development setup, code style, PR process |
| [Releasing](docs/RELEASING.md) | Version bump, CI workflows, Docker Hub push |

## ROS 2 Nodes

Pre-built nodes for common tasks:

```bash
# GUI
ros2 run nectar app.py

# ArUco detection
ros2 run nectar aruco_node.py --ros-args \
    -p image_source:=webcam -p marker_dict:=5 -p tag_size:=0.05

# Line detection
ros2 run nectar line_detection_node.py --ros-args \
    -p line_colors:="blue,red" -p method:=HoughLinesP

# Color calibration
ros2 run nectar color_calibration_node.py --ros-args -p image_source:=webcam

# Camera calibration
ros2 run nectar calibration.py --ros-args -p chessboard_size:="9,7"

# Webcam publisher
ros2 run nectar webcam_publisher_node.py --ros-args -p width:=1280 -p height:=720

# Object detection
ros2 run nectar detector_example.py --ros-args -p model_source:=yolov8n.pt
```

## Examples

Working examples in `nectar/nectar/examples/`:

| Example | Description |
|---------|-------------|
| [basic.py](nectar/nectar/examples/control/basic.py) | Takeoff, velocity, land |
| [sensors.py](nectar/nectar/examples/control/sensors.py) | Monitor GPS/vision data |
| [pid_simulation.py](nectar/nectar/examples/control/pid_simulation.py) | PID controller simulation |
| [mavros_navigation.py](nectar/nectar/examples/control/mavros_navigation.py) | Navigation test (BODY, TAKEOFF, GPS references) |
| [mavros_obstacles.py](nectar/nectar/examples/control/mavros_obstacles.py) | Obstacle avoidance |
| [camera_example.py](nectar/nectar/examples/vision/camera_example.py) | Camera capture |
| [depth_example.py](nectar/nectar/examples/vision/depth_example.py) | Depth visualization |
| [detector_example.py](nectar/nectar/examples/ai/detector_example.py) | Object detection |
| [batch_detector.py](nectar/nectar/examples/ai/batch_detector.py) | Batch image/video processing |

See: [control examples](nectar/nectar/examples/control/README.md) · [vision examples](nectar/nectar/examples/vision/README.md) · [AI examples](nectar/nectar/examples/ai/README.md)

## Directory Structure

```
nectar-sdk/
├── scripts/                    # Setup and installation
│   ├── bootstrap.sh            # Standalone curl installer
│   ├── setup.sh                # CLI + interactive menu
│   └── lib/                    # Modular shell functions
│       ├── config.sh           # Versions, packages (single source of truth)
│       ├── common.sh           # Logging
│       ├── system.sh           # apt packages
│       ├── ros2.sh             # ROS 2 install + env
│       ├── python.sh           # pip from pyproject.toml
│       ├── realsense.sh        # Intel RealSense from source
│       ├── workspace.sh        # Build, clean, verify
│       └── git.sh              # Git/SSH setup
├── docker/
│   ├── Dockerfile              # x86_64: sdk + sdk-full stages
│   └── Dockerfile.jetson       # ARM64: Jetson Orin Nano
├── docs/
│   ├── INSTALL.md              # Full installation guide
│   ├── CONTRIBUTING.md         # Development setup, code style, PR process
│   ├── RELEASING.md            # Version bump, CI, Docker Hub push
│   └── SECURITY.md
├── nectar_interfaces/          # ROS 2 custom messages
│   ├── CMakeLists.txt
│   ├── package.xml
│   └── msg/
├── nectar/                     # Main ROS 2 package
│   ├── CMakeLists.txt
│   ├── package.xml
│   ├── pyproject.toml
│   └── nectar/                 # Python package
│       ├── control/            # Drone control
│       ├── vision/             # Computer vision
│       ├── ai/                 # AI / detection
│       ├── interface/          # Qt6 GUI
│       ├── examples/
│       └── utils/
├── Makefile
└── README.md
```

## Contributing

We welcome contributions. Please see [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) for development setup, code style (PEP 8, NumPy docstrings, type hints), and the PR process.

1. Check [GitHub Issues](https://github.com/Black-Bee-Drones/nectar-sdk/issues) for existing discussions
2. Follow [Conventional Commits](https://www.conventionalcommits.org) for commit messages
3. Read our [Code of Conduct](docs/CODE_OF_CONDUCT.md)

<div align="center">
<a href="https://github.com/Black-Bee-Drones/nectar-sdk/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Black-Bee-Drones/nectar-sdk&max=100" alt="Contributors" />
</a>
</div>

## Black Bee Drones

[Black Bee Drones](https://github.com/Black-Bee-Drones) is Latin America's first academic autonomous drone team. Founded as a research project at the [Federal University of Itajuba](https://unifei.edu.br/) (UNIFEI) in 2014, the team develops unmanned aircraft for complex missions requiring computer vision and artificial intelligence. We compete nationally and internationally, including [IMAV](https://www.imavs.org/) (3rd place indoor 2023 and 2025, 3rd place outdoor 2015, best autonomous indoor flight worldwide), and participate in events like DroneShow LA and Campus Party.

Nectar SDK started in 2023 as a way to stop rewriting the same camera, PID, and detection code for each competition mission. It evolved into a ROS 2 package with consistent interfaces across drone control, computer vision, and AI detection — the shared foundation our team uses for every project. It has been turned into an open-source project to enable continuous development and to help other teams and researchers build autonomous systems more rapidly.

## Acknowledgments

Nectar SDK exists because of the open source projects it builds on. We are grateful to the [ROS 2](https://docs.ros.org/) community and Open Robotics for the middleware that connects everything. [MAVROS](https://github.com/mavlink/mavros) and the [MAVLink](https://mavlink.io/) protocol for bridging ROS 2 with [ArduPilot](https://ardupilot.org/) and [PX4](https://docs.px4.io/) flight controllers. [OpenCV](https://opencv.org/) for the computer vision foundation. [Ultralytics](https://docs.ultralytics.com/), [HuggingFace](https://huggingface.co/), and [Roboflow](https://roboflow.com/) for making object detection accessible through YOLO, Transformers, RF-DETR, and supervision. [PyTorch](https://pytorch.org/) for the deep learning backend. [Intel RealSense](https://github.com/IntelRealSense/librealsense) and [Luxonis](https://docs.luxonis.com/) for depth camera SDKs. [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions) for hand and face tracking. [Qt for Python](https://doc.qt.io/qtforpython-6/) for the GUI framework.

## License

This project is licensed under the Apache-2.0 License — see the [`LICENSE`](LICENSE) file for details.
