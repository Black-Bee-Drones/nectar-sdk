"""CLI for evaluating detection models."""

import argparse
import logging
import sys

from nectar.ai.cli.common import add_common_eval_args, parse_conf_per_class


def parse_args():
    """Parse command line arguments for detection evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate object detection models")
    add_common_eval_args(parser)

    # Detection-specific slicing options
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

    from nectar.ai.detection.core.configs import EvaluationConfig
    from nectar.ai.detection.evaluation.evaluator import ObjectDetectionEvaluator
    from nectar.ai.detection.models.rfdetr import RFDETRModel
    from nectar.ai.detection.models.transformers import TransformersModel
    from nectar.ai.detection.models.ultralytics import UltralyticsModel

    logger.info("Loading %s model from %s", args.framework, args.model_path)

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
        logger.error("Unsupported framework: %s", args.framework)
        sys.exit(1)

    model.load_model()

    if args.use_slicing:
        from nectar.ai.detection.slicing import SlicingConfig, SlicingStrategy

        slicing_config = SlicingConfig(
            strategy=SlicingStrategy(args.slicing_strategy),
            slice_size=tuple(args.slice_size),
            overlap_ratio=args.slice_overlap,
            iou_threshold=args.iou_threshold,
            conf_threshold=args.conf_threshold,
            max_slices=args.max_slices,
        )
        model.enable_slicing(slicing_config)
        logger.info("Slicing enabled: %s", args.slicing_strategy)

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
        prediction_samples_max=args.num_prediction_samples,
    )

    logger.info("Starting evaluation on %s split", args.split)
    logger.info("Dataset: %s", args.dataset_path)
    logger.info("Output: %s", args.output_dir)

    evaluator = ObjectDetectionEvaluator(model, config)

    if args.conf_per_class:
        from nectar.ai.detection.postprocess import PerClassConfidenceFilter

        mapping = parse_conf_per_class(args.conf_per_class, model.class_names)
        evaluator.set_post_processor(
            filter_strategy=PerClassConfidenceFilter(
                threshold_mapping=mapping, default_threshold=args.conf_threshold
            )
        )
        logger.info("Per-class confidence thresholds: %s", mapping)

    metrics = evaluator.evaluate()

    logger.info("=" * 50)
    logger.info("Evaluation Results")
    logger.info("=" * 50)
    logger.info("mAP@50:      %.4f", metrics.map50)
    logger.info("mAP@50-95:   %.4f", metrics.map50_95)
    logger.info("mAR@50:      %.4f", metrics.mar50)
    logger.info("mAR@50-95:   %.4f", metrics.mar50_95)
    logger.info("Precision:   %.4f", metrics.precision)
    logger.info("Recall:      %.4f", metrics.recall)
    logger.info("F1-score:    %.4f", metrics.f1_score)
    logger.info("Inference:   %.4fs/img", metrics.inference_time_per_image)
    logger.info("=" * 50)
    logger.info("Results saved to %s", args.output_dir)


if __name__ == "__main__":
    main()
