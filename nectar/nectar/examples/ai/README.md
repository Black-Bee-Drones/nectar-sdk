# AI Examples

Reference implementations for deep learning-based object detection and segmentation,
across every supported framework.

| Example | Script | What it does |
|---------|--------|--------------|
| **Detector Stream** | `detector_example.py` | Real-time object detection from a camera stream with ROS 2 integration |
| **Batch Detector** | `batch_detector.py` | Offline processing of image directories or video files |
| **Sequence Inference** | `sequence_inference.py` | Multi-model detection + segmentation over an image dir or video, annotated MP4 output |

## Supported Frameworks

| Framework | Models | Example |
|-----------|--------|---------|
| **Ultralytics** | YOLOv8, YOLOv10, YOLO11 | `yolov8n.pt`, `yolov11n.pt` |
| **Transformers** | DETR, Conditional DETR | `facebook/detr-resnet-50` |
| **RF-DETR** | RF-DETR Nano/Small/Medium/Large | `rfdetr-medium` |

---

## Real-time Detection Stream

Camera stream detection using `Detector` + `ImageHandler`.

### Usage

```bash
# Default (webcam + YOLO with auto GPU detection)
python3 detector_example.py

# Explicit framework
python3 detector_example.py --model facebook/detr-resnet-50 --framework transformers

# Custom YOLO model from HuggingFace
python3 detector_example.py --model "blackbeedrones/cbr-25-base:yolov11n.pt"

# Private HuggingFace model (env var or flag)
export HF_TOKEN="hf_your_token_here" && python3 detector_example.py
python3 detector_example.py --hf-token hf_your_token_here

# Local model file, headless, republish annotated frames as a ROS topic
python3 detector_example.py --model /path/to/model.pt --no-show --publish --topic /inference/compressed

# Device selection
python3 detector_example.py --device cuda   # GPU
python3 detector_example.py --device cpu    # CPU
python3 detector_example.py --device 0      # specific GPU
python3 detector_example.py --device auto   # auto-detect (default)
```

### Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `yolov8n.pt` | Model path or HuggingFace repo |
| `--framework` | "" | Explicit framework: `ultralytics`, `transformers`, `rfdetr` (empty = auto-detect) |
| `--confidence` | `0.25` | Detection confidence threshold |
| `--camera-source` | `webcam` | Camera source identifier |
| `--no-show` | off | Disable the detection window (default shows it) |
| `--annotator-type` | `color` | Annotation style: `box`, `round_box`, `color` |
| `--show-labels` / `--show-confidence` / `--show-class` | on | Toggle overlay fields |
| `--device` | `auto` | Device: `auto`, `cpu`, `cuda`, `0`, `1` |
| `--hf-token` | "" | HuggingFace API token (or `HF_TOKEN` env var) |
| `--publish` / `--topic` / `--jpeg-quality` | off / `/inference/compressed` / `80` | Republish annotated frames as a compressed image topic |

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

---

## Sequence Inference

Runs one or more models (detection and/or segmentation) over an image directory or video and writes an annotated MP4 (plus per-frame JPGs). Suffix a model with `@detection` / `@segmentation` to override task auto-detection.

```bash
# Single detection model over an image folder
python3 sequence_inference.py --input ./frames --output-dir ./out --models yolov8n.pt

# Detection + segmentation, per-class confidence, custom palette
python3 sequence_inference.py --input clip.mp4 --output-dir ./out \
    --models cbr.pt@detection seg.pt@segmentation \
    --conf 0.25 --class-conf "rose=0.47,sphere=0.70" --palette contrast
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | required | Image directory or video file |
| `--output-dir` | required | Output root directory |
| `--models` | required | One or more model sources (`@detection`/`@segmentation` suffix optional) |
| `--conf` | `0.25` | Default/fallback confidence threshold |
| `--class-conf` | none | Per-class confidence overrides, e.g. `rose=0.47,sphere=0.70` |
| `--iou` | `0.5` | IoU threshold (segmentation NMS) |
| `--device` | `auto` | Compute device |
| `--fps` | `15.0` | Output FPS for image-directory inputs |
| `--no-save-frames` | off | Keep only the MP4 |
| `--hf-token` | `HF_TOKEN` | HuggingFace token |

Annotation styling: `--palette`, `--colors`, `--box-thickness`, `--text-scale`, `--mask-opacity`, `--no-mask-outline` (see `--help`).
