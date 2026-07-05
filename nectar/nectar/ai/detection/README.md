# Detection Module

Object detection across Ultralytics YOLO, HuggingFace Transformers (DETR), and RF-DETR
behind one `Detector` — load a model, call `detect`, and get typed results. The same API
covers training, evaluation, and slicing inference, with dataset tooling and a `nectar-ai`
CLI.

## At a glance

```python
from nectar.ai.detection import Detector

detector = Detector("yolov8n.pt")     # framework auto-detected from the model name
detector.load()
result = detector.detect(image)
for det in result:
    print(f"{det.class_name}: {det.confidence:.2f}")
```

## Concepts

`Detector` is a thin factory over three framework backends (`UltralyticsModel`,
`TransformersModel`, `RFDETRModel`), all sharing `BaseDetectionModel` and the same typed
results, slicing, post-processing, and evaluation:

```mermaid
flowchart TB
    subgraph API["User API"]
        Detector["Detector"]
    end

    subgraph Core["Core"]
        BDM["BaseDetectionModel"]
        Types["Detection / DetectionResult<br/>DetectionInput / Prediction"]
        Configs["TrainingConfig / EvaluationConfig<br/>TrainingMetrics / EvaluationMetrics<br/>TrainingResult"]
        Exceptions["DetectionError<br/>ModelNotLoadedError<br/>TrainingError<br/>EvaluationError<br/>..."]
    end

    subgraph Models["Models"]
        UM["UltralyticsModel"]
        TM["TransformersModel"]
        RM["RFDETRModel"]
        ML["ModelLoader"]
    end

    subgraph Slicing["Slicing"]
        SI["SlicingInference"]
        SC["SlicingConfig"]
        SS["SlicingStrategy"]
    end

    subgraph PostProcess["Post-processing"]
        NMS["NMSStrategy"]
        SoftNMS["SoftNMSStrategy"]
        WBF["WBFStrategy"]
        NMM["NMMStrategy"]
        PCF["PerClassConfidenceFilter"]
    end

    subgraph Evaluation["Evaluation"]
        ODE["ObjectDetectionEvaluator"]
    end

    subgraph External["External"]
        YOLO["ultralytics"]
        HF["transformers"]
        RF["rfdetr"]
        SV["supervision"]
        HFH["huggingface_hub"]
        TB["tensorboard"]
    end

    Detector -->|creates| UM
    Detector -->|creates| TM
    Detector -->|creates| RM

    UM -->|extends| BDM
    TM -->|extends| BDM
    RM -->|extends| BDM

    BDM -->|uses| Types
    BDM -->|uses| Configs
    BDM -->|uses| Slicing
    BDM -->|raises| Exceptions

    SI -->|uses| SC
    SI -->|uses| SS
    SI -->|uses| PostProcess

    UM -->|wraps| YOLO
    TM -->|wraps| HF
    RM -->|wraps| RF

    ODE -->|uses| SV
    PostProcess -->|uses| SV
    ML -->|uses| HFH
    Detector -->|uses| TB
```

## Detector

Factory-based detector with auto-detection or explicit framework selection.

**Auto-detect from the model name**:

```python
from nectar.ai.detection import Detector, Framework

detector = Detector("yolov8n.pt")
```

**Explicit framework**:

```python
detector = Detector("model.pt", framework="ultralytics")
detector = Detector("facebook/detr-resnet-50", framework=Framework.TRANSFORMERS)
```

**HuggingFace model** (`user/repo:filename`):

```python
detector = Detector("user/repo:model.pt")
```

Load and run:

```python
detector.load()
result = detector.detect(image, conf=0.5)
results = detector.detect_batch([img1, img2, img3])
annotated = detector.draw_detections(image, result)
```

**Properties**:

```python
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
        -_builders Dict~str,BuilderFunc~
        -_model BaseDetectionModel
        -_framework Framework
        -_loaded bool
        -_hf_token Optional~str~
        -_kwargs Dict
        +model_source str
        +device str
        +confidence_threshold float
        +framework Framework
        +is_loaded bool
        +class_names Dict~int,str~
        +model BaseDetectionModel
        +register(framework, builder)$
        +available_frameworks()$ List~str~
        +_detect_framework(source)$ Framework
        +_create_model(framework, model_name)$ BaseDetectionModel
        +load(model_path) bool
        +detect(image, conf, iou) DetectionResult
        +detect_batch(images, conf, iou) List~DetectionResult~
        +train(config) Dict~str,Any~
        +evaluate(config) Dict~str,Any~
        +draw_detections(image, result, show_labels, show_confidence, show_class, annotator_type, thickness, text_scale) ndarray
        +enable_slicing(config)
        +disable_slicing()
    }

    class BaseDetectionModel {
        <<abstract>>
        +model_name str
        +framework str
        +model Any
        +class_names Dict~int,str~
        +slicing_config Optional~SlicingConfig~
        -_slicing_inference Optional~SlicingInference~
        -logger Logger
        +is_loaded bool
        +load_model(path)*
        +_predict_single(input)* Prediction
        +_predict_batch(input) Prediction
        +predict(input) Prediction
        +_predict_with_slicing(input) Prediction
        +detect(image, conf, iou) DetectionResult
        +detect_batch(images, conf, iou) List~DetectionResult~
        +train(config)* TrainingResult
        +save(path)* str
        +evaluate(config) EvaluationMetrics
        +draw_detections(image, result, show_labels, show_confidence, show_class, annotator_type, thickness, text_scale) ndarray
        +enable_slicing(config)
        +disable_slicing()
    }

    class UltralyticsModel {
        -model Optional~YOLO~
        -_callbacks List
        +from_scratch bool
        +load_model(path)
        +_download_from_huggingface(path) str
        +train(config) TrainingResult
        +save(path) str
    }

    class TransformersModel {
        -model Optional~AutoModelForObjectDetection~
        -processor Optional~AutoImageProcessor~
        +from_scratch bool
        +load_model(path, id2label, label2id, imgsz)
        +train(config) TrainingResult
        +save(path) str
    }

    class RFDETRModel {
        -model Optional
        -model_class Type
        -base_model_name str
        -model_path Optional~str~
        +rfdetr_size Optional~str~
        +resolution Optional~int~
        +from_scratch bool
        +load_model(path)
        +_infer_model_size(path) str
        +train(config) TrainingResult
    }

    class Detection {
        <<dataclass>>
        +xyxy ndarray
        +confidence float
        +class_id int
        +class_name str
        +center Tuple~float,float~
        +width int
        +height int
        +area int
        +bbox List~int~
        +to_dict() Dict
        +from_dict(data)$ Detection
    }

    class DetectionResult {
        <<dataclass>>
        +detections List~Detection~
        +image Optional~ndarray~
        +inference_time float
        +image_path Optional~str~
        +model_name Optional~str~
        +__len__() int
        +__getitem__(idx) Detection
        +__iter__() Iterator
        +__bool__() bool
        +filter_by_confidence(threshold) DetectionResult
        +filter_by_class(class_names) DetectionResult
        +filter_by_class_id(class_ids) DetectionResult
        +to_supervision() sv.Detections
        +from_supervision(detections, class_names)$ DetectionResult
        +to_dict() Dict
    }

    class TrainingConfig {
        <<dataclass>>
        +dataset_path str
        +epochs int
        +batch_size int
        +learning_rate float
        +output_dir str
        +device str
        +seed int
        +tensorboard bool
        +save_period int
        +push_to_hub bool
        +hub_model_id Optional~str~
        +multi_gpu bool
        +mixed_precision str
        +gradient_accumulation_steps int
        +max_train_samples Optional~int~
        +max_eval_samples Optional~int~
        +max_test_samples Optional~int~
        +train_split float
        +val_split float
        +test_split float
        +dataset_format Optional~str~
        +framework str
        +model str
        +from_scratch bool
        +imgsz Optional~Union~int,List~int~~
        +early_stopping_patience Optional~int~
        +early_stopping_delta float
        +early_stopping_metric str
        +early_stopping_mode str
        +weight_decay float
        +lr_scheduler_type str
        +warmup_steps int
        +warmup_ratio float
        +max_grad_norm float
        +optimizer_type str
        +dropout float
        +warmup_epochs float
        +warmup_momentum float
        +lrf float
        +freeze Optional~Union~int,List~int~~
        +cos_lr bool
        +rfdetr_size Optional~str~
        +lr_encoder Optional~float~
        +use_ema bool
        +gradient_checkpointing bool
        +drop_path float
        +ema_decay float
        +sync_bn bool
        +num_workers int
        +gc_per_accumulation bool
        +evaluate bool
        +resume bool
        +to_dict() Dict
        +to_yaml(path)
        +from_dict(data)$ TrainingConfig
        +from_yaml(path)$ TrainingConfig
    }

    class EvaluationConfig {
        <<dataclass>>
        +model_path str
        +dataset_path str
        +framework str
        +output_dir str
        +dataset_type str
        +split str
        +conf_threshold float
        +iou_threshold float
        +device str
        +batch_size int
        +num_samples Optional~int~
        +to_dict() Dict
        +from_dict(data)$ EvaluationConfig
        +from_yaml(path)$ EvaluationConfig
    }

    class TrainingMetrics {
        <<dataclass>>
        +epoch int
        +train_loss float
        +val_loss Optional~float~
        +map50 Optional~float~
        +map50_95 Optional~float~
        +precision Optional~float~
        +recall Optional~float~
        +f1_score Optional~float~
        +learning_rate Optional~float~
        +to_dict() Dict
    }

    class EvaluationMetrics {
        <<dataclass>>
        +map50 float
        +map50_95 float
        +mar50 float
        +mar50_95 float
        +precision float
        +recall float
        +f1_score float
        +inference_time_per_image float
        +total_detections int
        +per_class_metrics List~Dict~
        +visualizations Dict~str,str~
        +to_dict() Dict
        +save_json(path)
    }

    class TrainingResult {
        <<dataclass>>
        +model_path str
        +metrics TrainingMetrics
        +config TrainingConfig
    }

    class DetectionInput {
        <<dataclass>>
        +image Union~ImageType,BatchImageType~
        +conf_threshold float
        +iou_threshold float
        +device Optional~str~
        +is_batch bool
        +to_dict() Dict
    }

    class Prediction {
        <<dataclass>>
        +detections Optional~sv.Detections~
        +batch_detections Optional~List~sv.Detections~~
        +results Optional~List~DetectionResult~~
        +inference_time float
        +image_path Optional~Union~str,List~str~~
        +model_name Optional~str~
        +is_batch bool
        +num_detections int
        +to_dict() Dict
        +from_detections(detections, class_names)$ Prediction
        +from_batch_detections(batch_detections, class_names)$ Prediction
    }

    class SlicingConfig {
        <<dataclass>>
        +strategy SlicingStrategy
        +slice_size Tuple~int,int~
        +overlap_ratio float
        +iou_threshold float
        +conf_threshold float
        +min_slice_area_ratio float
        +max_slices int
        +adaptive_threshold float
        +clustering_eps float
        +clustering_min_samples int
        +merge_strategy str
        +include_full_image bool
        +from_dict(config_dict)$ SlicingConfig
        +to_dict() Dict
        +grid(slice_size, overlap_ratio)$ SlicingConfig
        +adaptive(slice_size, threshold)$ SlicingConfig
    }

    class SlicingStrategy {
        <<enumeration>>
        NONE
        GRID
        ADAPTIVE
        CLUSTERING
        SUPERVISION
    }

    class SlicingInference {
        -config SlicingConfig
        -slicer ImageSlicer
        -_merge_strategy BaseMergingStrategy
        +run_sliced_inference(image, inference_callback, initial_detections) sv.Detections
        -_create_merge_strategy(strategy_name) BaseMergingStrategy
    }

    class ObjectDetectionEvaluator {
        -model Any
        -config EvaluationConfig
        -output_dir Path
        -device str
        -logger Logger
        +evaluate() EvaluationMetrics
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
    BaseDetectionModel --> DetectionInput
    BaseDetectionModel --> Prediction
    BaseDetectionModel --> TrainingConfig
    BaseDetectionModel --> EvaluationConfig
    BaseDetectionModel --> SlicingConfig
    BaseDetectionModel ..> SlicingInference : uses

    DetectionResult o-- Detection
    DetectionResult --> DetectionInput
    Prediction o-- DetectionResult
    Prediction --> DetectionInput

    SlicingInference o-- SlicingConfig
    SlicingInference --> SlicingStrategy
    SlicingInference --> BaseMergingStrategy

    ObjectDetectionEvaluator --> EvaluationConfig
    ObjectDetectionEvaluator --> EvaluationMetrics
```

## Direct Model Classes

For advanced control:

```python
from nectar.ai.detection import UltralyticsModel, TransformersModel, RFDETRModel

model = UltralyticsModel("yolov8n.pt")
model.load_model()

model = TransformersModel("facebook/detr-resnet-50")
model.load_model()

model = RFDETRModel("rfdetr-medium")
model.load_model()
```

## Core Types

### Detection

```python
from nectar.ai.detection import Detection

det = Detection(
    xyxy=np.array([100, 100, 200, 200]),  # [x1, y1, x2, y2]
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
filtered = result.filter_by_class_id([0, 1, 2])          # by class id; filter_by_class([...]) takes class names
```

## Training

```python
from nectar.ai.detection import Detector, TrainingConfig

detector = Detector("yolov8n.pt")
detector.load()

config = TrainingConfig(
    dataset_path="/path/to/dataset",
    epochs=100,
    batch_size=16,
    learning_rate=0.001,
    output_dir="outputs/",
    tensorboard=True,  # enable TensorBoard logging
    push_to_hub=True,
    hub_model_id="user/model-name",
)

result = detector.train(config)
# Training outputs and evaluation results automatically uploaded to HF Hub
print(f"Model saved: {result['model_path']}")
```

### Training Flow

Training automatically handles:

- TensorBoard server lifecycle (start/stop)
- HuggingFace Hub uploads (checkpoints during training, final outputs, evaluation results)
- Dataset format conversion (YOLO ↔ COCO)
- Balanced subset creation

```mermaid
sequenceDiagram
    participant User
    participant Detector
    participant Model as BaseDetectionModel
    participant Framework as External Framework
    participant HF as HuggingFaceUploader
    participant TB as TensorBoardManager

    User->>TB: start_server() (nectar-ai train CLI, if tensorboard)
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
    Detector->>HF: upload(training outputs)
    opt Evaluate
        Detector->>Model: evaluate()
        Model-->>Detector: metrics
        Detector->>HF: upload(evaluation results)
    end
    Detector->>TB: stop_server()
    Detector-->>User: Result dict
```

### Framework-Specific Configs

```mermaid
classDiagram
    class TrainingConfig {
        <<dataclass>>
        +dataset_path str
        +epochs int
        +batch_size int
        +learning_rate float
        +output_dir str
        +device str
        +seed int
        +tensorboard bool
        +save_period int
        +push_to_hub bool
        +hub_model_id Optional~str~
        +multi_gpu bool
        +mixed_precision str
        +gradient_accumulation_steps int
        +max_train_samples Optional~int~
        +max_eval_samples Optional~int~
        +max_test_samples Optional~int~
        +train_split float
        +val_split float
        +test_split float
        +dataset_format Optional~str~
        +framework str
        +model str
        +from_scratch bool
        +imgsz Optional~Union~int,List~int~~
        +early_stopping_patience Optional~int~
        +early_stopping_delta float
        +early_stopping_metric str
        +early_stopping_mode str
        +weight_decay float
        +lr_scheduler_type str
        +warmup_steps int
        +warmup_ratio float
        +max_grad_norm float
        +optimizer_type str
        +dropout float
        +warmup_epochs float
        +warmup_momentum float
        +lrf float
        +freeze Optional~Union~int,List~int~~
        +cos_lr bool
        +rfdetr_size Optional~str~
        +lr_encoder Optional~float~
        +use_ema bool
        +gradient_checkpointing bool
        +drop_path float
        +ema_decay float
        +sync_bn bool
        +num_workers int
        +gc_per_accumulation bool
        +evaluate bool
        +resume bool
        +to_dict() Dict
        +to_yaml(path)
        +from_dict(data)$ TrainingConfig
        +from_yaml(path)$ TrainingConfig
    }

    class UltralyticsTrainingConfig {
        <<dataclass>>
        +model str
        +framework str
        +augment bool
        +mosaic float
        +mixup float
        +hsv_h float
        +hsv_s float
        +hsv_v float
        +degrees float
        +translate float
        +scale float
        +shear float
        +flipud float
        +fliplr float
        +close_mosaic int
        +nbs int
        +overlap_mask bool
        +mask_ratio int
        +to_ultralytics_args() Dict~str,Any~
    }

    class TransformersTrainingConfig {
        <<dataclass>>
        +model str
        +framework str
        +dataloader_num_workers int
        +load_best_model_at_end bool
        +metric_for_best_model str
        +greater_is_better bool
        +remove_unused_columns bool
        +eval_do_concat_batches bool
        +dataloader_pin_memory bool
        +hub_strategy str
        +hub_private_repo bool
        +to_training_args() Dict~str,Any~
    }

    class RFDETRTrainingConfig {
        <<dataclass>>
        +model str
        +framework str
        +rfdetr_size Optional~str~
        +resolution Optional~int~
        +use_ema bool
        +gradient_checkpointing bool
        +lr_encoder Optional~float~
        +ema_decay float
        +ema_tau float
        +lr_vit_layer_decay float
        +sync_bn bool
        +set_cost_class float
        +set_cost_bbox float
        +set_cost_giou float
        +to_rfdetr_args() Dict~str,Any~
    }

    TrainingConfig <|-- UltralyticsTrainingConfig
    TrainingConfig <|-- TransformersTrainingConfig
    TrainingConfig <|-- RFDETRTrainingConfig
```

## Evaluation

```python
from nectar.ai.detection import Detector, EvaluationConfig
from nectar.ai.detection.evaluation import ObjectDetectionEvaluator

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

# Optional: add a per-class confidence filter (set_post_processor takes filter_strategy only)
from nectar.ai.detection.postprocess import PerClassConfidenceFilter

evaluator.set_post_processor(
    filter_strategy=PerClassConfidenceFilter(csv_path="pr_analysis_results.csv"),
)

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
        +iou_threshold float
        +name str
        +merge_boxes(detections)* Tuple
        +_compute_iou_pair(box1, box2)$ float
        +_compute_iou_batch(box, boxes)$ ndarray
    }

    class NMSStrategy {
        +class_agnostic bool
        +merge_boxes(detections) Tuple
    }

    class SoftNMSStrategy {
        +sigma float
        +score_threshold float
        +merge_boxes(detections) Tuple
    }

    class WBFStrategy {
        +skip_box_threshold float
        +conf_type str
        +merge_boxes(detections) Tuple
    }

    class NMMStrategy {
        +merge_boxes(detections) Tuple
    }

    class PerClassConfidenceFilter {
        +threshold_mapping Dict
        +default_threshold float
        +filter(detections) sv.Detections
    }

    BaseMergingStrategy <|-- NMSStrategy
    BaseMergingStrategy <|-- SoftNMSStrategy
    BaseMergingStrategy <|-- WBFStrategy
    BaseMergingStrategy <|-- NMMStrategy
```

### Per-Class Confidence Filtering

Load optimal thresholds from PR analysis results:

**From a PR-analysis CSV**:

```python
from nectar.ai.detection.postprocess import PerClassConfidenceFilter

filter = PerClassConfidenceFilter(csv_path="evaluation/pr_analysis_results.csv")
```

**Manual mapping**:

```python
filter = PerClassConfidenceFilter(threshold_mapping={0: 0.3, 1: 0.5}, default_threshold=0.25)
```

```python
filtered = filter.filter(detections)
```

## Utilities

### TensorBoard Management

```python
from nectar.ai.detection.utils import TensorBoardManager

manager = TensorBoardManager()
manager.start_server(log_dir="outputs", port=6006)
# ... training ...
manager.stop_server()
```

### HuggingFace Hub Upload

```python
from nectar.ai.detection.utils import HuggingFaceUploader

uploader = HuggingFaceUploader(
    repo_id="user/model-name",
    local_dir="outputs/",
    repo_type="model",
)
uploader.upload(commit_message="Upload training results")
```

Training automatically uploads outputs and evaluation results to HuggingFace Hub when `push_to_hub=True` and `hub_model_id` is set.

## Extension

### Adding a Framework

```python
from nectar.ai.detection import Detector
from nectar.ai.detection.core.base import BaseDetectionModel

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

The detection module is driven through the unified `nectar-ai` CLI under the `detect` task (`detect`, `detection`, and `od` are aliases):

**Training**:

```bash
nectar-ai detect train --config configs/yolo_example.yaml
```

**Prediction**:

```bash
nectar-ai detect predict --model yolov8n.pt --input image.jpg --output results/
```

**Evaluation**:

```bash
nectar-ai detect eval --model-path best.pt --framework ultralytics --dataset-path /path/to/dataset
```

**Dataset management**:

```bash
nectar-ai detect dataset download --source visdrone --output datasets/visdrone
nectar-ai detect dataset convert --input datasets/coco --output datasets/yolo --format yolo
nectar-ai detect dataset stratify --input datasets/unsplit --output datasets/split --train-ratio 0.8
nectar-ai detect dataset subset --input datasets/full --output datasets/subset --max-train-samples 1000
nectar-ai detect dataset augment --input datasets/my_dataset --output datasets/my_dataset_augmented --preset aerial --num-augmented 2 --splits train --num-workers 8
nectar-ai detect dataset analyze --input datasets/my_dataset
nectar-ai detect dataset merge --dataset1 datasets/d1 --dataset2 datasets/d2 --output datasets/merged --train-config '{"d1": 1000, "d2": 5000}' --output-format coco
nectar-ai detect dataset upload --target huggingface --repo user/my-dataset --dataset datasets/my_dataset --title "My Dataset" --model-repo user/my-model
nectar-ai detect dataset upload --target huggingface --raw --repo user/my-dataset --dataset datasets/my_dataset
nectar-ai detect dataset upload --target roboflow --api-key KEY --project my-project --dataset datasets/my_dataset --splits train valid test
nectar-ai detect dataset upload --target roboflow --images-only --api-key KEY --project my-project --dataset images/
nectar-ai detect dataset upload-images --api-key KEY --project my-project --directory images/
nectar-ai detect dataset download --source huggingface --repo user/my-dataset --format yolo --output data/local
```

### Training

**Using a config file** (recommended):

```bash
nectar-ai detect train --config configs/yolo_example.yaml
```

**Using CLI arguments**:

```bash
nectar-ai detect train --model yolov8n.pt --dataset /path/to/dataset --epochs 100 --batch-size 16
```

### Evaluation

```bash
nectar-ai detect eval --model-path best.pt --framework ultralytics --dataset-path /path/to/dataset
```

**With per-class confidence thresholds** (name=value pairs; resolved against the model's class names):

```bash
nectar-ai detect eval --model-path best.pt --framework ultralytics --dataset-path /path/to/dataset \
    --conf-per-class 'crack=0.4,pothole=0.55'
```

## Dataset Management

Utilities for preparing detection datasets, each available as a Python class and as a
`nectar-ai detect dataset <command>` subcommand:

| Task | Python API | CLI |
|------|-----------|-----|
| Detect / convert format (COCO ↔ YOLO) | `FormatDetector`, `FormatConverter` | `convert` |
| Balanced subset | `SubsetCreator` | `subset` |
| Train/val/test split | `Stratifier` | `stratify` |
| Augmentation | `AugmentationBuilder` | `augment` |
| Analysis & stats | `DatasetAnalyzer` | `analyze` |
| Download by source (VisDrone, Roboflow) | `DatasetHandlerRegistry` | `download` |
| Merge datasets | `DatasetMerger` | `merge` |
| Upload (HuggingFace / Roboflow) | `HuggingFaceDatasetUploader`, `RoboflowUploader` | `upload` |

### Format Detection and Conversion

Datasets are automatically detected and converted between COCO and YOLO formats as needed:

```python
from nectar.ai.detection.datasets import FormatDetector, FormatConverter

# Auto-detect format
detector = FormatDetector("datasets/my_dataset")
format_type = detector.detect()  # "coco" or "yolo"

# Convert format
converter = FormatConverter("datasets/coco", "datasets/yolo")
yaml_path = converter.convert(target_format="yolo")
```

### Balanced Subset Creation

Create balanced subsets maintaining class distribution:

```python
from nectar.ai.detection.datasets import SubsetCreator

creator = SubsetCreator("datasets/full", "datasets/subset", seed=42)
subset_path = creator.create(
    max_train_samples=1000,
    max_eval_samples=200,
    max_test_samples=100,
)
```

### Dataset Stratification

Split unsplit datasets into train/val/test with balanced class distribution:

```python
from nectar.ai.detection.datasets import Stratifier

stratifier = Stratifier("datasets/unsplit", "datasets/split", seed=42)
split_path = stratifier.stratify(
    train_ratio=0.8,
    val_ratio=0.2,
    test_ratio=0.0,
)
```

### Augmentation

Build augmentation configs and apply to datasets with parallel processing:

**Use a preset**:

```python
from nectar.ai.detection.datasets import AugmentationBuilder

builder = AugmentationBuilder(preset="aerial")
builder.apply(
    input_path="datasets/my_dataset",
    output_path="datasets/my_dataset_augmented",
    num_augmented=2,
    splits=["train"],
    num_workers=8,
)
```

**Custom transforms**:

```python
builder = AugmentationBuilder(config={
    "HorizontalFlip": {"p": 0.5},
    "Rotate": {"limit": 15, "p": 0.3},
})
builder.apply("datasets/input", "datasets/output", num_augmented=3)
```

**Augmentation Behavior:**

- `num_augmented`: Number of augmented copies generated per original image.
  - Example: 1000 original images + `num_augmented=2` → 1000 original + 2000 augmented = 3000 total

- `max_original_samples`: Limits how many original images are selected for augmentation (not total generated).
  - Example: 1000 original images + `max_original_samples=500` + `num_augmented=2`:
    - All 1000 original images are kept in output
    - 500 original images are augmented (each produces 2 copies)
    - Total: 1000 original + 1000 augmented = 2000 images

- `augmentation_ratio`: Adds augmented data as fraction of train size.
  - Example: `augmentation_ratio=0.25` with 1000 images → adds ~250 augmented images (25% of original)
  - Automatically calculates `max_original_samples` based on ratio

- `prioritize_rare_classes`: When using `max_original_samples`, prioritizes images containing underrepresented categories to balance the dataset.

**CLI Usage:**

**Basic augmentation** (2 copies per image):

```bash
nectar-ai detect dataset augment \
  --input datasets/visdrone \
  --output datasets/visdrone-augmented \
  --preset aerial \
  --num-augmented 2 \
  --splits train \
  --num-workers 8
```

**Limit to 1000 original images**:

```bash
nectar-ai detect dataset augment \
  --input datasets/visdrone \
  --output datasets/visdrone-augmented \
  --preset aerial \
  --num-augmented 2 \
  --max-original-samples 1000
```

**Add 25% extra data via augmentation ratio**:

```bash
nectar-ai detect dataset augment \
  --input datasets/visdrone \
  --output datasets/visdrone-augmented \
  --preset aerial \
  --num-augmented 2 \
  --augmentation-ratio 0.25
```

**Prioritize rare classes when limiting samples**:

```bash
nectar-ai detect dataset augment \
  --input datasets/visdrone \
  --output datasets/visdrone-augmented \
  --preset aerial \
  --num-augmented 2 \
  --max-original-samples 1000 \
  --prioritize-rare-classes
```

### Dataset Analysis

Analyze dataset distribution and generate visualizations:

```python
from nectar.ai.detection.datasets import DatasetAnalyzer

analyzer = DatasetAnalyzer("datasets/my_dataset", output_dir="analysis/")
results = analyzer.analyze()
# Generates plots and statistics report
```

### Dataset Handlers

Download datasets from various sources using the handler registry:

```python
from nectar.ai.detection.datasets import DatasetHandlerRegistry

# VisDrone
handler_class = DatasetHandlerRegistry.get("visdrone")
handler = handler_class("datasets/visdrone")
handler.download_and_convert(output_format="coco")

# Roboflow
handler_class = DatasetHandlerRegistry.get("roboflow")
handler = handler_class("datasets/roboflow", api_key="YOUR_KEY")
handler.download(workspace="workspace", project="project", version=1, format_type="yolo")
```

### Dataset Merging

Merge two datasets (YOLO or COCO format) with balanced sampling:

```python
from nectar.ai.detection.datasets import DatasetMerger

# Auto-detect formats and merge (output format matches first dataset)
merger = DatasetMerger("datasets/dataset1", "datasets/dataset2", "datasets/merged", seed=42)
merger.merge({
    "train": {"d1": 1000, "d2": 5000},
    "valid": {"d1": "all", "d2": 500},
    "test": {"d1": 200, "d2": 200}
})

# Specify output format explicitly
merger = DatasetMerger(
    "datasets/dataset1",
    "datasets/dataset2",
    "datasets/merged",
    output_format="coco",  # or "yolo", "auto"
    seed=42
)
```

### Dataset Upload

Upload datasets to HuggingFace Hub or Roboflow with images **and** annotations.

#### HuggingFace: native Parquet (recommended)

`upload_native()` converts a local COCO/YOLO dataset to the Hub-native schema
(`image` column + `objects.{bbox, category, area}` with `ClassLabel`). The Hub
dataset viewer renders bounding box overlays automatically.

```python
from nectar.ai.detection.datasets import HuggingFaceDatasetUploader

uploader = HuggingFaceDatasetUploader(repo_id="user/my-dataset", private=False)

result = uploader.upload_native(
    dataset_path="datasets/my_dataset",   # COCO or YOLO, auto-detected
    commit_message="Upload v1.0",
    card_metadata={
        "title": "My Dataset",
        "description": "Aerial gate detection.",
        "license": "apache-2.0",
        "tags": ["drone", "uav"],
        "model_repo": "user/my-model",     # optional, links the trained model
    },
)
print(result["splits"], result["class_names"])

# Legacy raw-files upload (no viewer):
uploader.upload_dataset(dataset_path="datasets/my_dataset")
```

#### Roboflow: dataset (images + annotations)

`upload_dataset()` auto-detects COCO/YOLO format, pairs each image with its
annotation, preserves the train/valid/test split assignment, and uploads in
parallel.

```python
from nectar.ai.detection.datasets import RoboflowUploader

uploader = RoboflowUploader(api_key="YOUR_KEY")

stats = uploader.upload_dataset(
    dataset_path="datasets/my_dataset",
    project_name="my-project",
    annotation_format=None,   # auto-detect ("coco" or "yolo")
    splits=["train", "valid", "test"],
    batch_name="batch-1",
    tag_names=["robotics"],
    max_workers=10,
)
print(stats["per_split"], stats["failed_files"])

# Legacy: upload images only (no annotations) for an annotation workflow.
uploader.upload_directory(directory_path="images/", project_name="my-project")
```

#### CLI

**HuggingFace native upload** (Parquet + viewer):

```bash
nectar-ai detect dataset upload --target huggingface \
    --repo user/my-dataset --dataset datasets/my_dataset \
    --public --title "My Dataset" --model-repo user/my-model
```

**HuggingFace raw-files fallback**:

```bash
nectar-ai detect dataset upload --target huggingface --raw \
    --repo user/my-dataset --dataset datasets/my_dataset
```

**Roboflow dataset** (images + annotations, default):

```bash
nectar-ai detect dataset upload --target roboflow --api-key KEY \
    --project my-project --dataset datasets/my_dataset \
    --splits train valid test
```

**Roboflow images-only** (legacy):

```bash
nectar-ai detect dataset upload --target roboflow --images-only \
    --api-key KEY --project my-project --dataset images/
```

### Dataset Download

The `huggingface` (alias `hf`) handler downloads a HF dataset and materializes
it on disk in COCO or YOLO format ready for training.

```python
from nectar.ai.detection.datasets import HuggingFaceHandler

handler = HuggingFaceHandler("data/imav-gate", token=None)  # uses HF_TOKEN
handler.download(
    repo_id="blackbeedrones/imav-2025-gate-dataset",
    format_type="yolo",   # or "coco"
)
# data/imav-gate now has data.yaml + train/images + train/labels (YOLO)
# or train/_annotations.coco.json + image files (COCO)
```

CLI:

```bash
nectar-ai detect dataset download --source huggingface \
    --repo blackbeedrones/imav-2025-gate-dataset \
    --format yolo --output data/imav-gate

nectar-ai detect dataset download --source roboflow \
    --workspace WS --project P --version 1 --format coco \
    --api-key KEY --output data/roboflow
```

### HF format converters

Low-level converters used by both upload and download:

```python
from nectar.ai.detection.datasets import (
    coco_to_hf, yolo_to_hf, hf_to_coco, hf_to_yolo, generate_dataset_card,
)

ds = coco_to_hf("datasets/my_dataset")          # COCO -> DatasetDict
ds = yolo_to_hf("datasets/my_dataset")          # YOLO -> DatasetDict
hf_to_coco(ds, "out/coco")                      # DatasetDict -> COCO files
hf_to_yolo(ds, "out/yolo")                      # DatasetDict -> YOLO files + data.yaml
card = generate_dataset_card(ds, "user/repo", title="My Dataset")
```

## Config Files

YAML config files for training:

```yaml
data:
  dataset_path: /path/to/dataset
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
  push_to_hub: true
  hub_model_id: user/model-name
  mixed_precision: fp16
  max_train_samples: 1000
  max_eval_samples: 200

eval:
  evaluate: true
  eval_split: test
  conf_threshold: 0.25
  iou_threshold: 0.5
  batch_size: 2
  device: auto
  num_samples: 100
```

Usage:

```bash
nectar-ai detect train --config configs/detr_example.yaml
```

## Layout

The `detection/` package is organized into:

- `detector.py` — the `Detector` facade and factory
- `core/` — `BaseDetectionModel`, detection types, `TrainingConfig`/`EvaluationConfig`, exceptions
- `models/` — framework backends (`UltralyticsModel`, `TransformersModel`, `RFDETRModel`) and the HuggingFace loader
- `training/` — framework-specific training configs
- `evaluation/` — `ObjectDetectionEvaluator`, PR/error analysis, plots
- `slicing/` — `SlicingConfig` and `SlicingInference` for high-resolution tiling
- `postprocess/` — merge strategies (NMS, Soft-NMS, WBF, NMM) and per-class confidence filtering
- `datasets/` — format conversion, subset/stratify/augment/analyze/merge, and download handlers (VisDrone, Roboflow, HuggingFace)
- `cli/`, `configs/`, `scripts/` — the `nectar-ai` CLI, example configs, and training shell scripts
- `utils/` — device management, HuggingFace upload, TensorBoard
