"""Shared CLI utilities for detection and segmentation commands."""

import argparse
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

TRAIN_PARSER_DEFAULTS = {
    "epochs": 10,
    "batch_size": 16,
    "learning_rate": 0.001,
    "imgsz": 640,
    "device": "auto",
    "seed": 42,
    "output_dir": "outputs",
    "dataset_format": "yolo",
    "mixed_precision": "no",
    "gradient_accumulation_steps": 1,
    "weight_decay": 0.0001,
    "warmup_ratio": 0.1,
    "lr_scheduler_type": "linear",
    "eval_split": "test",
    "conf_threshold": 0.25,
    "iou_threshold": 0.5,
}

ARG_TO_CONFIG_KEY = {
    "dataset": "dataset_path",
    "learning_rate": "learning_rate",
    "output_dir": "output_dir",
    "batch_size": "batch_size",
    "hub_model_id": "hub_model_id",
    "gradient_accumulation_steps": "gradient_accumulation_steps",
    "early_stopping_patience": "early_stopping_patience",
    "weight_decay": "weight_decay",
    "warmup_ratio": "warmup_ratio",
    "lr_scheduler_type": "lr_scheduler_type",
    "eval_split": "eval_split",
    "conf_threshold": "conf_threshold",
    "iou_threshold": "iou_threshold",
    "dataset_format": "dataset_format",
    "mixed_precision": "mixed_precision",
    "epochs": "epochs",
    "imgsz": "imgsz",
    "model": "model",
    "framework": "framework",
    "resolution": "resolution",
    "lr_encoder": "lr_encoder",
    "use_ema": "use_ema",
    "gradient_checkpointing": "gradient_checkpointing",
    "drop_path": "drop_path",
    "drop_mode": "drop_mode",
    "drop_schedule": "drop_schedule",
    "freeze_encoder": "freeze_encoder",
    "layer_norm": "layer_norm",
    "rms_norm": "rms_norm",
    "multi_scale": "multi_scale",
    "ema_decay": "ema_decay",
    "sync_bn": "sync_bn",
    "num_workers": "num_workers",
    "warmup_epochs": "warmup_epochs",
    "warmup_momentum": "warmup_momentum",
    "cos_lr": "cos_lr",
    "dropout": "dropout",
}


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load and flatten a YAML configuration file.

    Supports sectioned format with ``data``, ``train``, and ``eval`` keys.
    Eval keys that conflict with train keys are prefixed with ``eval_``.
    """
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    flat: Dict[str, Any] = {}

    if "data" in config:
        flat.update(config["data"])

    if "train" in config:
        flat.update(config["train"])

    if "eval" in config:
        for k, v in config["eval"].items():
            if k in ("batch_size", "device", "output_dir", "num_samples"):
                flat[f"eval_{k}"] = v
            elif k not in flat:
                flat[k] = v

    if "gradient_checkpoint" in flat and "gradient_checkpointing" not in flat:
        flat["gradient_checkpointing"] = flat.pop("gradient_checkpoint")

    return flat


def merge_config_with_args(
    config: Dict[str, Any],
    args: argparse.Namespace,
    parser_defaults: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Merge a YAML config dict with CLI args. CLI args take precedence,
    but parser defaults do not override explicit config values.
    """
    if parser_defaults is None:
        parser_defaults = TRAIN_PARSER_DEFAULTS

    result = config.copy()

    for arg_name, value in vars(args).items():
        if value is None or arg_name == "config":
            continue

        config_key = ARG_TO_CONFIG_KEY.get(arg_name, arg_name)

        if isinstance(value, bool):
            if value:
                result[config_key] = value
            continue

        default_value = parser_defaults.get(arg_name)
        if default_value is not None and value == default_value and config_key in config:
            continue

        result[config_key] = value

    return result


def resolve_paths(dataset: str, output_dir: str) -> Tuple[str, str]:
    """Resolve relative dataset and output_dir paths to absolute."""
    base_dir = Path.cwd()

    dataset_path = Path(dataset)
    if not dataset_path.is_absolute():
        dataset = str((base_dir / dataset_path).resolve())

    output_dir_path = Path(output_dir)
    if not output_dir_path.is_absolute():
        output_dir = str((base_dir / output_dir_path).resolve())

    return dataset, output_dir


def detect_framework(model_name: str, task: str = "detection") -> str:
    """
    Auto-detect framework from model name.

    Parameters
    ----------
    model_name : str
        Model name or path.
    task : str
        Task type ('detection' or 'segmentation') to adjust heuristics.
    """
    model_lower = model_name.lower()
    normalized = model_lower.replace("-", "").replace("_", "")

    if "rfdetr" in normalized:
        return "rfdetr"

    if task == "segmentation":
        if any(kw in model_lower for kw in ["mask2former", "maskformer", "segformer"]):
            return "transformers"
        if any(kw in model_lower for kw in ["facebook/", "microsoft/", "nvidia/"]):
            return "transformers"
        return "ultralytics"

    if any(kw in model_lower for kw in ["detr", "facebook/", "microsoft/"]):
        return "transformers"
    return "ultralytics"


def add_common_train_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add training arguments shared by detection and segmentation."""
    parser.add_argument("--config", type=str, help="Path to YAML config file")
    parser.add_argument("--model", type=str, help="Model name or path")
    parser.add_argument(
        "--framework", type=str, help="Framework (ultralytics, transformers, rfdetr)"
    )
    parser.add_argument("--dataset", type=str, help="Path to dataset")
    parser.add_argument(
        "--dataset-format", type=str, default="yolo", help="Dataset format (yolo, coco)"
    )
    parser.add_argument("--output-dir", type=str, default="outputs", help="Output directory")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--learning-rate", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--tensorboard", action="store_true", help="Enable TensorBoard")
    parser.add_argument("--push-to-hub", action="store_true", help="Push to HuggingFace Hub")
    parser.add_argument("--hub-model-id", type=str, help="HuggingFace model ID")
    parser.add_argument("--multi-gpu", action="store_true", help="Enable multi-GPU")
    parser.add_argument("--mixed-precision", type=str, default="no", choices=["no", "fp16", "bf16"])
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--early-stopping-patience", type=int, help="Early stopping patience")
    parser.add_argument("--from-scratch", action="store_true", help="Train from scratch")
    parser.add_argument("--weight-decay", type=float, default=0.0001, help="Weight decay")
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--lr-scheduler-type", type=str, default="linear", help="LR scheduler")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate after training")
    parser.add_argument("--eval-split", type=str, default="test", help="Evaluation split")
    parser.add_argument("--conf-threshold", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    return parser


def add_common_predict_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add prediction arguments shared by detection and segmentation."""
    parser.add_argument("--model", type=str, required=True, help="Model path or name")
    parser.add_argument("--input", type=str, required=True, help="Input image or directory")
    parser.add_argument(
        "--output", type=str, default="outputs/predictions", help="Output directory"
    )
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--conf-threshold", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.45, help="IoU threshold")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--show", action="store_true", help="Display predictions")
    return parser


def add_common_eval_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add evaluation arguments shared by detection and segmentation."""
    parser.add_argument("--model-path", type=str, required=True, help="Model path")
    parser.add_argument(
        "--framework",
        type=str,
        required=True,
        choices=["ultralytics", "transformers", "rfdetr"],
        help="Framework",
    )
    parser.add_argument("--dataset-path", type=str, required=True, help="Dataset path")
    parser.add_argument("--output-dir", type=str, default="outputs/evaluation", help="Output dir")
    parser.add_argument(
        "--dataset-type", type=str, default="auto", choices=["coco", "yolo", "auto"]
    )
    parser.add_argument("--split", type=str, default="test", help="Dataset split")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="IoU threshold")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--num-samples", type=int, help="Number of samples to evaluate")
    parser.add_argument(
        "--num-prediction-samples",
        type=int,
        default=4,
        help="Number of test images to render in prediction_samples.png",
    )
    parser.add_argument(
        "--conf-per-class",
        type=str,
        help=(
            "Per-class confidence thresholds for the operating-point report. "
            "Comma-separated 'name=value' pairs (e.g. 'rose=0.47,sphere=0.70'). "
            "When set, replaces --conf-threshold for P/R/F1 and prediction "
            "samples; mAP curves are unaffected."
        ),
    )
    parser.add_argument("--rfdetr-size", type=str, help="RF-DETR model size")
    parser.add_argument("--resolution", type=int, help="Resolution for RF-DETR")
    return parser


def parse_conf_per_class(spec: str, class_names) -> Dict[int, float]:
    """Parse 'name=value,name=value' into {class_id: threshold}.

    `class_names` may be a list (`['rose', 'sphere']`) or a dict
    (`{0: 'rose', 1: 'sphere'}`). Names not present in the model's class list
    raise ValueError so typos fail loudly.
    """
    if isinstance(class_names, dict):
        name_to_id = {v: k for k, v in class_names.items()}
    else:
        name_to_id = {n: i for i, n in enumerate(class_names)}

    mapping: Dict[int, float] = {}
    for chunk in spec.split(","):
        if not chunk.strip():
            continue
        name, _, value = chunk.partition("=")
        name = name.strip()
        if name not in name_to_id:
            raise ValueError(
                f"Unknown class '{name}' in --conf-per-class; expected one of {list(name_to_id)}"
            )
        mapping[name_to_id[name]] = float(value)
    return mapping


def collect_common_train_params(
    params: Dict[str, Any], dataset: str, output_dir: str
) -> Dict[str, Any]:
    """Build the common_args dict consumed by all framework training configs."""
    return {
        "dataset_path": dataset,
        "epochs": params.get("epochs", 10),
        "batch_size": params.get("batch_size", 16),
        "learning_rate": float(params.get("learning_rate", 0.001)),
        "output_dir": output_dir,
        "device": params.get("device", "auto"),
        "seed": params.get("seed", 42),
        "tensorboard": params.get("tensorboard", False),
        "push_to_hub": params.get("push_to_hub", False),
        "hub_model_id": params.get("hub_model_id"),
        "multi_gpu": params.get("multi_gpu", False),
        "mixed_precision": params.get("mixed_precision", "no"),
        "gradient_accumulation_steps": params.get("gradient_accumulation_steps", 1),
        "early_stopping_patience": params.get("early_stopping_patience"),
        "early_stopping_delta": params.get("early_stopping_delta", 0.0),
        "early_stopping_metric": params.get("early_stopping_metric", "eval_loss"),
        "early_stopping_mode": params.get("early_stopping_mode", "min"),
        "from_scratch": params.get("from_scratch", False),
        "imgsz": params.get("imgsz", 640),
        "weight_decay": params.get("weight_decay", 0.0001),
        "warmup_ratio": params.get("warmup_ratio", 0.1),
        "warmup_steps": params.get("warmup_steps", 10),
        "lr_scheduler_type": params.get("lr_scheduler_type", "linear"),
        "max_grad_norm": params.get("max_grad_norm", 1.0),
        "optimizer_type": params.get("optimizer_type"),
        "save_period": params.get("save_period", 1),
        "max_train_samples": params.get("max_train_samples"),
        "max_eval_samples": params.get("max_eval_samples"),
        "max_test_samples": params.get("max_test_samples"),
        "train_split": params.get("train_split", 0.8),
        "val_split": params.get("val_split", 0.2),
        "test_split": params.get("test_split", 0.0),
        "dataset_format": params.get("dataset_format"),
        "gc_per_accumulation": params.get("gc_per_accumulation", True),
        "resume": params.get("resume", False),
    }


def add_ultralytics_args(common_args: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Extend common_args in-place with Ultralytics-specific parameters."""
    common_args.update(
        {
            "warmup_epochs": params.get("warmup_epochs", 3.0),
            "warmup_momentum": params.get("warmup_momentum", 0.8),
            "lrf": params.get("lrf", 0.01),
            "cos_lr": params.get("cos_lr", False),
            "dropout": params.get("dropout", 0.0),
            "freeze": params.get("freeze"),
        }
    )


def add_rfdetr_args(common_args: Dict[str, Any], params: Dict[str, Any]) -> None:
    """Extend common_args in-place with RF-DETR-specific parameters."""
    common_args.update(
        {
            "resolution": params.get("resolution", params.get("imgsz", 560)),
            "lr_encoder": params.get("lr_encoder"),
            "use_ema": params.get("use_ema", True),
            "gradient_checkpointing": params.get("gradient_checkpointing")
            or params.get("gradient_checkpoint", False),
            "drop_path": params.get("drop_path", 0.0),
            "drop_mode": params.get("drop_mode", "standard"),
            "drop_schedule": params.get("drop_schedule", "constant"),
            "cutoff_epoch": params.get("cutoff_epoch", 0),
            "freeze_encoder": params.get("freeze_encoder", False),
            "layer_norm": params.get("layer_norm", False),
            "rms_norm": params.get("rms_norm", False),
            "backbone_lora": params.get("backbone_lora", False),
            "multi_scale": params.get("multi_scale", False),
            "force_no_pretrain": params.get("force_no_pretrain", False),
            "ema_decay": params.get("ema_decay", 0.9997),
            "ema_tau": params.get("ema_tau", 0.0),
            "lr_vit_layer_decay": params.get("lr_vit_layer_decay", 0.8),
            "lr_component_decay": params.get("lr_component_decay", 1.0),
            "sync_bn": params.get("sync_bn", True),
            "num_workers": params.get("num_workers", 2),
            "set_cost_class": params.get("set_cost_class", 2.0),
            "set_cost_bbox": params.get("set_cost_bbox", 5.0),
            "set_cost_giou": params.get("set_cost_giou", 2.0),
            "start_epoch": params.get("start_epoch", 0),
            "early_stopping_use_ema": params.get("early_stopping_use_ema", False),
            "warmup_epochs": params.get("warmup_epochs", 3.0),
            "dropout": params.get("dropout", 0.0),
            "rfdetr_size": params.get("rfdetr_size"),
        }
    )
