# Detection Module

Object detection API supporting Ultralytics YOLO, HuggingFace Transformers, and RF-DETR frameworks.

## Architecture

```mermaid
flowchart TB
    subgraph API["User API"]
        Detector["Detector"]
    end

    subgraph Core["Core"]
        BDM["BaseDetectionModel"]
        Types["Detection / DetectionResult"]
        Configs["TrainingConfig / EvaluationConfig"]
    end

    subgraph Models["Models"]
        UM["UltralyticsModel"]
        TM["TransformersModel"]
        RM["RFDETRModel"]
    end

    subgraph External["External"]
        YOLO["ultralytics"]
        HF["transformers"]
        RF["rfdetr"]
    end

    Detector -->|creates| UM
    Detector -->|creates| TM
    Detector -->|creates| RM

    UM -->|extends| BDM
    TM -->|extends| BDM
    RM -->|extends| BDM

    BDM -->|uses| Types
    BDM -->|uses| Configs

    UM -->|wraps| YOLO
    TM -->|wraps| HF
    RM -->|wraps| RF
```

## Quick Start

```python
from mirela_sdk.ai.detection import Detector

detector = Detector("yolov8n.pt")
detector.load()

result = detector.detect(image)
for det in result:
    print(f"{det.class_name}: {det.confidence:.2f}")
```

## Detector

Factory-based detector with auto-detection or explicit framework selection.

```python
from mirela_sdk.ai.detection import Detector, Framework

# Auto-detect from model name
detector = Detector("yolov8n.pt")

# Explicit framework
detector = Detector("model.pt", framework="ultralytics")
detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)

# HuggingFace model (user/repo:filename)
detector = Detector("user/repo:model.pt")

detector.load()
result = detector.detect(image, conf=0.5)
results = detector.detect_batch([img1, img2, img3])
annotated = detector.draw_detections(image, result)

# Properties
detector.framework          # Framework.ULTRALYTICS
detector.is_loaded          # bool
detector.class_names        # Dict[int, str]
Detector.available_frameworks()  # ['ultralytics', 'transformers', 'rfdetr']
```

### Framework Enum

```python
Framework.ULTRALYTICS  # YOLOv8, YOLOv10, YOLO11
Framework.TRANSFORMERS  # DETR, Conditional DETR
Framework.RFDETR        # RF-DETR
```

## Class Diagram

```mermaid
classDiagram
    class Framework {
        <<enum>>
        ULTRALYTICS
        TRANSFORMERS
        RFDETR
    }

    class Detector {
        -_builders: Dict
        -_model: BaseDetectionModel
        -_framework: Framework
        +model_source: str
        +device: str
        +confidence_threshold: float
        +framework: Framework
        +is_loaded: bool
        +class_names: Dict
        +register(framework, builder)$
        +available_frameworks()$ List
        +load(model_path) bool
        +detect(image, conf, iou) DetectionResult
        +detect_batch(images) List
        +train(config) Dict
        +evaluate(config) Dict
        +draw_detections(image, result) ndarray
        +enable_slicing(config)
        +disable_slicing()
    }

    class BaseDetectionModel {
        <<abstract>>
        +model_name: str
        +framework: str
        +model: Any
        +class_names: Dict
        +is_loaded: bool
        +load_model(path)*
        +detect(image, conf, iou) DetectionResult
        +detect_batch(images) List
        +train(config)* Dict
        +save(path)* str
        +evaluate(config) Dict
        +draw_detections(image, result) ndarray
    }

    class UltralyticsModel {
        +from_scratch: bool
        +load_model(path)
        +train(config) Dict
        +save(path) str
    }

    class TransformersModel {
        +processor: AutoImageProcessor
        +from_scratch: bool
        +load_model(path, id2label, label2id)
        +train(config) Dict
        +save(path) str
    }

    class RFDETRModel {
        +rfdetr_wrapper: Any
        +resolution: int
        +from_scratch: bool
        +load_model(path)
        +train(config) Dict
    }

    class Detection {
        +bbox: ndarray
        +confidence: float
        +class_id: int
        +class_name: str
        +tracker_id: int
        +metadata: Dict
        +center: Tuple
        +width: float
        +height: float
        +area: float
    }

    class DetectionResult {
        +detections: List
        +inference_time: float
        +image_path: str
        +model_name: str
        +filter_by_confidence(threshold) DetectionResult
        +filter_by_class(class_ids) DetectionResult
    }

    class TrainingConfig {
        +dataset_path: str
        +epochs: int
        +batch_size: int
        +learning_rate: float
        +output_dir: str
        +device: str
        +tensorboard: bool
        +push_to_hub: bool
        +hub_model_id: str
        +multi_gpu: bool
        +mixed_precision: str
    }

    class EvaluationConfig {
        +model_path: str
        +dataset_path: str
        +framework: str
        +output_dir: str
        +split: str
        +conf_threshold: float
        +iou_threshold: float
    }

    Detector --> Framework
    Detector --> BaseDetectionModel
    Detector ..> UltralyticsModel : creates
    Detector ..> TransformersModel : creates
    Detector ..> RFDETRModel : creates

    BaseDetectionModel <|-- UltralyticsModel
    BaseDetectionModel <|-- TransformersModel
    BaseDetectionModel <|-- RFDETRModel

    BaseDetectionModel --> Detection
    BaseDetectionModel --> DetectionResult
    BaseDetectionModel --> TrainingConfig
```

## Direct Model Classes

For advanced control:

```python
from mirela_sdk.ai.detection import UltralyticsModel, TransformersModel, RFDETRModel

model = UltralyticsModel("yolov8n.pt")
model.load_model()

model = TransformersModel("facebook/detr-resnet-50")
model.load_model()

model = RFDETRModel("rfdetr-base", resolution=560)
model.load_model()
```

## Core Types

### Detection

```python
from mirela_sdk.ai.detection import Detection

det = Detection(
    bbox=np.array([100, 100, 200, 200]),  # xyxy
    confidence=0.95,
    class_id=0,
    class_name="person",
)

det.center    # (150, 150)
det.width     # 100
det.height    # 100
det.area      # 10000
```

### DetectionResult

```python
result = detector.detect(image)

len(result)              # Number of detections
result.detections        # List[Detection]
result.inference_time    # Seconds

for det in result:
    print(det.class_name, det.confidence)

filtered = result.filter_by_confidence(0.5)
filtered = result.filter_by_class([0, 1, 2])
```

## Training

```python
from mirela_sdk.ai.detection import Detector, TrainingConfig

detector = Detector("yolov8n.pt")
detector.load()

config = TrainingConfig(
    dataset_path="/path/to/dataset",
    epochs=100,
    batch_size=16,
    learning_rate=0.001,
    output_dir="outputs/",
    tensorboard=True,
    push_to_hub=True,
    hub_model_id="user/model-name",
)

result = detector.train(config)
print(f"Model saved: {result['model_path']}")
```

### Training Flow

```mermaid
sequenceDiagram
    participant User
    participant Detector
    participant Model as BaseDetectionModel
    participant Framework as External Framework
    participant HF as HuggingFaceUploader

    User->>Detector: train(TrainingConfig)
    Detector->>Model: train(config)
    Model->>Framework: train(**args)

    loop Each epoch
        Framework-->>Model: Epoch complete
        opt Push to Hub
            Model->>HF: upload_file(checkpoint)
        end
    end

    Framework-->>Model: Training complete
    Model-->>Detector: {"model_path", "metrics"}
    Detector-->>User: Result dict
```

### Framework-Specific Configs

```mermaid
classDiagram
    class TrainingConfig {
        +dataset_path: str
        +epochs: int
        +batch_size: int
    }

    class UltralyticsTrainingConfig {
        +augment: bool
        +mosaic: float
        +mixup: float
        +to_ultralytics_args() Dict
    }

    class TransformersTrainingConfig {
        +dataloader_num_workers: int
        +load_best_model_at_end: bool
        +to_training_args() Dict
    }

    class RFDETRTrainingConfig {
        +resolution: int
        +use_ema: bool
        +to_rfdetr_args() Dict
    }

    TrainingConfig <|-- UltralyticsTrainingConfig
    TrainingConfig <|-- TransformersTrainingConfig
    TrainingConfig <|-- RFDETRTrainingConfig
```

## Evaluation

```python
from mirela_sdk.ai.detection import Detector, EvaluationConfig
from mirela_sdk.ai.detection.evaluation import ObjectDetectionEvaluator

detector = Detector("best.pt")
detector.load()

config = EvaluationConfig(
    model_path="best.pt",
    dataset_path="/path/to/dataset",
    framework="ultralytics",
    split="test",
    conf_threshold=0.25,
)

evaluator = ObjectDetectionEvaluator(detector.model, config)
metrics = evaluator.evaluate()

print(f"mAP@50: {metrics.map50:.4f}")
print(f"mAP@50-95: {metrics.map50_95:.4f}")
```

## Slicing Inference

For high-resolution images:

```python
detector = Detector("yolov8n.pt")
detector.load()

detector.enable_slicing({
    "strategy": "grid",
    "slice_size": (640, 640),
    "overlap_ratio": 0.2,
    "merge_strategy": "nms",  # nms, soft_nms, wbf, nmm
})

result = detector.detect(large_image)
detector.disable_slicing()
```

### Post-processing Strategies

```mermaid
classDiagram
    class BaseMergingStrategy {
        <<abstract>>
        +iou_threshold: float
        +name: str
        +merge_boxes(detections)* Tuple
    }

    class NMSStrategy {
        +class_agnostic: bool
    }

    class SoftNMSStrategy {
        +sigma: float
    }

    class WBFStrategy {
        +skip_box_thr: float
    }

    class NMMStrategy
    
    BaseMergingStrategy <|-- NMSStrategy
    BaseMergingStrategy <|-- SoftNMSStrategy
    BaseMergingStrategy <|-- WBFStrategy
    BaseMergingStrategy <|-- NMMStrategy
```

## Extension

### Adding a Framework

```python
from mirela_sdk.ai.detection import Detector
from mirela_sdk.ai.detection.core.base import BaseDetectionModel

class CustomModel(BaseDetectionModel):
    def load_model(self, path):
        pass

    def _predict_single(self, input):
        pass

    def train(self, config):
        pass

    def save(self, path):
        pass

Detector.register("custom", lambda name, **kw: CustomModel(name, **kw))
detector = Detector("model.pt", framework="custom")
```

## CLI

### Predict

```bash
python -m mirela_sdk.ai.detection.cli.predict \
    --model yolov8n.pt \
    --input image.jpg \
    --output results/
```

### Train

Using CLI arguments:

```bash
python -m mirela_sdk.ai.detection.cli.train \
    --model yolov8n.pt \
    --dataset /path/to/dataset \
    --epochs 100
```

Using config file:

```bash
python -m mirela_sdk.ai.detection.cli.train \
    --config configs/yolo_example.yaml
```

### Evaluate

```bash
python -m mirela_sdk.ai.detection.cli.evaluate \
    --model-path best.pt \
    --framework ultralytics \
    --dataset-path /path/to/dataset
```

## Config Files

YAML config files for training (see `configs/` for examples):

```yaml
# configs/detr_example.yaml
data:
  dataset_path: /path/to/coco/dataset
  dataset_format: coco

train:
  framework: transformers
  model: facebook/detr-resnet-50
  epochs: 50
  batch_size: 4
  learning_rate: 5e-5
  output_dir: outputs/detr
  device: cuda
  tensorboard: true
  push_to_hub: false
  multi_gpu: false
  mixed_precision: "no"

eval:
  evaluate: true
  eval_split: test
  conf_threshold: 0.25
  iou_threshold: 0.5
```

Shell scripts with config support:

```bash
# Transformers (DETR)
./scripts/train_transformers.sh --config configs/detr_example.yaml

# RF-DETR
./scripts/train_rfdetr.sh --config configs/rfdetr_example.yaml

# Ultralytics (YOLO)
./scripts/train_ultralytics.sh --config configs/yolo_example.yaml
```

## Module Structure

```
detection/
├── detector.py          # Detector with factory
├── cli/
│   ├── train.py         # Training CLI
│   ├── predict.py       # Inference CLI
│   └── evaluate.py      # Evaluation CLI
├── configs/             # Example config files
│   ├── detr_example.yaml
│   ├── rfdetr_example.yaml
│   └── yolo_example.yaml
├── scripts/             # Shell scripts
│   ├── train_transformers.sh
│   ├── train_rfdetr.sh
│   └── train_ultralytics.sh
├── core/
│   ├── base.py          # BaseDetectionModel
│   ├── types.py         # Detection, DetectionResult
│   ├── configs.py       # TrainingConfig, EvaluationConfig
│   └── protocols.py     # DetectorProtocol, TrainableProtocol
├── models/
│   ├── ultralytics.py   # UltralyticsModel
│   ├── transformers.py  # TransformersModel
│   ├── rfdetr.py        # RFDETRModel
│   └── model_loader.py  # HuggingFace loader
├── training/
│   └── config.py        # Framework-specific configs
├── evaluation/
│   └── evaluator.py     # ObjectDetectionEvaluator
├── slicing/
│   ├── config.py        # SlicingConfig
│   └── inference.py     # SlicingInference
├── postprocess/
│   ├── nms.py           # NMSStrategy
│   ├── soft_nms.py      # SoftNMSStrategy
│   ├── wbf.py           # WBFStrategy
│   └── nmm.py           # NMMStrategy
└── utils/
    ├── device.py        # get_device
    └── huggingface.py   # HuggingFaceUploader
```
