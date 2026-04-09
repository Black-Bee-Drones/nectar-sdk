"""Configuration classes for segmentation training and evaluation."""

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from nectar.ai.detection.core.configs import TrainingMetrics, TrainingResult


def _get_source_segmentation_module_dir() -> Path:
    """Get the segmentation module directory from source location if available."""
    installed_dir = Path(__file__).parent.parent

    def _find_git_root(start: Path) -> Optional[Path]:
        current = start.resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        return None

    git_root = _find_git_root(Path(__file__))
    if git_root is None:
        return installed_dir

    source_candidates = [
        git_root / "nectar" / "nectar" / "ai" / "segmentation",
        git_root / "nectar" / "ai" / "segmentation",
    ]
    for candidate in source_candidates:
        if candidate.exists() and (candidate / "__init__.py").exists():
            return candidate

    return installed_dir


SEGMENTATION_MODULE_DIR = _get_source_segmentation_module_dir()
DEFAULT_DATA_DIR = SEGMENTATION_MODULE_DIR / "data"
DEFAULT_OUTPUT_DIR = SEGMENTATION_MODULE_DIR / "outputs"


@dataclass
class SegTrainingConfig:
    """
    Configuration for segmentation model training.

    Parameters
    ----------
    dataset_path : str
        Path to the training dataset.
    epochs : int
        Number of training epochs.
    batch_size : int
        Batch size per device.
    learning_rate : float
        Initial learning rate.
    output_dir : str
        Directory for outputs.
    device : str
        Device specification.
    seed : int
        Random seed.
    """

    dataset_path: str = ""
    epochs: int = 10
    batch_size: int = 16
    learning_rate: float = 0.001
    output_dir: str = field(default_factory=lambda: str(DEFAULT_OUTPUT_DIR))
    device: str = "auto"
    seed: int = 42

    tensorboard: bool = True
    save_period: int = 1
    push_to_hub: bool = False
    hub_model_id: Optional[str] = None

    multi_gpu: bool = False
    mixed_precision: str = "no"
    gradient_accumulation_steps: int = 1

    max_train_samples: Optional[int] = None
    max_eval_samples: Optional[int] = None
    max_test_samples: Optional[int] = None
    train_split: float = 0.8
    val_split: float = 0.2
    test_split: float = 0.0
    dataset_format: Optional[str] = None

    framework: str = ""
    model: str = ""
    from_scratch: bool = False
    imgsz: Optional[Union[int, List[int]]] = None

    early_stopping_patience: Optional[int] = None
    early_stopping_delta: float = 0.0
    early_stopping_metric: str = "eval_loss"
    early_stopping_mode: str = "min"

    weight_decay: float = 1e-4
    lr_scheduler_type: str = "linear"
    warmup_steps: int = 10
    warmup_ratio: float = 0.1
    max_grad_norm: float = 1.0
    optimizer_type: Optional[str] = None

    # Ultralytics-specific
    dropout: float = 0.0
    warmup_epochs: float = 3.0
    warmup_momentum: float = 0.8
    lrf: float = 0.01
    freeze: Optional[Union[int, List[int]]] = None
    cos_lr: bool = False

    # RF-DETR specific
    rfdetr_size: Optional[str] = None
    lr_encoder: Optional[float] = None
    use_ema: bool = True
    gradient_checkpointing: bool = False
    drop_path: float = 0.0
    drop_mode: str = "standard"
    drop_schedule: str = "constant"
    cutoff_epoch: int = 0
    freeze_encoder: bool = False
    layer_norm: bool = False
    rms_norm: bool = False
    backbone_lora: bool = False
    multi_scale: bool = False
    force_no_pretrain: bool = False
    ema_decay: float = 0.9997
    ema_tau: float = 0.0
    lr_vit_layer_decay: float = 0.8
    lr_component_decay: float = 1.0
    sync_bn: bool = True
    num_workers: int = 2
    set_cost_class: float = 2.0
    set_cost_bbox: float = 5.0
    set_cost_giou: float = 2.0
    start_epoch: int = 0
    gc_batch_frequency: int = 100
    early_stopping_use_ema: bool = False

    # Transformers-specific
    gc_per_accumulation: bool = True
    evaluate: bool = False
    resume: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_yaml(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SegTrainingConfig":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "SegTrainingConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        if any(k in data for k in ["train", "eval", "predict", "data"]):
            train_cfg = data.get("train", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **train_cfg}
            return cls.from_dict(merged)
        return cls.from_dict(data)


@dataclass
class SegEvaluationConfig:
    """
    Configuration for segmentation model evaluation.

    Parameters
    ----------
    model_path : str
        Path to model checkpoint.
    dataset_path : str
        Path to evaluation dataset.
    framework : str
        Model framework.
    output_dir : str
        Directory for outputs.
    """

    model_path: str = ""
    dataset_path: str = ""
    framework: str = ""
    output_dir: str = "outputs/evaluations"
    dataset_type: str = "auto"
    split: str = "test"
    conf_threshold: float = 0.5
    iou_threshold: float = 0.5
    device: str = "auto"
    batch_size: int = 16
    num_samples: Optional[int] = None
    imgsz: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SegEvaluationConfig":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "SegEvaluationConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if "eval" in data:
            eval_cfg = data.get("eval", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **eval_cfg}
            return cls.from_dict(merged)
        return cls.from_dict(data)


@dataclass
class SegEvaluationMetrics:
    """
    Segmentation evaluation metrics.

    Supports both instance segmentation (mask mAP) and semantic segmentation (mIoU).
    """

    map50: float = 0.0
    map50_95: float = 0.0
    mar50: float = 0.0
    mar50_95: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    mean_iou: float = 0.0
    pixel_accuracy: float = 0.0
    inference_time_per_image: float = 0.0
    total_segmentations: int = 0
    per_class_metrics: List[Dict] = field(default_factory=list)
    per_class_iou: Dict[str, float] = field(default_factory=dict)
    visualizations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save_json(self, path: str) -> None:
        import json

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def summary(self) -> str:
        parts = [
            f"mAP@50: {self.map50:.4f}",
            f"mAP@50-95: {self.map50_95:.4f}",
            f"mIoU: {self.mean_iou:.4f}",
            f"Precision: {self.precision:.4f}",
            f"Recall: {self.recall:.4f}",
            f"F1: {self.f1_score:.4f}",
        ]
        return " | ".join(parts)
