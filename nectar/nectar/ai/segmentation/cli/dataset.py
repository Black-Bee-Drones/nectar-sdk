"""CLI for segmentation dataset management operations."""

import argparse
import logging
import sys
from pathlib import Path

from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.segmentation.datasets.analyze import SegDatasetAnalyzer
from nectar.ai.segmentation.datasets.format import SegFormatConverter
from nectar.ai.segmentation.datasets.handlers import SegDatasetHandlerRegistry

logger = logging.getLogger(__name__)


def cmd_download(args):
    """Download a segmentation dataset."""
    handler_name = args.source.lower()
    handler_class = SegDatasetHandlerRegistry.get(handler_name)

    if not handler_class:
        logger.error("Unknown dataset source: %s", handler_name)
        logger.info("Available: %s", SegDatasetHandlerRegistry.list_handlers())
        sys.exit(1)

    from nectar.ai.segmentation.core.configs import DEFAULT_DATA_DIR

    output_dir = Path(args.output).resolve()
    default_data_dir = Path(DEFAULT_DATA_DIR).resolve()
    if output_dir == default_data_dir:
        dataset_id = getattr(args, "dataset", handler_name)
        output_dir = output_dir / dataset_id

    output_dir.mkdir(parents=True, exist_ok=True)

    if handler_name == "ultralytics":
        dataset_name = args.dataset
        if not dataset_name:
            logger.error("--dataset is required for ultralytics source (e.g. crack-seg)")
            sys.exit(1)
        handler = handler_class(str(output_dir), dataset_name)
        handler.download_and_convert(
            output_format=args.format,
            num_workers=args.num_workers,
        )
    elif handler_name == "roboflow":
        if not args.api_key:
            logger.error("--api-key is required for roboflow source")
            sys.exit(1)
        handler = handler_class(str(output_dir), args.api_key)
        handler.download(
            workspace=args.workspace,
            project=args.project,
            version=args.version,
            format_type=args.roboflow_format or "yolov8",
        )
    else:
        logger.error("Handler %s not yet supported in CLI", handler_name)
        sys.exit(1)


def cmd_convert(args):
    """Convert segmentation dataset format."""
    from nectar.ai.detection.datasets.format import FormatDetector

    detector = FormatDetector(args.input)
    source_format = detector.detect()

    if source_format == "unknown":
        logger.error("Could not detect format in %s", args.input)
        sys.exit(1)

    target_format = args.format.lower()
    if source_format == target_format:
        logger.info("Dataset already in %s format", target_format)
        return

    converter = SegFormatConverter(
        args.input,
        args.output,
        num_workers=args.num_workers,
    )
    converter.convert(
        target_format=target_format,
        copy_images=args.copy_images,
        num_workers=args.num_workers,
    )
    logger.info("Converted to %s format: %s", target_format, args.output)


def cmd_subset(args):
    """Create balanced subset of dataset."""
    creator = SubsetCreator(args.input, args.output, seed=args.seed)
    result = creator.create(
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        max_test_samples=args.max_test_samples,
    )
    logger.info("Subset saved to: %s", result)


def cmd_analyze(args):
    """Analyze segmentation dataset distribution."""
    analyzer = SegDatasetAnalyzer(args.input, output_dir=args.output)
    analyzer.analyze()
    logger.info("Analysis complete. Results saved to: %s", args.output or f"{args.input}/analysis")


def main():
    """Main entry point for segmentation dataset CLI."""
    parser = argparse.ArgumentParser(description="Segmentation dataset management")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # ---- download ----
    dl_parser = subparsers.add_parser("download", help="Download segmentation dataset")
    dl_parser.add_argument(
        "--source",
        required=True,
        help="Dataset source (ultralytics, roboflow)",
    )
    dl_parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset identifier for ultralytics (e.g. crack-seg)",
    )

    from nectar.ai.segmentation.core.configs import DEFAULT_DATA_DIR

    dl_parser.add_argument(
        "--output",
        default=str(DEFAULT_DATA_DIR),
        help=f"Output directory (default: {DEFAULT_DATA_DIR}/<dataset>)",
    )
    dl_parser.add_argument(
        "--format",
        default="yolo",
        choices=["yolo", "coco", "both"],
        help="Output format",
    )
    dl_parser.add_argument("--num-workers", type=int, default=None)

    dl_parser.add_argument("--api-key", help="Roboflow API key")
    dl_parser.add_argument("--workspace", help="Roboflow workspace")
    dl_parser.add_argument("--project", help="Roboflow project")
    dl_parser.add_argument("--version", type=int, help="Roboflow version")
    dl_parser.add_argument(
        "--roboflow-format",
        default=None,
        help="Roboflow export format (yolov8, coco, etc.)",
    )

    # ---- convert ----
    conv_parser = subparsers.add_parser("convert", help="Convert dataset format")
    conv_parser.add_argument("--input", required=True, help="Input dataset directory")
    conv_parser.add_argument("--output", required=True, help="Output directory")
    conv_parser.add_argument(
        "--format",
        required=True,
        choices=["coco", "yolo"],
        help="Target format",
    )
    conv_parser.add_argument("--copy-images", action="store_true", default=True)
    conv_parser.add_argument("--num-workers", type=int, default=None)

    # ---- subset ----
    sub_parser = subparsers.add_parser("subset", help="Create balanced subset")
    sub_parser.add_argument("--input", required=True)
    sub_parser.add_argument("--output", required=True)
    sub_parser.add_argument("--max-train-samples", type=int)
    sub_parser.add_argument("--max-eval-samples", type=int)
    sub_parser.add_argument("--max-test-samples", type=int)
    sub_parser.add_argument("--seed", type=int, default=42)

    # ---- analyze ----
    an_parser = subparsers.add_parser("analyze", help="Analyze dataset")
    an_parser.add_argument("--input", required=True, help="Input dataset directory")
    an_parser.add_argument("--output", help="Output directory (default: input/analysis)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "download": cmd_download,
        "convert": cmd_convert,
        "subset": cmd_subset,
        "analyze": cmd_analyze,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
