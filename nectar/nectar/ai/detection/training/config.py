"""
Training configuration classes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from nectar.ai.detection.core.configs import TrainingConfig as BaseTrainingConfig

TrainingConfig = BaseTrainingConfig


@dataclass
class UltralyticsTrainingConfig(TrainingConfig):
    """
    Ultralytics-specific training configuration.

    Extends base config with YOLO-specific parameters.

    Parameters
    ----------
    model : str
        YOLO model name (e.g., 'yolov8n.pt', 'yolov11m.pt').
    dropout : float, optional
        Dropout rate. Defaults to 0.0.
    warmup_epochs : float, optional
        Number of warmup epochs. Defaults to 3.0.
    freeze : Optional[Union[int, List[int]]], optional
        Layers to freeze. Defaults to None.
    cos_lr : bool, optional
        Use cosine learning rate scheduler. Defaults to False.
    augment : bool, optional
        Enable data augmentation. Defaults to True.
    mosaic : float, optional
        Mosaic augmentation probability. Defaults to 1.0.
    mixup : float, optional
        MixUp augmentation probability. Defaults to 0.0.
    hsv_h : float, optional
        HSV-Hue augmentation range. Defaults to 0.015.
    hsv_s : float, optional
        HSV-Saturation augmentation range. Defaults to 0.7.
    hsv_v : float, optional
        HSV-Value augmentation range. Defaults to 0.4.
    degrees : float, optional
        Rotation augmentation degrees. Defaults to 0.0.
    translate : float, optional
        Translation augmentation range. Defaults to 0.1.
    scale : float, optional
        Scale augmentation range. Defaults to 0.5.
    shear : float, optional
        Shear augmentation degrees. Defaults to 0.0.
    flipud : float, optional
        Vertical flip probability. Defaults to 0.0.
    fliplr : float, optional
        Horizontal flip probability. Defaults to 0.5.
    """

    # Required
    model: str = "yolov8n.pt"
    framework: str = field(default="ultralytics", init=False)

    # YOLO-specific augmentation
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

    # YOLO-specific training
    close_mosaic: int = 10
    nbs: int = 64
    overlap_mask: bool = True
    mask_ratio: int = 4

    def to_ultralytics_args(self) -> Dict[str, Any]:
        """
        Convert to Ultralytics training arguments.

        Returns
        -------
        Dict[str, Any]
            Arguments for YOLO.train().
        """
        return {
            "data": self.dataset_path,
            "epochs": self.epochs,
            "batch": self.batch_size,
            "imgsz": self.imgsz or 640,
            "save": True,
            "save_period": self.save_period,
            "project": self.output_dir,
            "exist_ok": True,
            "optimizer": self.optimizer_type,
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
        }


@dataclass
class TransformersTrainingConfig(TrainingConfig):
    """
    Transformers-specific training configuration.

    Extends base config with Hugging Face Transformers parameters.

    Parameters
    ----------
    model : str
        Model identifier (e.g., 'facebook/detr-resnet-50').
    warmup_ratio : float, optional
        Warmup ratio. Defaults to 0.1.
    weight_decay : float, optional
        Weight decay. Defaults to 0.0001.
    lr_scheduler_type : str, optional
        LR scheduler type. Defaults to 'linear'.
    max_grad_norm : float, optional
        Maximum gradient norm. Defaults to 1.0.
    fp16 : bool, optional
        Use FP16 training. Defaults to False.
    bf16 : bool, optional
        Use BF16 training. Defaults to False.
    dataloader_num_workers : int, optional
        Number of dataloader workers. Defaults to 2.
    load_best_model_at_end : bool, optional
        Load best model at end. Defaults to True.
    metric_for_best_model : str, optional
        Metric to monitor. Defaults to 'eval_loss'.
    greater_is_better : bool, optional
        Whether higher metric is better. Defaults to False.
    """

    # Required
    model: str = "facebook/detr-resnet-50"
    framework: str = field(default="transformers", init=False)

    # Transformers-specific
    dataloader_num_workers: int = 2
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    remove_unused_columns: bool = False
    eval_do_concat_batches: bool = False
    dataloader_pin_memory: bool = False
    hub_strategy: str = "all_checkpoints"
    hub_private_repo: bool = True

    def to_training_args(self) -> Dict[str, Any]:
        """
        Convert to TrainingArguments parameters.

        Returns
        -------
        Dict[str, Any]
            Arguments for TrainingArguments.
        """
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
            "push_to_hub": self.push_to_hub,
            "hub_model_id": self.hub_model_id,
            "hub_strategy": self.hub_strategy,
            "hub_private_repo": self.hub_private_repo,
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
class RFDETRTrainingConfig(TrainingConfig):
    """
    RF-DETR specific training configuration.

    Extends base config with RF-DETR parameters.

    Parameters
    ----------
    model : str
        Model path or size (e.g., 'rfdetr-base').
    rfdetr_size : str, optional
        Model size ('nano', 'small', 'base', 'medium', 'large').
    resolution : int, optional
        Input resolution. Defaults to 560.
    use_ema : bool, optional
        Use EMA. Defaults to True.
    gradient_checkpointing : bool, optional
        Use gradient checkpointing. Defaults to False.
    lr_encoder : Optional[float], optional
        Encoder learning rate. Defaults to None.
    ema_decay : float, optional
        EMA decay rate. Defaults to 0.9997.
    ema_tau : float, optional
        EMA tau. Defaults to 0.0.
    lr_vit_layer_decay : float, optional
        ViT layer decay. Defaults to 0.8.
    sync_bn : bool, optional
        Use sync batch norm. Defaults to True.
    set_cost_class : float, optional
        Matcher class cost. Defaults to 2.0.
    set_cost_bbox : float, optional
        Matcher bbox cost. Defaults to 5.0.
    set_cost_giou : float, optional
        Matcher GIoU cost. Defaults to 2.0.
    """

    # Required
    model: str = "rfdetr-base"
    framework: str = field(default="rfdetr", init=False)

    # RF-DETR specific
    resolution: int = 560

    def to_rfdetr_args(self) -> Dict[str, Any]:
        """
        Convert to RF-DETR training arguments.

        Returns
        -------
        Dict[str, Any]
            Arguments for rfdetr.train().
        """
        return {
            "dataset_dir": self.dataset_path,
            "output_dir": self.output_dir,
            "epochs": self.epochs,
            "warmup_epochs": int(self.warmup_epochs) if self.warmup_epochs else 1,
            "batch_size": self.batch_size,
            "grad_accum_steps": self.gradient_accumulation_steps,
            "lr": self.learning_rate,
            "lr_scheduler": self.lr_scheduler_type,
            "lr_encoder": self.lr_encoder,
            "resolution": self.resolution if self.imgsz is None else self.imgsz,
            "weight_decay": self.weight_decay,
            "use_ema": self.use_ema,
            "gradient_checkpointing": self.gradient_checkpointing,
            "checkpoint_interval": self.save_period,
            "tensorboard": self.tensorboard,
            "early_stopping": self.early_stopping_patience is not None,
            "early_stopping_patience": self.early_stopping_patience,
            "early_stopping_min_delta": self.early_stopping_delta,
            "clip_max_norm": self.max_grad_norm,
            "dropout": self.dropout,
            "drop_path": self.drop_path,
            "sync_bn": self.sync_bn,
            "num_workers": self.num_workers,
            "amp": self.mixed_precision == "fp16",
            "set_cost_class": self.set_cost_class,
            "set_cost_bbox": self.set_cost_bbox,
            "set_cost_giou": self.set_cost_giou,
            "ema_decay": self.ema_decay,
            "ema_tau": self.ema_tau,
            "lr_vit_layer_decay": self.lr_vit_layer_decay,
        }
