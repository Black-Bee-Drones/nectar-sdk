"""CLI for training detection models."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict

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
        "--output-dir",
        type=str,
        default="outputs",
        help="Output directory (default: outputs)",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--learning-rate", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")

    # Training options
    parser.add_argument("--tensorboard", action="store_true", help="Enable TensorBoard")
    parser.add_argument("--push-to-hub", action="store_true", help="Push to HuggingFace Hub")
    parser.add_argument("--hub-model-id", type=str, help="HuggingFace model ID")
    parser.add_argument("--multi-gpu", action="store_true", help="Enable multi-GPU")
    parser.add_argument("--mixed-precision", type=str, default="no", choices=["no", "fp16", "bf16"])
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--early-stopping-patience", type=int, help="Early stopping patience")
    parser.add_argument("--from-scratch", action="store_true", help="Train from scratch")

    # Optimizer
    parser.add_argument("--weight-decay", type=float, default=0.0001, help="Weight decay")
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--lr-scheduler-type", type=str, default="linear", help="LR scheduler")

    # Evaluation
    parser.add_argument("--evaluate", action="store_true", help="Evaluate after training")
    parser.add_argument("--eval-split", type=str, default="test", help="Evaluation split")
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
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Flatten config sections
    flat = {}

    if "data" in config:
        flat.update(config["data"])

    if "train" in config:
        flat.update(config["train"])

    if "eval" in config:
        for k, v in config["eval"].items():
            # Prefix eval-specific keys to avoid conflicts with train keys
            if k in ("batch_size", "device", "output_dir", "num_samples"):
                flat[f"eval_{k}"] = v
            elif k not in flat:
                flat[k] = v

    return flat


def merge_config_with_args(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """
    Merge config file with CLI arguments.

    CLI arguments take precedence over config file.
    """
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
        "epochs": "epochs",
        "imgsz": "imgsz",
        "model": "model",
        "framework": "framework",
    }

    result = config.copy()

    parser_defaults = {
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

    for arg_name, value in vars(args).items():
        if value is None or arg_name == "config":
            continue

        config_key = arg_to_config.get(arg_name, arg_name)

        if isinstance(value, bool):
            if value:
                result[config_key] = value
            continue

        default_value = parser_defaults.get(arg_name)
        if default_value is not None and value == default_value and config_key in config:
            continue

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

    # Resolve relative paths from CWD
    base_dir = Path.cwd()

    dataset_path = Path(dataset)
    if not dataset_path.is_absolute():
        dataset = str((base_dir / dataset_path).resolve())

    output_dir_raw = params.get("output_dir", "outputs")
    output_dir_path = Path(output_dir_raw)
    if not output_dir_path.is_absolute():
        output_dir_raw = str((base_dir / output_dir_path).resolve())

    # Detect framework
    framework = params.get("framework") or detect_framework(model)
    logger.info("Framework: %s", framework)

    # Import framework-specific config and model
    from nectar.ai.detection import Detector
    from nectar.ai.detection.core.configs import EvaluationConfig
    from nectar.ai.detection.evaluation.evaluator import ObjectDetectionEvaluator
    from nectar.ai.detection.training.config import (
        RFDETRTrainingConfig,
        TransformersTrainingConfig,
        UltralyticsTrainingConfig,
    )
    from nectar.ai.detection.utils.huggingface import HuggingFaceUploader
    from nectar.ai.detection.utils.tensorboard import TensorBoardManager

    # Build training config
    common_args = {
        "dataset_path": dataset,
        "epochs": params.get("epochs", 10),
        "batch_size": params.get("batch_size", 16),
        "learning_rate": float(params.get("learning_rate", 0.001)),
        "output_dir": output_dir_raw,
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
        "warmup_epochs": params.get("warmup_epochs", 3.0),
        "warmup_momentum": params.get("warmup_momentum", 0.8),
        "lrf": params.get("lrf", 0.01),
        "cos_lr": params.get("cos_lr", False),
        "dropout": params.get("dropout", 0.0),
        "max_train_samples": params.get("max_train_samples"),
        "max_eval_samples": params.get("max_eval_samples"),
        "max_test_samples": params.get("max_test_samples"),
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

    # Start TensorBoard server if requested
    tb_manager = TensorBoardManager()
    if params.get("start_tensorboard") and params.get("tensorboard"):
        tb_port = params.get("tensorboard_port", 6006)
        tb_manager.start_server(log_dir=output_dir_raw, port=tb_port)

    detector = Detector(model, framework=framework, device=params.get("device", "auto"))
    detector.load()

    logger.info("Starting training...")

    try:
        result = detector.train(training_config)
        logger.info("Training completed")
        logger.info("Model saved: %s", result.get("model_path", "N/A"))

        if params.get("push_to_hub") and params.get("hub_model_id"):
            logger.info("Uploading training outputs to HuggingFace Hub...")
            try:
                uploader = HuggingFaceUploader(
                    repo_id=params["hub_model_id"],
                    local_dir=output_dir_raw,
                    repo_type="model",
                )

                ignore_patterns = [
                    "*.tmp",
                    "*.bak",
                    "__pycache__",
                    "*.git*",
                    "*.pyc",
                    ".ipynb_checkpoints",
                    "datasets/**",
                ]

                uploader.upload(
                    commit_message="Upload complete training results",
                    ignore_patterns=ignore_patterns,
                )
                logger.info(
                    "Successfully uploaded training outputs to %s",
                    params["hub_model_id"],
                )
            except Exception as e:
                logger.error("Failed to upload training outputs: %s", e)

        # Evaluate if requested
        if params.get("evaluate"):
            eval_split = params.get("eval_split", "test")
            eval_batch = params.get("eval_batch_size", params.get("batch_size", 1))
            eval_device = params.get("eval_device", params.get("device", "auto"))
            eval_samples = params.get("eval_num_samples", params.get("max_test_samples"))
            eval_output = params.get("eval_output_dir", str(Path(output_dir_raw) / "evaluation"))
            logger.info("Evaluating on %s split", eval_split)

            eval_config = EvaluationConfig(
                model_path=result["model_path"],
                dataset_path=dataset,
                framework=framework,
                output_dir=eval_output,
                split=eval_split,
                conf_threshold=params.get("conf_threshold", 0.25),
                iou_threshold=params.get("iou_threshold", 0.5),
                device=eval_device,
                batch_size=eval_batch,
                num_samples=eval_samples,
                imgsz=params.get("imgsz"),
            )

            evaluator = ObjectDetectionEvaluator(detector.model, eval_config)
            metrics = evaluator.evaluate()

            logger.info("mAP@50: %.4f", metrics.map50)
            logger.info("mAP@50-95: %.4f", metrics.map50_95)

            # Upload evaluation results to HuggingFace Hub if enabled
            if params.get("push_to_hub") and params.get("hub_model_id"):
                logger.info("Uploading evaluation results to HuggingFace Hub...")
                try:
                    eval_uploader = HuggingFaceUploader(
                        repo_id=params["hub_model_id"],
                        local_dir=eval_output,
                        repo_type="model",
                    )

                    ignore_patterns = [
                        "*.tmp",
                        "*.bak",
                        "__pycache__",
                        "*.git*",
                        "*.pyc",
                        ".ipynb_checkpoints",
                    ]

                    eval_uploader.upload(
                        commit_message="Add evaluation results",
                        path_in_repo="evaluation",
                        ignore_patterns=ignore_patterns,
                    )
                    logger.info(
                        "Successfully uploaded evaluation results to %s in 'evaluation' folder",
                        params["hub_model_id"],
                    )
                except Exception as e:
                    logger.error("Failed to upload evaluation results: %s", e)

    except Exception as e:
        logger.error("Training failed: %s", e)
        raise
    finally:
        tb_manager.stop_server()


if __name__ == "__main__":
    main()
