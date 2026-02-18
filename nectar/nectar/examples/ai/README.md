# AI Examples

Reference implementations for deep learning-based object detection.

## Overview

| Example | Script | Description |
|---------|--------|-------------|
| **Detector Stream** | `detector_example.py` | Real-time object detection from camera stream with ROS2 integration |
| **Batch Detector** | `batch_detector.py` | Offline processing of image directories or video files |

## Supported Frameworks

| Framework | Models | Example |
|-----------|--------|---------|
| **Ultralytics** | YOLOv8, YOLOv10, YOLO11 | `yolov8n.pt`, `yolov11n.pt` |
| **Transformers** | DETR, Conditional DETR | `facebook/detr-resnet-50` |
| **RF-DETR** | RF-DETR variants | `rfdetr-base` |

---

## Real-time Detection Stream

Camera stream detection using `Detector` + `ImageHandler`.

### Usage

```bash
# Default (webcam + YOLO with auto GPU detection)
ros2 run nectar detector_example

# Explicit framework specification
ros2 run nectar detector_example --ros-args \
    -p model_source:="facebook/detr-resnet-50" \
    -p framework:="transformers"

# Custom YOLO model from HuggingFace
ros2 run nectar detector_example --ros-args \
    -p model_source:="blackbeedrones/cbr-25-base:yolov11n.pt"

# Private HuggingFace model (with token)
export HF_TOKEN="hf_your_token_here"
ros2 run nectar detector_example

# Or pass token as parameter
ros2 run nectar detector_example --ros-args -p hf_token:="hf_your_token_here"

# Local model file
ros2 run nectar detector_example --ros-args -p model_source:="/path/to/model.pt"

# Device selection
ros2 run nectar detector_example --ros-args -p device:="cuda"   # Force GPU
ros2 run nectar detector_example --ros-args -p device:="cpu"    # Force CPU
ros2 run nectar detector_example --ros-args -p device:="0"      # Specific GPU
ros2 run nectar detector_example --ros-args -p device:="auto"   # Auto-detect (default)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_source` | string | `yolov8n.pt` | Model path or HuggingFace repo |
| `framework` | string | "" | Explicit framework: `ultralytics`, `transformers`, `rfdetr` (empty = auto-detect) |
| `confidence` | float | 0.25 | Detection confidence threshold |
| `camera_source` | string | webcam | Camera source identifier |
| `show_result` | bool | true | Display detection window |
| `annotator_type` | string | color | Annotation style: `box`, `round_box`, `color` |
| `show_labels` | bool | true | Show class labels |
| `show_confidence` | bool | true | Show confidence scores |
| `show_class` | bool | true | Show class names |
| `device` | string | auto | Device: `auto`, `cpu`, `cuda`, `0`, `1` |
| `hf_token` | string | "" | HuggingFace API token |

### Annotation Styles

| Style | Rendering |
|-------|-----------|
| `box` | Rectangle outline |
| `round_box` | Rounded corner rectangle |
| `color` | Filled region with alpha overlay |

### Statistics Overlay

The stream displays real-time statistics:
- **Framework**: Detection framework being used
- **FPS**: Frames per second (based on inference time)
- **Detections**: Current frame detection count
- **Total**: Cumulative detections

---

## Batch Detector

Standalone script for offline processing of image sequences or video files.

### Usage

```bash
# Process image directory (auto-detect framework)
python3 batch_detector.py \
    --input /path/to/images \
    --output-dir ./results

# Process video file
python3 batch_detector.py \
    --input /path/to/video.mp4 \
    --output-dir ./results

# Explicit framework specification
python3 batch_detector.py \
    --input /path/to/images \
    --model-source yolov8n.pt \
    --framework ultralytics \
    --output-dir ./results

# Transformers DETR model
python3 batch_detector.py \
    --input /path/to/images \
    --model-source facebook/detr-resnet-50 \
    --framework transformers \
    --output-dir ./results

# HuggingFace model
python3 batch_detector.py \
    --input /path/to/images \
    --model-source "blackbeedrones/cbr-25-base:yolov11n.pt" \
    --output-dir ./results

# Full options
python3 batch_detector.py \
    --input /path/to/video.mp4 \
    --output-dir ./results \
    --model-source yolov8n.pt \
    --framework ultralytics \
    --confidence 0.5 \
    --device cuda \
    --annotator-type round_box \
    --fps 30
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--input` | string | required | Image directory or video file |
| `--output-dir` | string | required | Output directory for results |
| `--model-source` | string | `yolov8n.pt` | Model path or HuggingFace format |
| `--framework` | string | "" | Framework: `ultralytics`, `transformers`, `rfdetr` (empty = auto) |
| `--confidence` | float | 0.5 | Detection confidence threshold |
| `--device` | string | auto | Compute device |
| `--annotator-type` | string | box | Annotation style |
| `--hide-labels` | flag | false | Hide detection labels |
| `--hide-confidence` | flag | false | Hide confidence scores |
| `--fps` | int | 30 | Output video FPS (images only) |

### Output Structure

```
output-dir/
├── detection_video.mp4    # Annotated video with all frames
├── frames/                # Individual annotated frames
│   ├── frame_0000.jpg
│   ├── frame_0001.jpg
│   └── ...
└── extracted_frames/      # (video input only) Original frames
    ├── frame_000000.jpg
    └── ...
```

### Video Processing

For video input, the batch detector:
1. Extracts all frames to temporary directory
2. Processes each frame with the selected model
3. Reconstructs video at original FPS
4. Saves individual annotated frames
