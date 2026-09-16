# Vision Examples

Working examples for the vision module's camera drivers and image processing.

| Example | Script | What it does |
|---------|--------|--------------|
| **Camera Capture** | `camera_example.py` | Multi-camera support with configuration options |
| **Depth Visualization** | `depth_example.py` | RGB-D camera depth measurement and colormap display |
| **T265 Tracking** | `t265_example.py` | RealSense T265 pose/odometry (direct SDK or ROS) |
| **Optical Flow** | `optical_flow_example.py` | Sparse/dense optical-flow visualization |
| **Photo Collection** | `collect_photos.py` | Save frames at intervals for dataset creation |

All scripts use `argparse` flags (not `--ros-args -p`). Run with `python3 <script>.py [flags]`.
Some scripts are also installed as ROS 2 executables (`ros2 run nectar <script>.py -- [flags]`):
`camera_example.py`, `depth_example.py`, `t265_example.py`, `collect_photos.py`. Use `python3`
for `optical_flow_example.py` (not installed as an executable).

## Camera Example

Camera capture using `ImageHandler` with configurable backends.

### Usage

Run with the default webcam, or pass `--source` plus any camera flags from `ros2 run nectar camera_example.py --help`; add `--no-show` to run headless.

```bash
python3 camera_example.py
python3 camera_example.py --source realsense
python3 camera_example.py --source webcam --device-index 1 --width 1280 --height 720
```

### Arguments

Shared camera/stream flags (`--source`, `--device-index`, `--width`, `--show` / `--no-show`, …). See the [vision nodes](../vision/nodes/README.md) shared-flags table.

### Supported Camera Types

| `--source` | Driver | Notes |
|------------|--------|-------|
| `webcam` / `opencv` | `OpenCVCam` | `--device-index`, `--width`, `--height`, `--fps` |
| `realsense` | `RealsenseCam` | `--color-width`, `--color-height`, `--enable-depth` |
| `ros_depth` | `ROSDepthCam` | `--topic`, `--depth-topic` |
| `oakd` | `OakdCam` | `--cam-num`, `--enable-depth` (default off) |
| `c920` | `C920Cam` | `--profile` |
| `imx219` | `IMX219Cam` | `--sensor-id`, `--width` default 1920 |
| `ros` | `ROSCam` | `--topic`, `--compressed` |
| `/topic` or a file path | auto | Same rules as `CameraFactory.from_source` |

---

## Depth Example

Demonstrates depth camera usage with interactive distance measurement.

### Usage

| Source | Command |
|--------|---------|
| RealSense (direct pyrealsense2 SDK) | `python3 depth_example.py --source realsense` |
| RealSense via ROS topics | `python3 depth_example.py --source ros_depth` |
| OAK-D | `python3 depth_example.py --source oakd --enable-depth` |

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

Runs in direct-SDK mode by default; see the arguments below for ROS mode and the depth toggle.

```bash
python3 t265_example.py
python3 t265_example.py --use-ros-topics
```

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `t265` | Must stay `t265` |
| `--use-ros-topics` / `--no-use-ros-topics` | off | Subscribe to fisheye/pose topics instead of the SDK |
| `--enable-depth` / `--no-enable-depth` | on | Stereo depth path |

---

## Optical Flow

Sparse (Lucas-Kanade) or dense (Farneback) optical flow. With `--focal`/`--altitude` it also decodes angular rate (rad/s) and horizontal velocity (m/s), like the ArduPilot OPTICAL_FLOW pipeline.

| Case | Command |
|------|---------|
| Webcam, dense Farneback (default) | `python3 optical_flow_example.py` |
| RealSense, sparse Lucas-Kanade | `python3 optical_flow_example.py --source realsense --method lucas_kanade` |
| Any ROS image topic | `python3 optical_flow_example.py --source /camera/image_raw` |
| Decode angular rate + horizontal velocity | `python3 optical_flow_example.py --focal 500 --altitude 1.5` |
| Headless | `python3 optical_flow_example.py --no-show` |

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

| Case | Command |
|------|---------|
| Default (webcam, 1 photo/s, timestamped folder) | `python3 collect_photos.py` |
| Custom output dir and interval (2 photos/s) | `python3 collect_photos.py --output-dir hook_photos --capture-interval 0.5` |
| Named run for a flight session | `python3 collect_photos.py --output-dir hook_photos --run-name flight_01_low_alt` |
| RealSense with preview window | `python3 collect_photos.py --source realsense --show` |
| High-res webcam, PNG, max 500 photos | `python3 collect_photos.py --width 1920 --height 1080 --image-format png --max-photos 500` |

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | `webcam` | Camera source (shared camera flags; see `--help`) |
| `--output-dir` | `collected_photos` | Base output directory under `~/` |
| `--run-name` | *(timestamp)* | Sub-folder name for this run |
| `--capture-interval` | `1.0` | Seconds between captures |
| `--image-format` | `jpg` | Output format: `jpg` or `png` |
| `--jpeg-quality` | `80` | JPEG quality 0-100 |
| `--show` | off | Show live OpenCV preview window |
| `--max-photos` | `0` | Stop after N photos (0 = unlimited) |
| `--width` / `--height` / `--fps` | dataclass defaults | Capture settings when the driver uses them |
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
# Registered: webcam, opencv, realsense, t265, oakd, c920, imx219, ros, ros_depth, file
```

### RealSense Import Error

```
RuntimeError: pyrealsense2 is not installed
```

Install librealsense and realsense-ros (builds matching pyrealsense2 from source):

```bash
make realsense
# T265 (Humble only): LIBREALSENSE_VERSION=v2.53.1 REALSENSE_ROS_TAG=4.51.1 make realsense
```

Or use ROS topic mode (`--source ros_depth`) with `realsense2_camera` already running.

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
