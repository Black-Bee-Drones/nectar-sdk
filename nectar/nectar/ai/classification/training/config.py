"""Framework-specific classification training configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from nectar.ai.classification.core.configs import ClsTrainingConfig


@dataclass
class UltralyticsClsTrainingConfig(ClsTrainingConfig):
    """
    Ultralytics-specific classification training configuration.

    Parameters
    ----------
    model : str
        YOLO classification model name (e.g., 'yolo26n-cls.pt').
    """

    model: str = "yolo26n-cls.pt"
    framework: str = field(default="ultralytics", init=False)

    def to_ultralytics_args(self) -> Dict[str, Any]:
        """Convert to Ultralytics classification training arguments."""
        output_dir = Path(self.output_dir).resolve()
        args = {
            "data": self.dataset_path,
            "epochs": self.epochs,
            "batch": self.batch_size,
            "imgsz": self.imgsz if self.imgsz is not None else 224,
            "save": True,
            "save_period": self.save_period,
            "project": str(output_dir.parent),
            "name": output_dir.name,
            "exist_ok": True,
            "lr0": self.learning_rate,
            "seed": self.seed,
            "deterministic": True,
            "val": True,
            "weight_decay": self.weight_decay,
            "warmup_epochs": self.warmup_epochs,
            "warmup_momentum": self.warmup_momentum,
            "lrf": self.lrf,
            "cos_lr": self.cos_lr,
            "dropout": self.dropout,
            "plots": self.tensorboard,
            "patience": self.early_stopping_patience or 0,
            "freeze": self.freeze,
            "pretrained": not self.from_scratch,
            "erasing": self.erasing,
            "fliplr": self.fliplr,
            "flipud": self.flipud,
            "hsv_h": self.hsv_h,
            "hsv_s": self.hsv_s,
            "hsv_v": self.hsv_v,
        }
        if self.optimizer_type is not None:
            args["optimizer"] = self.optimizer_type
        return args


@dataclass
class TransformersClsTrainingConfig(ClsTrainingConfig):
    """
    Transformers-specific classification training configuration.

    Parameters
    ----------
    model : str
        Model identifier (e.g., 'google/vit-base-patch16-224-in21k').
    """

    model: str = "google/vit-base-patch16-224-in21k"
    framework: str = field(default="transformers", init=False)

    dataloader_num_workers: int = 2
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "accuracy"
    greater_is_better: bool = True
    remove_unused_columns: bool = False
    dataloader_pin_memory: bool = True

    def to_training_args(self) -> Dict[str, Any]:
        """Convert to TrainingArguments parameters."""
        return {
            "output_dir": self.output_dir,
            "num_train_epochs": self.epochs,
            "per_device_train_batch_size": self.batch_size,
            "per_device_eval_batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "learning_rate": self.learning_rate,
            "logging_steps": 10,
            "eval_strategy": "epoch",
            "save_strategy": "epoch",
            "save_total_limit": 3,
            "load_best_model_at_end": self.load_best_model_at_end,
            "metric_for_best_model": self.metric_for_best_model,
            "greater_is_better": self.greater_is_better,
            "seed": self.seed,
            "report_to": ["tensorboard"] if self.tensorboard else None,
            "fp16": self.mixed_precision == "fp16",
            "bf16": self.mixed_precision == "bf16",
            "dataloader_pin_memory": self.dataloader_pin_memory,
            "remove_unused_columns": self.remove_unused_columns,
            "warmup_ratio": self.warmup_ratio,
            "warmup_steps": self.warmup_steps,
            "weight_decay": self.weight_decay,
            "lr_scheduler_type": self.lr_scheduler_type,
            "max_grad_norm": self.max_grad_norm,
            "dataloader_num_workers": self.dataloader_num_workers,
            "push_to_hub": self.push_to_hub,
            "hub_model_id": self.hub_model_id,
        }
