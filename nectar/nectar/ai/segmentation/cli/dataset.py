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
        dataset_id = getattr(args, "dataset", None)
        if not dataset_id and handler_name in ("huggingface", "hf") and args.repo:
            dataset_id = args.repo.split("/")[-1]
        output_dir = output_dir / (dataset_id or handler_name)

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
    elif handler_name in ("huggingface", "hf"):
        if not args.repo:
            logger.error("--repo is required for huggingface source (e.g. user/dataset)")
            sys.exit(1)
        hf_format = args.format if args.format in ("coco", "yolo") else "yolo"
        handler = handler_class(str(output_dir), token=args.token)
        handler.download(
            repo_id=args.repo,
            format_type=hf_format,
            split=args.split,
            revision=args.revision,
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


def cmd_upload(args):
    """Upload a segmentation dataset to HuggingFace Hub or Roboflow."""
    if args.target == "huggingface":
        from nectar.ai.segmentation.datasets.upload import HuggingFaceSegDatasetUploader

        uploader = HuggingFaceSegDatasetUploader(
            repo_id=args.repo,
            token=args.token,
            private=not args.public,
        )

        if not uploader.ensure_repo_exists():
            logger.error("Failed to create/access repository: %s", args.repo)
            sys.exit(1)

        if args.raw:
            uploader.upload_dataset(
                dataset_path=args.dataset,
                commit_message=args.message,
                ignore_patterns=args.ignore,
            )
        else:
            card_metadata = {}
            if args.title:
                card_metadata["title"] = args.title
            if args.description:
                card_metadata["description"] = args.description
            if args.license:
                card_metadata["license"] = args.license
            if args.tag:
                card_metadata["tags"] = args.tag
            if args.model_repo:
                card_metadata["model_repo"] = args.model_repo

            result = uploader.upload_native(
                dataset_path=args.dataset,
                source_format=args.annotation_format,
                commit_message=args.message,
                card_metadata=card_metadata or None,
            )
            logger.info(
                "Pushed splits %s with classes %s",
                result["splits"],
                result["class_names"],
            )
        logger.info("Dataset uploaded to: https://huggingface.co/datasets/%s", args.repo)
    elif args.target == "roboflow":
        from nectar.ai.detection.datasets.upload import RoboflowUploader

        if not args.api_key:
            logger.error("--api-key is required for Roboflow upload")
            sys.exit(1)

        uploader = RoboflowUploader(api_key=args.api_key, workspace=args.workspace)

        if args.images_only:
            uploader.upload_directory(
                directory_path=args.dataset,
                project_name=args.project,
                batch_name=args.batch_name,
                recursive=args.recursive,
                verbose=True,
                max_workers=args.max_workers,
            )
            logger.info("Images uploaded to Roboflow project: %s", args.project)
        else:
            uploader.upload_dataset(
                dataset_path=args.dataset,
                project_name=args.project,
                annotation_format=args.annotation_format,
                splits=args.splits,
                batch_name=args.batch_name,
                tag_names=args.tag,
                max_workers=args.max_workers,
                verbose=True,
            )
            logger.info("Dataset (images + annotations) uploaded to: %s", args.project)
    else:
        logger.error("Unknown upload target: %s", args.target)
        sys.exit(1)


def main():
    """Main entry point for segmentation dataset CLI."""
    parser = argparse.ArgumentParser(description="Segmentation dataset management")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # ---- download ----
    dl_parser = subparsers.add_parser("download", help="Download segmentation dataset")
    dl_parser.add_argument(
        "--source",
        required=True,
        help="Dataset source (ultralytics, roboflow, huggingface)",
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
    dl_parser.add_argument(
        "--repo", help="HuggingFace dataset repo (user/name) (for huggingface source)"
    )
    dl_parser.add_argument(
        "--token",
        help="HuggingFace API token (for huggingface source; falls back to HF_TOKEN)",
    )
    dl_parser.add_argument(
        "--split",
        help="Single split to load (for huggingface source: train/validation/test)",
    )
    dl_parser.add_argument("--revision", help="Git revision/branch/tag (for huggingface source)")

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

    # ---- upload ----
    up_parser = subparsers.add_parser(
        "upload", help="Upload segmentation dataset to HuggingFace Hub or Roboflow"
    )
    up_parser.add_argument(
        "--target",
        required=True,
        choices=["huggingface", "roboflow"],
        help="Upload target",
    )
    up_parser.add_argument("--dataset", required=True, help="Dataset directory to upload")
    up_parser.add_argument(
        "--repo", help="HuggingFace repository ID (user/repo, required for huggingface)"
    )
    up_parser.add_argument(
        "--message", default="Upload dataset", help="Commit message (for huggingface)"
    )
    up_parser.add_argument(
        "--token", help="HuggingFace API token (uses HF_TOKEN env var if not provided)"
    )
    up_parser.add_argument(
        "--public", action="store_true", help="Make repository public (for huggingface)"
    )
    up_parser.add_argument(
        "--ignore",
        nargs="*",
        help="Patterns to ignore (for huggingface --raw)",
    )
    up_parser.add_argument(
        "--raw",
        action="store_true",
        help="huggingface: upload files as-is instead of converting to native Parquet",
    )
    up_parser.add_argument("--title", help="Dataset card title (huggingface native)")
    up_parser.add_argument("--description", help="Dataset card description (huggingface native)")
    up_parser.add_argument(
        "--license",
        default=None,
        help="Dataset license tag (huggingface native, default apache-2.0)",
    )
    up_parser.add_argument(
        "--model-repo",
        help="Linked trained-model repo id (huggingface native dataset card)",
    )
    up_parser.add_argument("--api-key", help="Roboflow API key (required for roboflow)")
    up_parser.add_argument("--project", help="Roboflow project name (required for roboflow)")
    up_parser.add_argument("--workspace", help="Roboflow workspace (for roboflow)")
    up_parser.add_argument("--batch-name", help="Batch name (for roboflow)")
    up_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include subdirectories (for roboflow --images-only)",
    )
    up_parser.add_argument(
        "--max-workers", type=int, default=10, help="Parallel threads (for roboflow)"
    )
    up_parser.add_argument(
        "--images-only",
        action="store_true",
        help="roboflow: upload images without annotations",
    )
    up_parser.add_argument(
        "--annotation-format",
        choices=["coco", "yolo"],
        help="Override annotation format detection (default: auto-detect)",
    )
    up_parser.add_argument(
        "--splits",
        nargs="+",
        help="Limit upload to these splits (e.g. train valid test). Defaults to all available.",
    )
    up_parser.add_argument(
        "--tag",
        action="append",
        help="Tag to apply (repeatable). Roboflow image tag / HuggingFace dataset tag.",
    )

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
        "upload": cmd_upload,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
