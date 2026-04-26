"""CLI for dataset management operations."""

import argparse
import logging
import sys
from pathlib import Path

from nectar.ai.detection.datasets.analyze import DatasetAnalyzer
from nectar.ai.detection.datasets.augment import AugmentationBuilder
from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector
from nectar.ai.detection.datasets.handlers import DatasetHandlerRegistry
from nectar.ai.detection.datasets.merge import DatasetMerger
from nectar.ai.detection.datasets.stratify import Stratifier
from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.detection.datasets.upload import HuggingFaceDatasetUploader

logger = logging.getLogger(__name__)


def cmd_download(args):
    """Download dataset from a handler."""
    handler_name = args.source.lower()
    handler_class = DatasetHandlerRegistry.get(handler_name)

    if not handler_class:
        logger.error(f"Unknown dataset source: {handler_name}")
        logger.info(f"Available sources: {DatasetHandlerRegistry.list_handlers()}")
        sys.exit(1)

    from nectar.ai.detection.core.configs import DEFAULT_DATA_DIR

    output_dir = Path(args.output).resolve()
    default_data_dir = Path(DEFAULT_DATA_DIR).resolve()
    if output_dir == default_data_dir:
        output_dir = output_dir / handler_name

    output_dir.mkdir(parents=True, exist_ok=True)

    if handler_name == "visdrone":
        handler = handler_class(str(output_dir))
        handler.download_and_convert(
            output_format=args.format,
            splits=args.splits,
            download=True,
            threads=args.threads,
            num_workers=getattr(args, "num_workers", None),
        )
    elif handler_name == "roboflow":
        handler = handler_class(str(output_dir), args.api_key)
        handler.download(
            workspace=args.workspace,
            project=args.project,
            version=args.version,
            format_type=args.format,
        )
    elif handler_name in ("huggingface", "hf"):
        if not args.repo:
            logger.error("--repo is required for huggingface source (e.g. user/dataset)")
            sys.exit(1)
        hf_format = args.format if args.format in ("coco", "yolo") else "coco"
        handler = handler_class(str(output_dir), token=args.token)
        handler.download(
            repo_id=args.repo,
            format_type=hf_format,
            split=getattr(args, "split", None),
            revision=getattr(args, "revision", None),
        )
    else:
        logger.error(f"Handler {handler_name} not yet supported in CLI")
        sys.exit(1)


def cmd_convert(args):
    """Convert dataset format."""
    detector = FormatDetector(args.input)
    source_format = detector.detect()

    if source_format == "unknown":
        logger.error(f"Could not detect format in {args.input}")
        sys.exit(1)

    target_format = args.format.lower()
    if source_format == target_format:
        logger.info(f"Dataset already in {target_format} format")
        return

    converter = FormatConverter(args.input, args.output, num_workers=args.num_workers)
    converter.convert(
        target_format=target_format,
        copy_images=args.copy_images,
        num_workers=args.num_workers,
    )
    logger.info(f"Converted to {target_format} format: {args.output}")


def cmd_stratify(args):
    """Stratify dataset into train/val/test splits."""
    stratifier = Stratifier(args.input, args.output, seed=args.seed)
    result = stratifier.stratify(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        target_format=args.target_format,
    )
    logger.info(f"Stratified dataset saved to: {result}")


def cmd_subset(args):
    """Create balanced subset of dataset."""
    creator = SubsetCreator(args.input, args.output, seed=args.seed)
    result = creator.create(
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        max_test_samples=args.max_test_samples,
    )
    logger.info(f"Subset dataset saved to: {result}")


def cmd_augment(args):
    """Apply augmentations to a dataset, generating new augmented images."""
    if args.preset:
        builder = AugmentationBuilder(preset=args.preset)
    elif args.config:
        builder = AugmentationBuilder.from_yaml(args.config)
    else:
        builder = AugmentationBuilder(preset="conservative")

    if args.add_transform:
        for transform_spec in args.add_transform:
            parts = transform_spec.split(":", 1)
            if len(parts) != 2:
                logger.error(f"Invalid transform spec: {transform_spec}")
                sys.exit(1)
            name = parts[0]
            import json

            try:
                params = json.loads(parts[1])
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in transform params: {parts[1]}")
                sys.exit(1)
            builder.add_transform(name, params)

    if not args.input or not args.output:
        logger.error("--input and --output are required for augmentation")
        sys.exit(1)

    splits = [s.strip() for s in args.splits.split(",")] if args.splits else ["train"]
    result_path = builder.apply(
        args.input,
        args.output,
        args.num_augmented,
        splits,
        num_workers=args.num_workers,
        augmentation_ratio=args.augmentation_ratio,
        max_original_samples=args.max_original_samples,
        prioritize_rare_classes=args.prioritize_rare_classes,
        seed=args.seed,
    )
    logger.info("Augmented dataset saved to: %s", result_path)


def cmd_analyze(args):
    """Analyze dataset distribution."""
    analyzer = DatasetAnalyzer(args.input, output_dir=args.output)
    analyzer.analyze()
    logger.info(f"Analysis complete. Results saved to: {args.output}")


def cmd_merge(args):
    """Merge two datasets (YOLO or COCO format)."""
    import json

    merger = DatasetMerger(
        args.dataset1,
        args.dataset2,
        args.output,
        output_format=args.output_format,
        seed=args.seed,
    )

    split_config = {}
    if args.train_config:
        try:
            split_config["train"] = json.loads(args.train_config)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in --train-config: {args.train_config}")
            sys.exit(1)
    if args.val_config:
        try:
            split_config["valid"] = json.loads(args.val_config)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in --val-config: {args.val_config}")
            sys.exit(1)
    if args.test_config:
        try:
            split_config["test"] = json.loads(args.test_config)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in --test-config: {args.test_config}")
            sys.exit(1)

    if not split_config:
        logger.error(
            "At least one split configuration required (--train-config, --val-config, or --test-config)"
        )
        sys.exit(1)

    merger.merge(split_config, rename_files=not args.no_rename_files)
    logger.info(f"Merged dataset saved to: {args.output}")


def cmd_upload(args):
    """Upload dataset to HuggingFace Hub or Roboflow."""
    if args.target == "huggingface":
        uploader = HuggingFaceDatasetUploader(
            repo_id=args.repo,
            token=args.token,
            private=not args.public,
        )

        if not uploader.ensure_repo_exists():
            logger.error(f"Failed to create/access repository: {args.repo}")
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
        logger.info(f"Dataset uploaded to: https://huggingface.co/datasets/{args.repo}")
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
            logger.info(f"Images uploaded to Roboflow project: {args.project}")
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
            logger.info(f"Dataset (images + annotations) uploaded to: {args.project}")
    else:
        logger.error(f"Unknown upload target: {args.target}")
        sys.exit(1)


def cmd_upload_images(args):
    """Upload images to Roboflow for annotation."""
    from nectar.ai.detection.datasets.upload import RoboflowUploader

    uploader = RoboflowUploader(api_key=args.api_key, workspace=args.workspace)
    uploader.upload_directory(
        directory_path=args.directory,
        project_name=args.project,
        batch_name=args.batch_name,
        recursive=args.recursive,
        verbose=True,
        max_workers=args.max_workers,
    )
    logger.info(f"Images uploaded to Roboflow project: {args.project}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Dataset management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    download_parser = subparsers.add_parser("download", help="Download dataset")
    download_parser.add_argument(
        "--source",
        required=True,
        help="Dataset source (visdrone, roboflow, huggingface)",
    )
    from nectar.ai.detection.core.configs import DEFAULT_DATA_DIR

    download_parser.add_argument(
        "--output",
        default=str(DEFAULT_DATA_DIR),
        help=f"Output directory (default: {DEFAULT_DATA_DIR}/<source>)",
    )
    download_parser.add_argument(
        "--format",
        default="yolo",
        choices=["yolo", "coco", "both"],
        help="Output format",
    )
    download_parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val", "test"],
        help="Splits to download",
    )
    download_parser.add_argument("--threads", type=int, default=4, help="Download threads")
    download_parser.add_argument("--api-key", help="Roboflow API key (for roboflow source)")
    download_parser.add_argument("--workspace", help="Roboflow workspace (for roboflow source)")
    download_parser.add_argument("--project", help="Roboflow project (for roboflow source)")
    download_parser.add_argument(
        "--version", type=int, help="Roboflow version (for roboflow source)"
    )
    download_parser.add_argument(
        "--repo", help="HuggingFace dataset repo (user/name) (for huggingface source)"
    )
    download_parser.add_argument(
        "--token",
        help="HuggingFace API token (for huggingface source; falls back to HF_TOKEN)",
    )
    download_parser.add_argument(
        "--split",
        help="Single split to load (for huggingface source: train/validation/test)",
    )
    download_parser.add_argument(
        "--revision", help="Git revision/branch/tag (for huggingface source)"
    )
    download_parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Number of parallel workers for format conversion (default: min(CPU count, 8))",
    )

    convert_parser = subparsers.add_parser("convert", help="Convert dataset format")
    convert_parser.add_argument("--input", required=True, help="Input dataset directory")
    convert_parser.add_argument("--output", required=True, help="Output dataset directory")
    convert_parser.add_argument(
        "--format", required=True, choices=["coco", "yolo"], help="Target format"
    )
    convert_parser.add_argument(
        "--copy-images", action="store_true", default=True, help="Copy images"
    )
    convert_parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: min(CPU count, 8))",
    )

    stratify_parser = subparsers.add_parser("stratify", help="Stratify dataset into splits")
    stratify_parser.add_argument("--input", required=True, help="Input dataset directory")
    stratify_parser.add_argument("--output", required=True, help="Output directory")
    stratify_parser.add_argument("--train-ratio", type=float, default=0.8, help="Train split ratio")
    stratify_parser.add_argument(
        "--val-ratio", type=float, default=0.2, help="Validation split ratio"
    )
    stratify_parser.add_argument("--test-ratio", type=float, default=0.0, help="Test split ratio")
    stratify_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    stratify_parser.add_argument("--target-format", choices=["coco", "yolo"], help="Target format")

    subset_parser = subparsers.add_parser("subset", help="Create balanced subset")
    subset_parser.add_argument("--input", required=True, help="Input dataset directory")
    subset_parser.add_argument("--output", required=True, help="Output directory")
    subset_parser.add_argument("--max-train-samples", type=int, help="Max train samples")
    subset_parser.add_argument("--max-eval-samples", type=int, help="Max validation samples")
    subset_parser.add_argument("--max-test-samples", type=int, help="Max test samples")
    subset_parser.add_argument("--seed", type=int, default=42, help="Random seed")

    augment_parser = subparsers.add_parser("augment", help="Apply augmentations to dataset")
    augment_parser.add_argument("--input", required=True, help="Input dataset path")
    augment_parser.add_argument(
        "--output", required=True, help="Output directory for augmented dataset"
    )
    augment_parser.add_argument(
        "--num-augmented",
        type=int,
        default=2,
        help="Augmented copies per image (default: 2)",
    )
    augment_parser.add_argument(
        "--splits",
        default="train",
        help="Splits to augment, comma-separated (default: train)",
    )
    augment_parser.add_argument(
        "--preset",
        choices=["conservative", "aggressive", "aerial", "industrial"],
        help="Augmentation preset",
    )
    augment_parser.add_argument("--config", help="Load augmentation config from YAML")
    augment_parser.add_argument(
        "--add-transform", action="append", help="Add transform (name:json_params)"
    )
    augment_parser.add_argument(
        "--num-workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: min(32, cpu_count))",
    )
    augment_parser.add_argument(
        "--augmentation-ratio",
        type=float,
        default=None,
        help="Add augmented data as fraction of train size (e.g. 0.25 = 25%% extra). Overrides max-original-samples.",
    )
    augment_parser.add_argument(
        "--max-original-samples",
        type=int,
        default=None,
        help="Maximum number of original images to augment",
    )
    augment_parser.add_argument(
        "--prioritize-rare-classes",
        action="store_true",
        help="Prioritize images with rare categories when capping samples",
    )
    augment_parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )

    analyze_parser = subparsers.add_parser("analyze", help="Analyze dataset")
    analyze_parser.add_argument("--input", required=True, help="Input dataset directory")
    analyze_parser.add_argument("--output", help="Output directory (default: input/analysis)")

    merge_parser = subparsers.add_parser("merge", help="Merge two YOLO datasets")
    merge_parser.add_argument("--dataset1", required=True, help="First dataset path")
    merge_parser.add_argument("--dataset2", required=True, help="Second dataset path")
    merge_parser.add_argument("--output", required=True, help="Output directory")
    merge_parser.add_argument(
        "--output-format",
        choices=["yolo", "coco", "auto"],
        default="auto",
        help="Output format (auto uses format of first dataset)",
    )
    merge_parser.add_argument(
        "--train-config", help='Train split config (e.g., \'{"d1": 1000, "d2": 5000}\')'
    )
    merge_parser.add_argument("--val-config", help="Validation split config")
    merge_parser.add_argument("--test-config", help="Test split config")
    merge_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    merge_parser.add_argument(
        "--no-rename-files",
        action="store_true",
        help="Don't rename files with dataset prefix",
    )

    upload_parser = subparsers.add_parser(
        "upload", help="Upload dataset to HuggingFace Hub or Roboflow"
    )
    upload_parser.add_argument(
        "--target",
        required=True,
        choices=["huggingface", "roboflow"],
        help="Upload target",
    )
    upload_parser.add_argument("--dataset", required=True, help="Dataset directory to upload")

    upload_parser.add_argument(
        "--repo", help="HuggingFace repository ID (user/repo, required for huggingface)"
    )
    upload_parser.add_argument(
        "--message", default="Upload dataset", help="Commit message (for huggingface)"
    )
    upload_parser.add_argument(
        "--token", help="HuggingFace API token (uses HF_TOKEN env var if not provided)"
    )
    upload_parser.add_argument(
        "--public", action="store_true", help="Make repository public (for huggingface)"
    )
    upload_parser.add_argument(
        "--ignore",
        nargs="*",
        help="Patterns to ignore (e.g., '*.log', for huggingface --raw)",
    )
    upload_parser.add_argument(
        "--raw",
        action="store_true",
        help="huggingface: upload files as-is instead of converting to native Parquet",
    )
    upload_parser.add_argument("--title", help="Dataset card title (huggingface native)")
    upload_parser.add_argument(
        "--description", help="Dataset card description (huggingface native)"
    )
    upload_parser.add_argument(
        "--license",
        default=None,
        help="Dataset license tag (huggingface native, default apache-2.0)",
    )
    upload_parser.add_argument(
        "--model-repo",
        help="Linked trained-model repo id (huggingface native dataset card)",
    )

    upload_parser.add_argument("--api-key", help="Roboflow API key (required for roboflow)")
    upload_parser.add_argument("--project", help="Roboflow project name (required for roboflow)")
    upload_parser.add_argument("--workspace", help="Roboflow workspace (for roboflow)")
    upload_parser.add_argument("--batch-name", help="Batch name (for roboflow)")
    upload_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include subdirectories (for roboflow --images-only)",
    )
    upload_parser.add_argument(
        "--max-workers", type=int, default=10, help="Parallel threads (for roboflow)"
    )
    upload_parser.add_argument(
        "--images-only",
        action="store_true",
        help="roboflow: upload images without annotations (legacy behavior)",
    )
    upload_parser.add_argument(
        "--annotation-format",
        choices=["coco", "yolo"],
        help="Override annotation format detection (default: auto-detect)",
    )
    upload_parser.add_argument(
        "--splits",
        nargs="+",
        help="Limit upload to these splits (e.g. train valid test). Defaults to all available.",
    )
    upload_parser.add_argument(
        "--tag",
        action="append",
        help="Tag to apply (repeatable). Used as image tag for Roboflow and as dataset tag for HuggingFace.",
    )

    upload_images_parser = subparsers.add_parser(
        "upload-images", help="Upload images to Roboflow for annotation"
    )
    upload_images_parser.add_argument("--api-key", required=True, help="Roboflow API key")
    upload_images_parser.add_argument("--project", required=True, help="Roboflow project name")
    upload_images_parser.add_argument("--directory", required=True, help="Image directory")
    upload_images_parser.add_argument("--batch-name", help="Batch name")
    upload_images_parser.add_argument(
        "--recursive", action="store_true", help="Include subdirectories"
    )
    upload_images_parser.add_argument("--workspace", help="Workspace name")
    upload_images_parser.add_argument(
        "--max-workers", type=int, default=10, help="Parallel threads"
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
        "stratify": cmd_stratify,
        "subset": cmd_subset,
        "augment": cmd_augment,
        "analyze": cmd_analyze,
        "merge": cmd_merge,
        "upload": cmd_upload,
        "upload-images": cmd_upload_images,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
