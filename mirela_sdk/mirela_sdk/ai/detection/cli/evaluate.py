"""CLI for evaluating detection models."""

import argparse
import logging
import sys


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate object detection models")

    parser.add_argument("--model-path", type=str, required=True, help="Model path")
    parser.add_argument(
        "--framework",
        type=str,
        required=True,
        choices=["ultralytics", "transformers", "rfdetr"],
        help="Framework",
    )
    parser.add_argument("--dataset-path", type=str, required=True, help="Dataset path")
    parser.add_argument(
        "--output-dir", type=str, default="outputs/evaluation", help="Output directory"
    )
    parser.add_argument(
        "--dataset-type", type=str, default="auto", choices=["coco", "yolo", "auto"]
    )
    parser.add_argument("--split", type=str, default="test", help="Dataset split")
    parser.add_argument("--conf-threshold", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou-threshold", type=float, default=0.5, help="IoU threshold")
    parser.add_argument("--device", type=str, default="auto", help="Device")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--num-samples", type=int, help="Number of samples to evaluate")
    parser.add_argument("--rfdetr-size", type=str, help="RF-DETR model size")
    parser.add_argument("--resolution", type=int, help="Resolution for RF-DETR")

    # Slicing options
    parser.add_argument("--use-slicing", action="store_true", help="Enable slicing inference")
    parser.add_argument(
        "--slicing-strategy",
        type=str,
        default="grid",
        choices=["grid", "adaptive", "clustering", "none"],
    )
    parser.add_argument("--slice-size", type=int, nargs=2, default=[640, 640])
    parser.add_argument("--slice-overlap", type=float, default=0.2)
    parser.add_argument("--max-slices", type=int, default=16)

    return parser.parse_args()


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = parse_args()

    # Import model classes
    from mirela_sdk.ai.detection.core.configs import EvaluationConfig
    from mirela_sdk.ai.detection.evaluation.evaluator import ObjectDetectionEvaluator
    from mirela_sdk.ai.detection.models.rfdetr import RFDETRModel
    from mirela_sdk.ai.detection.models.transformers import TransformersModel
    from mirela_sdk.ai.detection.models.ultralytics import UltralyticsModel

    logger.info(f"Loading {args.framework} model from {args.model_path}")

    if args.framework == "ultralytics":
        model = UltralyticsModel(args.model_path)
    elif args.framework == "transformers":
        model = TransformersModel(args.model_path)
    elif args.framework == "rfdetr":
        model = RFDETRModel(
            args.model_path,
            rfdetr_size=args.rfdetr_size,
            resolution=args.resolution,
        )
        model.update_class_names_from_dataset(args.dataset_path)
    else:
        logger.error(f"Unsupported framework: {args.framework}")
        sys.exit(1)

    model.load_model()

    # Configure slicing if enabled
    if args.use_slicing:
        from mirela_sdk.ai.detection.slicing import SlicingConfig, SlicingStrategy

        slicing_config = SlicingConfig(
            strategy=SlicingStrategy(args.slicing_strategy),
            slice_size=tuple(args.slice_size),
            overlap_ratio=args.slice_overlap,
            iou_threshold=args.iou_threshold,
            conf_threshold=args.conf_threshold,
            max_slices=args.max_slices,
        )
        model.enable_slicing(slicing_config)
        logger.info(f"Slicing enabled: {args.slicing_strategy}")

    # Create evaluation config
    config = EvaluationConfig(
        model_path=args.model_path,
        dataset_path=args.dataset_path,
        framework=args.framework,
        output_dir=args.output_dir,
        dataset_type=args.dataset_type,
        split=args.split,
        conf_threshold=args.conf_threshold,
        iou_threshold=args.iou_threshold,
        device=args.device,
        batch_size=args.batch_size,
        num_samples=args.num_samples,
    )

    # Run evaluation
    logger.info(f"Starting evaluation on {args.split} split")
    logger.info(f"Dataset: {args.dataset_path}")
    logger.info(f"Output: {args.output_dir}")

    evaluator = ObjectDetectionEvaluator(model, config)
    metrics = evaluator.evaluate()

    # Print results
    logger.info("=" * 50)
    logger.info("Evaluation Results")
    logger.info("=" * 50)
    logger.info(f"mAP@50:      {metrics.map50:.4f}")
    logger.info(f"mAP@50-95:   {metrics.map50_95:.4f}")
    logger.info(f"mAR@50:      {metrics.mar50:.4f}")
    logger.info(f"mAR@50-95:   {metrics.mar50_95:.4f}")
    logger.info(f"Precision:   {metrics.precision:.4f}")
    logger.info(f"Recall:      {metrics.recall:.4f}")
    logger.info(f"F1-score:    {metrics.f1_score:.4f}")
    logger.info(f"Inference:   {metrics.inference_time_per_image:.4f}s/img")
    logger.info("=" * 50)
    logger.info(f"Results saved to {args.output_dir}")


if __name__ == "__main__":
    main()
