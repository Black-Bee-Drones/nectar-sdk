"""Framework-specific segmentation training configuration classes."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from nectar.ai.segmentation.core.configs import SegTrainingConfig


@dataclass
class UltralyticsSegTrainingConfig(SegTrainingConfig):
    """
    Ultralytics-specific segmentation training configuration.

    Parameters
    ----------
    model : str
        YOLO segmentation model name (e.g., 'yolov8n-seg.pt').
    """

    model: str = "yolov8n-seg.pt"
    framework: str = field(default="ultralytics", init=False)

    augment: bool = True
    mosaic: float = 1.0
    mixup: float = 0.0
    hsv_h: float = 0.015
    hsv_s: float = 0.7
    hsv_v: float = 0.4
    degrees: float = 0.0
    translate: float = 0.1
    scale: float = 0.5
    shear: float = 0.0
    flipud: float = 0.0
    fliplr: float = 0.5
    close_mosaic: int = 10
    overlap_mask: bool = True
    mask_ratio: int = 4

    def to_ultralytics_args(self) -> Dict[str, Any]:
        """Convert to Ultralytics training arguments."""
        output_dir = Path(self.output_dir).resolve()
        args = {
            "data": self.dataset_path,
            "epochs": self.epochs,
            "batch": self.batch_size,
            "imgsz": self.imgsz if self.imgsz is not None else 640,
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
            "augment": self.augment,
            "mosaic": self.mosaic,
            "mixup": self.mixup,
            "hsv_h": self.hsv_h,
            "hsv_s": self.hsv_s,
            "hsv_v": self.hsv_v,
            "degrees": self.degrees,
            "translate": self.translate,
            "scale": self.scale,
            "shear": self.shear,
            "flipud": self.flipud,
            "fliplr": self.fliplr,
            "close_mosaic": self.close_mosaic,
            "overlap_mask": self.overlap_mask,
            "mask_ratio": self.mask_ratio,
        }
        if self.optimizer_type is not None:
            args["optimizer"] = self.optimizer_type
        return args


@dataclass
class TransformersSegTrainingConfig(SegTrainingConfig):
    """
    Transformers-specific segmentation training configuration.

    Parameters
    ----------
    model : str
        Model identifier (e.g., 'facebook/mask2former-swin-large-cityscapes-instance').
    """

    model: str = "facebook/mask2former-swin-large-cityscapes-instance"
    framework: str = field(default="transformers", init=False)

    dataloader_num_workers: int = 2
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    remove_unused_columns: bool = False
    eval_do_concat_batches: bool = False
    dataloader_pin_memory: bool = False

    def to_training_args(self) -> Dict[str, Any]:
        """Convert to TrainingArguments parameters."""
        return {
            "output_dir": self.output_dir,
            "num_train_epochs": self.epochs,
            "per_device_train_batch_size": self.batch_size,
            "per_device_eval_batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "learning_rate": self.learning_rate,
            "logging_steps": 5,
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
            "eval_do_concat_batches": self.eval_do_concat_batches,
            "warmup_ratio": self.warmup_ratio,
            "weight_decay": self.weight_decay,
            "lr_scheduler_type": self.lr_scheduler_type,
            "max_grad_norm": self.max_grad_norm,
            "dataloader_num_workers": self.dataloader_num_workers,
        }


@dataclass
class RFDETRSegTrainingConfig(SegTrainingConfig):
    """
    RF-DETR specific segmentation training configuration.

    Parameters
    ----------
    model : str
        Model path or size (e.g., 'rfdetr-seg-medium').
    """

    model: str = "rfdetr-seg-medium"
    framework: str = field(default="rfdetr", init=False)
    resolution: int = 560

    _VALID_LR_SCHEDULERS = ("step", "cosine")

    def to_rfdetr_args(self) -> Dict[str, Any]:
        """Convert to RF-DETR TrainConfig-compatible training arguments.

        Fields handled specially by RFDETR.train() (popped before TrainConfig):
        ``device`` and ``resolution``.
        """
        lr_scheduler = self.lr_scheduler_type
        if lr_scheduler not in self._VALID_LR_SCHEDULERS:
            lr_scheduler = "step"

        args: Dict[str, Any] = {
            "dataset_dir": self.dataset_path,
            "output_dir": self.output_dir,
            "epochs": self.epochs,
            "warmup_epochs": int(self.warmup_epochs) if self.warmup_epochs else 1,
            "batch_size": self.batch_size,
            "grad_accum_steps": self.gradient_accumulation_steps,
            "lr": self.learning_rate,
            "lr_scheduler": lr_scheduler,
            "resolution": self.resolution if self.imgsz is None else self.imgsz,
            "weight_decay": self.weight_decay,
            "use_ema": self.use_ema,
            "checkpoint_interval": self.save_period,
            "tensorboard": self.tensorboard,
            "early_stopping": self.early_stopping_patience is not None
            and self.early_stopping_patience > 0,
            "early_stopping_min_delta": self.early_stopping_delta,
            "drop_path": self.drop_path,
            "sync_bn": self.sync_bn,
            "num_workers": self.num_workers,
            "ema_decay": self.ema_decay,
            "ema_tau": self.ema_tau,
            "lr_vit_layer_decay": self.lr_vit_layer_decay,
        }
        if self.early_stopping_patience is not None:
            args["early_stopping_patience"] = self.early_stopping_patience
        if self.lr_encoder is not None:
            args["lr_encoder"] = self.lr_encoder
        return args

    def get_model_config_overrides(self) -> Dict[str, Any]:
        """Return ModelConfig fields that must be set before training."""
        overrides: Dict[str, Any] = {}
        if self.gradient_checkpointing:
            overrides["gradient_checkpointing"] = True
        return overrides
