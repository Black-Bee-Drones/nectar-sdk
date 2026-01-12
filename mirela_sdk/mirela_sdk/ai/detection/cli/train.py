"""CLI for training detection models."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Train object detection models")

    # Config file
    parser.add_argument("--config", type=str, help="Path to YAML config file")

    # Model and data
    parser.add_argument("--model", type=str, help="Model name or path")
    parser.add_argument(
        "--framework", type=str, help="Framework (ultralytics, transformers, rfdetr)"
    )
    parser.add_argument("--dataset", type=str, help="Path to dataset")
    parser.add_argument(
        "--dataset-format", type=str, default="yolo", help="Dataset format (yolo, coco)"
    )

    # Training parameters
    parser.add_argument(
        "--output-dir", type=str, default="outputs", help="Output directory"
    )
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument(
        "--learning-rate", type=float, default=0.001, help="Learning rate"
    )
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")

    # Training options
    parser.add_argument("--tensorboard", action="store_true", help="Enable TensorBoard")
    parser.add_argument(
        "--push-to-hub", action="store_true", help="Push to HuggingFace Hub"
    )
    parser.add_argument("--hub-model-id", type=str, help="HuggingFace model ID")
    parser.add_argument("--multi-gpu", action="store_true", help="Enable multi-GPU")
    parser.add_argument(
        "--mixed-precision", type=str, default="no", choices=["no", "fp16", "bf16"]
    )
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument(
        "--early-stopping-patience", type=int, help="Early stopping patience"
    )
    parser.add_argument(
        "--from-scratch", action="store_true", help="Train from scratch"
    )

    # Optimizer
    parser.add_argument(
        "--weight-decay", type=float, default=0.0001, help="Weight decay"
    )
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument(
        "--lr-scheduler-type", type=str, default="linear", help="LR scheduler"
    )

    # Evaluation
    parser.add_argument(
        "--evaluate", action="store_true", help="Evaluate after training"
    )
    parser.add_argument(
        "--eval-split", type=str, default="test", help="Evaluation split"
    )
    parser.add_argument("--conf-threshold", type=float, default=0.25)
    parser.add_argument("--iou-threshold", type=float, default=0.5)

    return parser.parse_args()


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Expected format:
        data:
          dataset_path: /path/to/dataset
          dataset_format: coco

        train:
          framework: transformers
          model: facebook/detr-resnet-50
          epochs: 100
          ...

        eval:
          eval_split: test
          conf_threshold: 0.25
          ...
    """
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Flatten config sections
    flat = {}

    if "data" in config:
        flat.update(config["data"])

    if "train" in config:
        flat.update(config["train"])

    if "eval" in config:
        for k, v in config["eval"].items():
            if k not in flat:
                flat[k] = v

    return flat


def merge_config_with_args(
    config: Dict[str, Any], args: argparse.Namespace
) -> Dict[str, Any]:
    """
    Merge config file with CLI arguments.

    CLI arguments take precedence over config file.
    """
    # Map CLI arg names to config keys
    arg_to_config = {
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
    }

    result = config.copy()

    for arg_name, value in vars(args).items():
        if value is None:
            continue

        # Skip config path
        if arg_name == "config":
            continue

        # Handle boolean flags
        if isinstance(value, bool):
            if value:
                config_key = arg_to_config.get(arg_name, arg_name)
                result[config_key] = value
            continue

        # Map arg name to config key
        config_key = arg_to_config.get(arg_name, arg_name)

        # CLI overrides config
        if arg_name in vars(args) and value != getattr(
            parse_args.__defaults__, arg_name, None
        ):
            result[config_key] = value
        elif config_key not in result:
            result[config_key] = value

    return result


def detect_framework(model_name: str) -> str:
    """Auto-detect framework from model name."""
    model_lower = model_name.lower()

    if "rfdetr" in model_lower:
        return "rfdetr"
    if any(x in model_lower for x in ["detr", "facebook/", "microsoft/"]):
        return "transformers"
    return "ultralytics"


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = parse_args()

    # Load config if provided
    config = {}
    if args.config:
        logger.info("Loading config: %s", args.config)
        config = load_config(args.config)

    # Merge with CLI args
    params = merge_config_with_args(config, args)

    # Validate required params
    model = params.get("model")
    dataset = params.get("dataset_path")

    if not model:
        logger.error("Model is required (--model or config train.model)")
        sys.exit(1)
    if not dataset:
        logger.error("Dataset is required (--dataset or config data.dataset_path)")
        sys.exit(1)

    # Detect framework
    framework = params.get("framework") or detect_framework(model)
    logger.info("Framework: %s", framework)

    # Import framework-specific config and model
    from mirela_sdk.ai.detection import Detector
    from mirela_sdk.ai.detection.core.configs import EvaluationConfig
    from mirela_sdk.ai.detection.training.config import (
        UltralyticsTrainingConfig,
        TransformersTrainingConfig,
        RFDETRTrainingConfig,
    )
    from mirela_sdk.ai.detection.evaluation.evaluator import ObjectDetectionEvaluator

    # Build training config
    common_args = {
        "dataset_path": dataset,
        "epochs": params.get("epochs", 10),
        "batch_size": params.get("batch_size", 16),
        "learning_rate": params.get("learning_rate", 0.001),
        "output_dir": params.get("output_dir", "outputs"),
        "device": params.get("device", "auto"),
        "seed": params.get("seed", 42),
        "tensorboard": params.get("tensorboard", False),
        "push_to_hub": params.get("push_to_hub", False),
        "hub_model_id": params.get("hub_model_id"),
        "multi_gpu": params.get("multi_gpu", False),
        "mixed_precision": params.get("mixed_precision", "no"),
        "gradient_accumulation_steps": params.get("gradient_accumulation_steps", 1),
        "early_stopping_patience": params.get("early_stopping_patience"),
        "from_scratch": params.get("from_scratch", False),
        "imgsz": params.get("imgsz", 640),
        "weight_decay": params.get("weight_decay", 0.0001),
        "warmup_ratio": params.get("warmup_ratio", 0.1),
        "lr_scheduler_type": params.get("lr_scheduler_type", "linear"),
    }

    # Create framework-specific config
    if framework == "ultralytics":
        training_config = UltralyticsTrainingConfig(model=model, **common_args)
    elif framework == "transformers":
        training_config = TransformersTrainingConfig(model=model, **common_args)
    elif framework == "rfdetr":
        # Add RF-DETR specific params
        common_args["resolution"] = params.get("resolution", params.get("imgsz", 560))
        if "lr_encoder" in params:
            common_args["lr_encoder"] = params["lr_encoder"]
        if "use_ema" in params:
            common_args["use_ema"] = params["use_ema"]
        if "gradient_checkpointing" in params:
            common_args["gradient_checkpointing"] = params["gradient_checkpointing"]
        training_config = RFDETRTrainingConfig(model=model, **common_args)
    else:
        logger.error("Unsupported framework: %s", framework)
        sys.exit(1)

    # Create detector and train
    logger.info("Model: %s", model)
    logger.info("Dataset: %s", dataset)
    logger.info("Output: %s", params.get("output_dir"))

    detector = Detector(model, framework=framework, device=params.get("device", "auto"))
    detector.load()

    logger.info("Starting training...")

    try:
        result = detector.train(training_config)
        logger.info("Training completed")
        logger.info("Model saved: %s", result.get("model_path", "N/A"))

        # Evaluate if requested
        if params.get("evaluate"):
            eval_split = params.get("eval_split", "test")
            logger.info("Evaluating on %s split", eval_split)

            eval_config = EvaluationConfig(
                model_path=result["model_path"],
                dataset_path=dataset,
                framework=framework,
                output_dir=str(Path(params.get("output_dir")) / "evaluation"),
                split=eval_split,
                conf_threshold=params.get("conf_threshold", 0.25),
                iou_threshold=params.get("iou_threshold", 0.5),
                device=params.get("device", "auto"),
                batch_size=params.get("batch_size", 16),
            )

            evaluator = ObjectDetectionEvaluator(detector.model, eval_config)
            metrics = evaluator.evaluate()

            logger.info("mAP@50: %.4f", metrics.map50)
            logger.info("mAP@50-95: %.4f", metrics.map50_95)

    except Exception as e:
        logger.error("Training failed: %s", e)
        raise


if __name__ == "__main__":
    main()
