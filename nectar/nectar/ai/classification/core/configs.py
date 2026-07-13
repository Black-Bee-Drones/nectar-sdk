"""Configuration classes for classification training and evaluation."""

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

import yaml

from nectar.ai.paths import DEFAULT_OUTPUT_DIR


@dataclass
class ClsTrainingConfig:
    """
    Configuration for classification model training.

    Parameters
    ----------
    dataset_path : str
        Path to ImageFolder root or HF dataset.
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
    imgsz: Optional[Union[int, List[int]]] = 224

    early_stopping_patience: Optional[int] = None
    early_stopping_delta: float = 0.0
    early_stopping_metric: str = "eval_accuracy"
    early_stopping_mode: str = "max"

    weight_decay: float = 1e-4
    lr_scheduler_type: str = "linear"
    warmup_steps: int = 0
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
    erasing: float = 0.4
    fliplr: float = 0.5
    flipud: float = 0.0
    hsv_h: float = 0.015
    hsv_s: float = 0.7
    hsv_v: float = 0.4

    # Transformers-specific
    gc_per_accumulation: bool = True
    evaluate: bool = False
    resume: bool = False
    num_workers: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_yaml(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClsTrainingConfig":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "ClsTrainingConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if any(k in data for k in ["train", "eval", "predict", "data"]):
            train_cfg = data.get("train", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **train_cfg}
            return cls.from_dict(merged)
        return cls.from_dict(data)


@dataclass
class ClsEvaluationConfig:
    """
    Configuration for classification model evaluation.

    Parameters
    ----------
    model_path : str
        Path to model checkpoint.
    dataset_path : str
        Path to evaluation dataset (ImageFolder root).
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
    device: str = "auto"
    batch_size: int = 16
    num_samples: Optional[int] = None
    imgsz: Optional[int] = 224
    topk: int = 5
    conf_threshold: float = 0.0
    prediction_samples_max: int = 16

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClsEvaluationConfig":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "ClsEvaluationConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if "eval" in data:
            eval_cfg = data.get("eval", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **eval_cfg}
            return cls.from_dict(merged)
        return cls.from_dict(data)


@dataclass
class ClsEvaluationMetrics:
    """Classification evaluation metrics."""

    top1_accuracy: float = 0.0
    top5_accuracy: float = 0.0
    precision_macro: float = 0.0
    recall_macro: float = 0.0
    f1_macro: float = 0.0
    precision_weighted: float = 0.0
    recall_weighted: float = 0.0
    f1_weighted: float = 0.0
    inference_time_per_image: float = 0.0
    total_samples: int = 0
    per_class_metrics: List[Dict] = field(default_factory=list)
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
            f"Top-1: {self.top1_accuracy:.4f}",
            f"Top-5: {self.top5_accuracy:.4f}",
            f"P(macro): {self.precision_macro:.4f}",
            f"R(macro): {self.recall_macro:.4f}",
            f"F1(macro): {self.f1_macro:.4f}",
        ]
        return " | ".join(parts)
