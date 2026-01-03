# Vision Module

Computer vision tools for camera management and image processing algorithms, built for the Mirela SDK.

## Features

- **Multi-Camera Support**: Unified interface for webcams, RealSense, OAK-D, IMX219, and ROS topics
- **Camera Calibration**: Chessboard-based calibration for accurate measurements
- **ArUco Markers**: Detection and 6-DOF pose estimation
- **Color Detection**: HSV/LAB color space filtering with calibration tools
- **Line Detection**: Multiple estimation methods (Hough, RANSAC, ellipse fitting)
- **Distance Estimation**: Pixel-to-distance conversion with multiple models
- **ROS2 Integration**: Ready-to-use nodes for common vision tasks

## Quick Start

### Camera Usage

```python
import rclpy
from rclpy.node import Node
from mirela_sdk.vision import ImageHandler, OpenCVConfig

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        
        self.handler = ImageHandler(
            node=self,
            image_source="webcam",
            config=OpenCVConfig(width=1280, height=720),
            show_result="Camera View"
        )
        self.handler.run()

rclpy.init()
node = CameraNode()
rclpy.spin(node)
```

### ArUco Detection

```python
from mirela_sdk.vision import Aruco, ImageHandler

class ArucoDetector(Node):
    def __init__(self):
        super().__init__('aruco_detector')
        
        self.aruco = Aruco(marker_dict=5, tag_size=0.05)
        
        self.handler = ImageHandler(
            node=self,
            image_source="webcam",
            image_processing_callback=self.process_frame
        )
        self.handler.run()
    
    def process_frame(self, image):
        marker_id, translation, yaw = self.aruco.pose_estimate(image, draw=True)
        if marker_id is not None:
            self.get_logger().info(f"Detected marker {marker_id} at {translation}")
```

### Line Detection

```python
from mirela_sdk.vision import LineDetector, HoughLinesP, ColorSpace

detector = LineDetector(
    color="blue",
    estimation_method=HoughLinesP,
    color_space=ColorSpace.HSV
)

result, mask, cx, cy, angle, width, height = detector.detect_line(image, draw=True)
```

## Module Structure

```
vision/
├── camera/                 # Camera infrastructure
│   ├── drivers/           # Camera implementations
│   ├── calibration/       # Camera calibration
│   ├── abstract.py        # Base camera interfaces
│   ├── config.py          # Configuration dataclasses
│   ├── factory.py         # Camera factory
│   └── handler.py         # Image handler
│
├── algorithms/            # Vision algorithms
│   ├── markers/          # ArUco, AprilTag, etc.
│   ├── color/            # Color detection
│   ├── line/             # Line detection
│   └── distance/         # Distance estimation
│
├── utils/                # Utilities
│   └── gps_calculus.py   # GPS coordinate calculations
│
└── nodes/                # ROS2 nodes
    ├── aruco_node.py
    ├── color_calibration_node.py
    ├── line_detection_node.py
    └── webcam_publisher_node.py
```

## Available Cameras

| Camera | Class | Features |
|--------|-------|----------|
| Generic Webcam | `OpenCVCam` | Standard USB cameras |
| Logitech C920 | `C920Cam` | Optimized for C920/C920e |
| IMX219 | `IMX219Cam` | Raspberry Pi camera v2 |
| RealSense | `RealsenseCam` | RGB-D, depth sensing |
| OAK-D | `OakdCam` | Depth, stereo, AI |
| ROS Topic | `ROSCam` | Subscribe to image topics |
| File | `FileImageCam` | Static image files |

### Camera Configuration Examples

```python
from mirela_sdk.vision.camera import (
    OpenCVConfig,
    RealSenseConfig,
    OakDConfig,
    ROSConfig,
)

webcam_config = OpenCVConfig(
    device_index=0,
    width=1280,
    height=720,
    fps=30
)

realsense_config = RealSenseConfig(
    color_res=(1280, 720),
    depth_res=(1280, 720),
    fps=30,
    enable_depth=True
)

oakd_config = OakDConfig(
    cam_num=1,
    enable_depth=True
)

ros_config = ROSConfig(
    topic="/camera/image_raw",
    compressed=True
)
```

## ROS2 Nodes

### ArUco Detection Node

```bash
ros2 run mirela_sdk aruco_node --ros-args \
    -p image_source:=webcam \
    -p marker_dict:=5 \
    -p tag_size:=0.05
```

**Published Topics:**
- `/aruco/pose_estimate` (`mirela_interfaces/ArucoTransforms`)

### Color Calibration Node

```bash
ros2 run mirela_sdk color_calibration_node --ros-args \
    -p image_source:=webcam \
    -p color_space:=hsv
```

Interactive trackbars for HSV/LAB calibration.

### Line Detection Node

```bash
ros2 run mirela_sdk line_detection_node --ros-args \
    -p image_source:=webcam \
    -p color:=blue \
    -p estimation_method:=hough
```

**Published Topics:**
- `/line/info` (`mirela_interfaces/LineInfo`)

### Webcam Publisher

```bash
ros2 run mirela_sdk webcam_publisher --ros-args \
    -p device:=0 \
    -p width:=1280 \
    -p height:=720 \
    -p compressed:=true
```

**Published Topics:**
- `/webcam/image_raw/compressed` (`sensor_msgs/CompressedImage`)
- `/webcam/image_raw` (`sensor_msgs/Image`)

## Camera Calibration

Calibrate your camera for accurate pose estimation:

```bash
ros2 run mirela_sdk camera_calibration --ros-args \
    -p chessboard_size:=7x5
```

Follow the on-screen instructions to capture calibration images. Results are saved to:
- `vision/camera/calibration/camera_matrix.txt`
- `vision/camera/calibration/camera_distortion.txt`

## Algorithms

### Markers

**ArUco Detection**
```python
from mirela_sdk.vision import Aruco

aruco = Aruco(marker_dict=5, tag_size=0.05)
bbox, marker_id = aruco.detect(image, draw=True)
marker_id, translation, yaw = aruco.pose_estimate(image, draw=True)
```

### Color Detection

```python
from mirela_sdk.vision import ColorDetector, ColorSpace

detector = ColorDetector(mode="preset", color="red", color_space=ColorSpace.HSV)
mask = detector.filterColor(image)
```

**Calibration Mode:**
```python
detector = ColorDetector(mode="track", color="custom")
detector.initTrackbars()
mask = detector.filterColor(image)
detector.saveColorHSV()
```

### Line Detection

**Available Methods:**
- `HoughLinesP`: Probabilistic Hough transform
- `RotatedRect`: Minimum area rectangle
- `FitEllipse`: Ellipse fitting for curves
- `RansacLine`: RANSAC-based robust fitting
- `AdaptiveHoughLinesP`: Adaptive parameter tuning

```python
from mirela_sdk.vision import LineDetector, RotatedRect

detector = LineDetector(color="blue", estimation_method=RotatedRect)
img, mask, cx, cy, angle, width, height = detector.detect_line(image, draw=True)
```

### Distance Estimation

```python
from mirela_sdk.vision import DistanceEstimator, EstimationMethod

estimator = DistanceEstimator(
    default_method=EstimationMethod.POLYNOMIAL,
    valid_range=(15.0, 35.0)
)

distance_cm = estimator.estimate(pixel_measurement)
```

**Calibration:**
```python
from mirela_sdk.vision import DistanceCalibrator

calibrator = DistanceCalibrator()
calibrator.add_data_points([
    (50, 32.2),
    (60, 28.5),
    (100, 21.6),
])

result = calibrator.calibrate_polynomial(degree=2)
estimator = calibrator.create_estimator_from_calibration()
```

## Common Types

```python
from mirela_sdk.vision import Point2D, Point3D, BoundingBox, Pose

point = Point2D(x=100.0, y=200.0)
bbox = BoundingBox(x1=50, y1=50, x2=150, y2=150)

center = bbox.center
area = bbox.area
```

## Error Handling

```python
from mirela_sdk.vision import VisionError, CameraError, CalibrationError

try:
    camera = CameraFactory.from_source("invalid_source")
except CameraError as e:
    print(f"Camera error: {e}")
except VisionError as e:
    print(f"Vision error: {e}")
```

## Examples

See the `examples/` directory for complete working examples:
- `camera_example.py` - Basic camera usage
- `depth_example.py` - Depth camera visualization
- `yolo_example.py` - YOLO detection with camera

## Migration from `image_processing`

See `MIGRATION_GUIDE.md` for details on migrating from the old `image_processing` module.

**Quick migration:**
```python
from mirela_sdk.image_processing.camera import ImageHandler
from mirela_sdk.vision.camera import ImageHandler
```

## Documentation

- **Main README**: This file
- **Camera**: `camera/README.md`
- **Calibration**: `camera/calibration/README.md`
- **Migration Guide**: `../MIGRATION_GUIDE.md`

## Contributing

When adding new features:
1. Camera drivers go in `camera/drivers/`
2. Algorithms go in `algorithms/<category>/`
3. ROS2 nodes go in `nodes/`
4. Add exports to `__init__.py`
5. Update this README

