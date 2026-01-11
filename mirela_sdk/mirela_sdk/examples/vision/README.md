# Vision Examples

Working examples for vision module camera drivers and image processing.

## Overview

| Example | Script | Description |
|---------|--------|-------------|
| **Camera Capture** | `camera_example.py` | Multi-camera support with configuration options |
| **Depth Visualization** | `depth_example.py` | RGB-D camera depth measurement and colormap display |

## Camera Example

Camera capture using `ImageHandler` with configurable backends.

### Usage

```bash
# Webcam (default)
ros2 run mirela_sdk camera_example

# Specific camera type
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=webcam
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=realsense
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=oakd
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=c920
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=imx219

# RealSense via ROS topics
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=realsense_ros

# ROS topic subscription
ros2 run mirela_sdk camera_example --ros-args -p camera_type:=ros

# Disable display window
ros2 run mirela_sdk camera_example --ros-args -p show_result:=false
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `camera_type` | string | webcam | Camera source (see below) |
| `show_result` | bool | true | Display OpenCV window |

### Supported Camera Types

| Type | Driver | Configuration |
|------|--------|---------------|
| `webcam` | `OpenCVCam` | 1280x720 @ 30fps, device 0 |
| `realsense` | `RealsenseCam` | 1280x720 RGB+Depth @ 30fps |
| `realsense_ros` | `RealsenseCam` | Via ROS topics (compressed color) |
| `oakd` | `OakdCam` | Default OAK-D settings |
| `c920` | `C920Cam` | Profile 1 (1280x720) |
| `imx219` | `IMX219Cam` | 1280x720 @ 30fps, flip 180° |
| `ros` | `ROSCam` | `/camera/color/image_raw/compressed` |

---

## Depth Example

Demonstrates depth camera usage with interactive distance measurement.

### Usage

```bash
# RealSense with pyrealsense2 (direct SDK)
ros2 run mirela_sdk depth_example --camera realsense

# RealSense via ROS topics
ros2 run mirela_sdk depth_example --camera realsense_ros

# OAK-D
ros2 run mirela_sdk depth_example --camera oakd
```

### Features

- **RGB Display**: Color image with crosshair at selected pixel
- **Depth Colormap**: Plasma colormap visualization (0.1m - 3.0m range)
- **Interactive Selection**: Click on color image to select measurement point
- **Distance Display**: Real-time distance in meters at selected pixel

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit application |
| Mouse click | Select pixel for distance measurement |

---

## Troubleshooting

### Camera Not Found

```
ValueError: Unknown camera source type: xyz
```

Check registered camera types:
```python
from mirela_sdk.vision.camera import CameraFactory
# Registered: webcam, opencv, realsense, oakd, c920, imx219, ros, file
```

### RealSense Import Error

```
RuntimeError: pyrealsense2 is not installed
```

Install librealsense:
```bash
# See scripts/install_realsense.sh
# Or use ROS topic mode (realsense_ros)
```

### OAK-D Import Error

```
ModuleNotFoundError: No module named 'depthai'
```

Install DepthAI:
```bash
pip install depthai
```

### Low FPS / Frame Drops

Adjust buffer and threading settings:
```python
config = OpenCVConfig(
    buffer_size=2,    # Increase if dropping frames
    threaded=True,    # Enable background capture
)
```

### Display Not Working

```
cv2.error: The function is not implemented
```

OpenCV headless build. Options:
- Install `opencv-python` instead of `opencv-python-headless`
- Disable display: `show_result=None`

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `opencv-python` | Camera capture, image processing |
| `numpy` | Array operations |
| `rclpy` | ROS2 Python client |
| `cv_bridge` | ROS image conversion |
| `pyrealsense2` | RealSense SDK (optional) |
| `depthai` | OAK-D SDK (optional) |
