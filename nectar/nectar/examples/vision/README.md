# Vision Examples

Working examples for vision module camera drivers and image processing.

## Overview

| Example | Script | Description |
|---------|--------|-------------|
| **Camera Capture** | `camera_example.py` | Multi-camera support with configuration options |
| **Depth Visualization** | `depth_example.py` | RGB-D camera depth measurement and colormap display |
| **T265 Tracking** | `t265_example.py` | RealSense T265 pose/odometry (direct SDK or ROS) |
| **Optical Flow** | `optical_flow_example.py` | Sparse/dense optical-flow visualization |
| **Photo Collection** | `collect_photos.py` | Save frames at intervals for dataset creation |

All scripts use `argparse` flags (not `--ros-args -p`). Run with `python3 <script>.py [flags]` or `ros2 run nectar <script>.py -- [flags]`.

## Camera Example

Camera capture using `ImageHandler` with configurable backends.

### Usage

```bash
# Webcam (default)
python3 camera_example.py

# Specific camera type
python3 camera_example.py --camera-type webcam
python3 camera_example.py --camera-type realsense
python3 camera_example.py --camera-type oakd
python3 camera_example.py --camera-type c920
python3 camera_example.py --camera-type imx219

# RealSense via ROS topics, or a plain ROS image topic
python3 camera_example.py --camera-type realsense_ros
python3 camera_example.py --camera-type ros

# Disable display window
python3 camera_example.py --camera-type webcam --no-show
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--camera-type` | `webcam` | Camera source: `webcam`, `imx219`, `realsense`, `realsense_ros`, `oakd`, `c920`, `ros` |
| `--no-show` | off | Disable the OpenCV display window |

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
python3 depth_example.py --camera realsense

# RealSense via ROS topics
python3 depth_example.py --camera realsense_ros

# OAK-D
python3 depth_example.py --camera oakd
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

## T265 Tracking

RealSense T265 tracking camera pose/odometry, either through the direct SDK or via ROS topics.

```bash
python3 t265_example.py --mode direct     # pyrealsense2 (default)
python3 t265_example.py --mode ros        # subscribe to ROS odometry/pose topics
python3 t265_example.py --no-depth        # skip the fisheye depth path
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `direct` | `direct` (pyrealsense2) or `ros` (ROS topics) |
| `--no-depth` | off | Disable the depth/fisheye path |

---

## Optical Flow

Sparse (Lucas-Kanade) or dense (Farneback) optical flow. With `--focal`/`--altitude` it also decodes angular rate (rad/s) and horizontal velocity (m/s), like the ArduPilot OPTICAL_FLOW pipeline.

```bash
python3 optical_flow_example.py                                   # webcam, Farneback
python3 optical_flow_example.py --source realsense --method lucas_kanade
python3 optical_flow_example.py --source /camera/image_raw       # any ROS image topic
python3 optical_flow_example.py --focal 500 --altitude 1.5       # decode rad/s + m/s
python3 optical_flow_example.py --no-show                        # headless
```

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `webcam` | Camera key (`webcam`, `realsense`, `oakd`, `c920`, `imx219`), a ROS topic (`/...`), or an image/video file path |
| `--method` | `farneback` | `farneback` (dense) or `lucas_kanade` (sparse) |
| `--focal` | `0` | Camera focal length in px (0 skips rad/s and m/s decode) |
| `--altitude` | `0` | Camera height in m (0 skips m/s decode) |
| `--no-show` | off | Disable the preview window |

---

## Photo Collection

Captures frames at a configurable interval and saves them to an organized directory structure. Useful for building training datasets — fly the drone via RC or the Nectar interface while this node records frames.

### Usage

```bash
# Default (webcam, 1 photo/sec, timestamped run folder)
python3 collect_photos.py

# Custom output directory and interval (2 photos/sec)
python3 collect_photos.py --output-dir hook_photos --capture-interval 0.5

# Named run for a specific flight session
python3 collect_photos.py --output-dir hook_photos --run-name flight_01_low_alt

# RealSense camera with preview window
python3 collect_photos.py --camera-type realsense --show

# High-res webcam, PNG format, max 500 photos
python3 collect_photos.py --width 1920 --height 1080 --image-format png --max-photos 500
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--camera-type` | `webcam` | Camera source (same set as `camera_example.py`) |
| `--output-dir` | `collected_photos` | Base output directory under `~/` |
| `--run-name` | *(timestamp)* | Sub-folder name for this run |
| `--capture-interval` | `1.0` | Seconds between captures |
| `--image-format` | `jpg` | Output format: `jpg` or `png` |
| `--jpeg-quality` | `90` | JPEG quality 0-100 |
| `--show` | off | Show live OpenCV preview window |
| `--max-photos` | `0` | Stop after N photos (0 = unlimited) |
| `--width` / `--height` / `--fps` | `1280` / `720` / `30` | Capture settings |
| `--publish` / `--publish-topic` / `--publish-scale` | off / `collect_photos/compressed` / `0.5` | Re-publish captured frames as a compressed image topic |

### Output Structure

```
~/hook_photos/
├── flight_01_low_alt/
│   ├── frame_00001.jpg
│   ├── frame_00002.jpg
│   └── ...
├── flight_02_high_alt/
│   ├── frame_00001.jpg
│   └── ...
└── 20260416_143022/          # auto-named when run_name is empty
    └── ...
```

---

## Troubleshooting

### Camera Not Found

```
ValueError: Unknown camera source type: xyz
```

Check registered camera types:
```python
from nectar.vision.camera import CameraFactory
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
