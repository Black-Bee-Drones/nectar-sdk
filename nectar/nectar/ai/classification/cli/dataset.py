"""CLI for classification dataset management."""

import argparse
import logging
import sys
from pathlib import Path

from nectar.ai.classification.datasets.analyze import ClsDatasetAnalyzer
from nectar.ai.classification.datasets.format import (
    ClsFormatConverter,
    stratify_imagefolder,
    subset_imagefolder,
)
from nectar.ai.classification.datasets.handlers import ClsDatasetHandlerRegistry
from nectar.ai.paths import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)


def cmd_download(args):
    handler_name = args.source.lower()
    handler_class = ClsDatasetHandlerRegistry.get(handler_name)
    if not handler_class:
        logger.error("Unknown dataset source: %s", handler_name)
        logger.info("Available: %s", ClsDatasetHandlerRegistry.list_handlers())
        sys.exit(1)

    output_dir = Path(args.output).resolve()
    default_data_dir = Path(DEFAULT_DATA_DIR).resolve()
    if output_dir == default_data_dir:
        dataset_id = getattr(args, "dataset", None)
        if not dataset_id and handler_name in ("huggingface", "hf") and args.repo:
            dataset_id = args.repo.split("/")[-1]
        output_dir = output_dir / (dataset_id or handler_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    if handler_name == "ultralytics":
        dataset_name = args.dataset or "mnist160"
        handler = handler_class(str(output_dir))
        path = handler.download_and_convert(
            dataset=dataset_name,
            max_samples=args.max_samples,
        )
        logger.info("Dataset ready at: %s", path)
    elif handler_name == "roboflow":
        if not args.api_key:
            logger.error("--api-key is required for roboflow source")
            sys.exit(1)
        handler = handler_class(str(output_dir), args.api_key)
        path = handler.download(
            workspace=args.workspace,
            project=args.project,
            version=args.version,
            format_type=args.roboflow_format or "folder",
        )
        logger.info("Dataset ready at: %s", path)
    elif handler_name in ("huggingface", "hf"):
        if not args.repo:
            logger.error("--repo is required for huggingface source")
            sys.exit(1)
        handler = handler_class(str(output_dir), token=args.token)
        path = handler.download(
            repo_id=args.repo,
            format_type="imagefolder",
            split=args.split,
            max_samples=args.max_samples,
        )
        logger.info("Dataset ready at: %s", path)
    else:
        logger.error("Handler %s not supported", handler_name)
        sys.exit(1)


def cmd_subset(args):
    result = subset_imagefolder(
        args.input,
        args.output,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        max_test_samples=args.max_test_samples,
        seed=args.seed,
    )
    logger.info("Subset saved to: %s", result)


def cmd_stratify(args):
    result = stratify_imagefolder(
        args.input,
        args.output,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    logger.info("Stratified dataset saved to: %s", result)


def cmd_convert(args):
    converter = ClsFormatConverter(args.input, args.output, verbose=True)
    path = converter.normalize_split_names()
    logger.info("Normalized ImageFolder written to: %s", path)


def cmd_analyze(args):
    analyzer = ClsDatasetAnalyzer(args.input, output_dir=args.output)
    analyzer.analyze()
    logger.info("Analysis complete. Results in: %s", args.output or f"{args.input}/analysis")


def cmd_upload(args):
    if args.target == "huggingface":
        from nectar.ai.classification.datasets.upload import HuggingFaceClsDatasetUploader

        uploader = HuggingFaceClsDatasetUploader(
            repo_id=args.repo,
            token=args.token,
            private=not args.public,
        )
        card_metadata = {}
        if args.title:
            card_metadata["title"] = args.title
        if args.description:
            card_metadata["description"] = args.description
        if args.license:
            card_metadata["license"] = args.license
        if args.tag:
            card_metadata["tags"] = args.tag

        result = uploader.upload_native(
            dataset_path=args.dataset,
            commit_message=args.message,
            card_metadata=card_metadata or None,
        )
        logger.info("Uploaded splits %s classes %s", result["splits"], result["class_names"])
        logger.info("https://huggingface.co/datasets/%s", args.repo)
    elif args.target == "roboflow":
        from nectar.ai.classification.datasets.upload import RoboflowClsUploader

        if not args.api_key:
            logger.error("--api-key is required for Roboflow upload")
            sys.exit(1)
        uploader = RoboflowClsUploader(api_key=args.api_key)
        stats = uploader.upload_dataset(
            dataset_path=args.dataset,
            project_name=args.project,
            workspace=args.workspace,
            splits=args.splits,
        )
        logger.info("Upload stats: %s", stats)
    else:
        logger.error("Unknown upload target: %s", args.target)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classification dataset management")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dl = sub.add_parser("download", help="Download a dataset")
    p_dl.add_argument("--source", required=True, help="ultralytics | huggingface | roboflow")
    p_dl.add_argument("--output", default=str(DEFAULT_DATA_DIR), help="Output directory")
    p_dl.add_argument("--dataset", help="Ultralytics dataset name (e.g. mnist160)")
    p_dl.add_argument("--repo", help="HuggingFace dataset repo id")
    p_dl.add_argument("--token", help="HuggingFace token")
    p_dl.add_argument("--split", help="Optional HF split to download")
    p_dl.add_argument("--max-samples", type=int, help="Limit samples per split (HF)")
    p_dl.add_argument("--api-key", help="Roboflow API key")
    p_dl.add_argument("--workspace", help="Roboflow workspace")
    p_dl.add_argument("--project", help="Roboflow project")
    p_dl.add_argument("--version", type=int, default=1, help="Roboflow version")
    p_dl.add_argument("--roboflow-format", default="folder", help="Roboflow download format")
    p_dl.set_defaults(func=cmd_download)

    p_sub = sub.add_parser("subset", help="Create a balanced subset")
    p_sub.add_argument("--input", required=True)
    p_sub.add_argument("--output", required=True)
    p_sub.add_argument("--max-train-samples", type=int)
    p_sub.add_argument("--max-eval-samples", type=int)
    p_sub.add_argument("--max-test-samples", type=int)
    p_sub.add_argument("--seed", type=int, default=42)
    p_sub.set_defaults(func=cmd_subset)

    p_str = sub.add_parser("stratify", help="Split unsplit ImageFolder into train/val/test")
    p_str.add_argument("--input", required=True)
    p_str.add_argument("--output", required=True)
    p_str.add_argument("--train-ratio", type=float, default=0.8)
    p_str.add_argument("--val-ratio", type=float, default=0.2)
    p_str.add_argument("--test-ratio", type=float, default=0.0)
    p_str.add_argument("--seed", type=int, default=42)
    p_str.set_defaults(func=cmd_stratify)

    p_cv = sub.add_parser(
        "convert",
        help="Normalize ImageFolder split names (valid/validation → val)",
    )
    p_cv.add_argument("--input", required=True)
    p_cv.add_argument("--output", required=True)
    p_cv.set_defaults(func=cmd_convert)

    p_an = sub.add_parser("analyze", help="Analyze class distribution")
    p_an.add_argument("--input", required=True)
    p_an.add_argument("--output", help="Analysis output directory")
    p_an.set_defaults(func=cmd_analyze)

    p_up = sub.add_parser("upload", help="Upload dataset to HF or Roboflow")
    p_up.add_argument("--target", required=True, choices=["huggingface", "roboflow"])
    p_up.add_argument("--dataset", required=True, help="Local ImageFolder path")
    p_up.add_argument("--repo", help="HF dataset repo id")
    p_up.add_argument("--token", help="HF token")
    p_up.add_argument("--public", action="store_true")
    p_up.add_argument("--message", default="Upload classification dataset")
    p_up.add_argument("--title")
    p_up.add_argument("--description")
    p_up.add_argument("--license", default="apache-2.0")
    p_up.add_argument("--tag", nargs="*", dest="tag")
    p_up.add_argument("--api-key", help="Roboflow API key")
    p_up.add_argument("--workspace")
    p_up.add_argument("--project")
    p_up.add_argument("--splits", nargs="*", default=["train", "val", "test"])
    p_up.set_defaults(func=cmd_upload)

    return parser


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
