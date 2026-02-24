"""Unified CLI for detection module."""

import argparse
import logging
import sys
from pathlib import Path

from nectar.ai.detection.core.configs import DEFAULT_OUTPUT_DIR

logger = logging.getLogger(__name__)


def main():
    """Main entry point for unified CLI."""
    parser = argparse.ArgumentParser(
        description="Nectar Detection - Unified CLI for object detection",
        prog="nectar detection",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    train_parser = subparsers.add_parser("train", help="Train detection model")
    train_parser.add_argument("--config", help="Path to YAML config file")
    train_parser.add_argument("--model", help="Model name or path")
    train_parser.add_argument(
        "--framework", help="Framework (ultralytics, transformers, rfdetr)"
    )
    train_parser.add_argument("--dataset", help="Path to dataset")
    train_parser.add_argument(
        "--dataset-format", default="yolo", help="Dataset format (yolo, coco)"
    )
    train_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    train_parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    train_parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    train_parser.add_argument(
        "--learning-rate", type=float, default=0.001, help="Learning rate"
    )
    train_parser.add_argument("--device", default="auto", help="Device")
    train_parser.add_argument("--seed", type=int, default=42, help="Random seed")

    predict_parser = subparsers.add_parser("predict", help="Run inference")
    predict_parser.add_argument("--model", required=True, help="Model path")
    predict_parser.add_argument(
        "--input", required=True, help="Input image or directory"
    )
    predict_parser.add_argument("--output", help="Output directory")
    predict_parser.add_argument(
        "--conf", type=float, default=0.25, help="Confidence threshold"
    )
    predict_parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold")
    predict_parser.add_argument("--device", default="auto", help="Device")

    eval_parser = subparsers.add_parser("eval", help="Evaluate model")
    eval_parser.add_argument(
        "--model-path", required=True, help="Model checkpoint path"
    )
    eval_parser.add_argument("--dataset-path", required=True, help="Dataset path")
    eval_parser.add_argument("--framework", required=True, help="Framework")
    eval_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR / "evaluations"),
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR / 'evaluations'})",
    )
    eval_parser.add_argument("--split", default="test", help="Dataset split")
    eval_parser.add_argument(
        "--conf-threshold", type=float, default=0.5, help="Confidence threshold"
    )
    eval_parser.add_argument(
        "--iou-threshold", type=float, default=0.5, help="IoU threshold"
    )
    eval_parser.add_argument("--device", default="auto", help="Device")
    eval_parser.add_argument("--batch-size", type=int, default=16, help="Batch size")

    dataset_parser = subparsers.add_parser("dataset", help="Dataset management")
    dataset_parser.add_argument(
        "subcommand",
        choices=[
            "download",
            "convert",
            "stratify",
            "subset",
            "augment",
            "analyze",
            "merge",
            "upload",
            "upload-images",
        ],
        help="Dataset operation",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "train":
            from nectar.ai.detection.cli.train import main as train_main

            sys.argv = ["train"] + [
                f"--{k}={v}" for k, v in vars(args).items() if v and k != "command"
            ]
            train_main()
        elif args.command == "predict":
            from nectar.ai.detection.cli.predict import main as predict_main

            sys.argv = ["predict"] + [
                f"--{k}={v}" for k, v in vars(args).items() if v and k != "command"
            ]
            predict_main()
        elif args.command == "eval":
            from nectar.ai.detection.cli.evaluate import main as eval_main

            sys.argv = ["evaluate"] + [
                f"--{k.replace('_', '-')}={v}"
                for k, v in vars(args).items()
                if v and k != "command"
            ]
            eval_main()
        elif args.command == "dataset":
            from nectar.ai.detection.cli.dataset import main as dataset_main

            sys.argv = ["dataset", args.subcommand] + [
                f"--{k}={v}"
                for k, v in vars(args).items()
                if v and k not in ["command", "subcommand"]
            ]
            dataset_main()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
