import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

import yaml

from nectar.ai.paths import DEFAULT_DATA_DIR, DEFAULT_OUTPUT_DIR  # noqa: F401


@dataclass
class TrainingConfig:
    """
    Configuration for model training.

    Comprehensive configuration supporting multiple frameworks with
    common and framework-specific parameters.

    Parameters
    ----------
    dataset_path : str
        Path to the training dataset.
    epochs : int
        Number of training epochs.
    batch_size : int, optional
        Batch size per device. Defaults to 16.
    learning_rate : float, optional
        Initial learning rate. Defaults to 0.001.
    output_dir : str, optional
        Directory for outputs. Defaults to "outputs".
    device : str, optional
        Device specification ('auto', 'cpu', 'cuda', 'cuda:0'). Defaults to "auto".
    seed : int, optional
        Random seed for reproducibility. Defaults to 42.

    Examples
    --------
    >>> config = TrainingConfig(
    ...     dataset_path="/path/to/dataset",
    ...     epochs=100,
    ...     batch_size=16,
    ...     tensorboard=True,
    ... )
    >>> config.to_yaml("config.yaml")
    """

    # Required
    dataset_path: str = ""
    epochs: int = 10

    # Common parameters
    batch_size: int = 16
    learning_rate: float = 0.001
    output_dir: str = field(default_factory=lambda: str(DEFAULT_OUTPUT_DIR))
    device: str = "auto"
    seed: int = 42

    # Logging and checkpointing
    tensorboard: bool = True
    save_period: int = 1
    push_to_hub: bool = False
    hub_model_id: Optional[str] = None

    # GPU settings
    multi_gpu: bool = False
    mixed_precision: str = "no"  # "no", "fp16", "bf16"
    gradient_accumulation_steps: int = 1

    # Dataset settings
    max_train_samples: Optional[int] = None
    max_eval_samples: Optional[int] = None
    max_test_samples: Optional[int] = None
    train_split: float = 0.8
    val_split: float = 0.2
    test_split: float = 0.0
    dataset_format: Optional[str] = None  # "coco", "yolo", "auto"

    # Model settings
    framework: str = ""  # "ultralytics", "transformers", "rfdetr"
    model: str = ""
    from_scratch: bool = False
    imgsz: Optional[Union[int, List[int]]] = None

    # Early stopping
    early_stopping_patience: Optional[int] = None
    early_stopping_delta: float = 0.0
    early_stopping_metric: str = "eval_loss"
    early_stopping_mode: str = "min"

    # Optimizer settings
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
    rfdetr_size: Optional[str] = None  # "nano", "small", "base", "medium", "large"
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
    set_cost_class: float = 2.0  # Matcher cost for class
    set_cost_bbox: float = 5.0  # Matcher cost for bbox
    set_cost_giou: float = 2.0  # Matcher cost for GIoU
    start_epoch: int = 0  # Starting epoch for resume
    gc_batch_frequency: int = 100
    early_stopping_use_ema: bool = False

    # Transformers-specific
    gc_per_accumulation: bool = True
    evaluate: bool = False
    resume: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns
        -------
        Dict[str, Any]
            Configuration as dictionary.
        """
        return asdict(self)

    def to_yaml(self, path: str) -> None:
        """
        Save configuration to YAML file.

        Parameters
        ----------
        path : str
            Path to save YAML file.
        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingConfig":
        """
        Create configuration from dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Configuration dictionary.

        Returns
        -------
        TrainingConfig
            New TrainingConfig instance.
        """
        # Filter to only valid fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "TrainingConfig":
        """
        Load configuration from YAML file.

        Parameters
        ----------
        path : str
            Path to YAML file.

        Returns
        -------
        TrainingConfig
            New TrainingConfig instance.
        """
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        # Handle nested config structure
        if any(k in data for k in ["train", "eval", "predict", "data"]):
            train_cfg = data.get("train", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **train_cfg}
            return cls.from_dict(merged)

        return cls.from_dict(data)


@dataclass
class EvaluationConfig:
    """
    Configuration for model evaluation.

    Parameters
    ----------
    model_path : str
        Path to model checkpoint.
    dataset_path : str
        Path to evaluation dataset.
    framework : str
        Model framework ('ultralytics', 'transformers', 'rfdetr').
    output_dir : str, optional
        Directory for outputs. Defaults to "outputs/evaluations".
    dataset_type : str, optional
        Dataset format ('coco', 'yolo', 'auto'). Defaults to "auto".
    split : str, optional
        Dataset split to evaluate ('train', 'valid', 'test'). Defaults to "test".
    conf_threshold : float, optional
        Confidence threshold. Defaults to 0.5.
    iou_threshold : float, optional
        IoU threshold for metrics. Defaults to 0.5.
    device : str, optional
        Device specification. Defaults to "auto".
    batch_size : int, optional
        Batch size for evaluation. Defaults to 16.
    num_samples : Optional[int], optional
        Limit number of samples. Defaults to None (all).
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
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationConfig":
        """Create from dictionary."""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    @classmethod
    def from_yaml(cls, path: str) -> "EvaluationConfig":
        """Load from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if "eval" in data:
            eval_cfg = data.get("eval", {})
            data_cfg = data.get("data", {})
            merged = {**data_cfg, **eval_cfg}
            return cls.from_dict(merged)

        return cls.from_dict(data)


@dataclass
class TrainingMetrics:
    """
    Training metrics for a single epoch.

    Parameters
    ----------
    epoch : int
        Epoch number (1-indexed).
    train_loss : float
        Training loss.
    val_loss : Optional[float], optional
        Validation loss.
    map50 : Optional[float], optional
        mAP at IoU=0.5.
    map50_95 : Optional[float], optional
        mAP at IoU=0.5:0.95.
    precision : Optional[float], optional
        Precision at IoU=0.5.
    recall : Optional[float], optional
        Recall at IoU=0.5.
    f1_score : Optional[float], optional
        F1 score at IoU=0.5.
    learning_rate : Optional[float], optional
        Current learning rate.
    """

    epoch: int
    train_loss: float
    val_loss: Optional[float] = None
    map50: Optional[float] = None
    map50_95: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    learning_rate: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EvaluationMetrics:
    """
    Evaluation metrics.

    Parameters
    ----------
    map50 : float
        Mean Average Precision at IoU=0.5.
    map50_95 : float
        Mean Average Precision at IoU=0.5:0.95.
    mar50 : float
        Mean Average Recall at IoU=0.5.
    mar50_95 : float
        Mean Average Recall at IoU=0.5:0.95.
    precision : float
        Precision at IoU=0.5.
    recall : float
        Recall at IoU=0.5.
    f1_score : float
        F1 Score at IoU=0.5.
    inference_time_per_image : float
        Average inference time per image in seconds.
    total_detections : int
        Total number of detections.
    per_class_metrics : List[Dict], optional
        Per-class metrics breakdown.
    visualizations : Dict[str, str], optional
        Paths to generated visualizations.
    """

    map50: float = 0.0
    map50_95: float = 0.0
    mar50: float = 0.0
    mar50_95: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    inference_time_per_image: float = 0.0
    total_detections: int = 0
    per_class_metrics: List[Dict] = field(default_factory=list)
    visualizations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def save_json(self, path: str) -> None:
        """
        Save metrics to JSON file.

        Parameters
        ----------
        path : str
            Path to save JSON file.
        """
        import json

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def summary(self) -> str:
        """
        Get formatted summary string.

        Returns
        -------
        str
            Metrics summary.
        """
        return (
            f"mAP@50: {self.map50:.4f} | "
            f"mAP@50-95: {self.map50_95:.4f} | "
            f"Precision: {self.precision:.4f} | "
            f"Recall: {self.recall:.4f} | "
            f"F1: {self.f1_score:.4f}"
        )


@dataclass
class TrainingResult:
    """
    Result of a training run.

    Parameters
    ----------
    model_path : str
        Path to best model checkpoint.
    metrics : Dict[str, float]
        Final training metrics.
    training_time : float
        Total training time in seconds.
    best_epoch : int
        Epoch with best performance.
    final_metrics : Optional[TrainingMetrics], optional
        Metrics from final epoch.
    history : List[TrainingMetrics], optional
        Metrics history for all epochs.
    config : Optional[TrainingConfig], optional
        Training configuration used.
    """

    model_path: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    training_time: float = 0.0
    best_epoch: int = 0
    final_metrics: Optional[TrainingMetrics] = None
    history: List[TrainingMetrics] = field(default_factory=list)
    config: Optional[TrainingConfig] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "model_path": self.model_path,
            "metrics": self.metrics,
            "training_time": self.training_time,
            "best_epoch": self.best_epoch,
        }
        if self.final_metrics:
            result["final_metrics"] = self.final_metrics.to_dict()
        if self.history:
            result["history"] = [m.to_dict() for m in self.history]
        return result

    def save_json(self, path: str) -> None:
        """Save result to JSON file."""
        import json

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
