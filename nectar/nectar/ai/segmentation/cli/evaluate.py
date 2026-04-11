"""CLI for evaluating segmentation models."""

import argparse
import logging
import sys

from nectar.ai.cli.common import add_common_eval_args


def parse_args():
    """Parse command line arguments for segmentation evaluation."""
    parser = argparse.ArgumentParser(description="Evaluate segmentation models")
    add_common_eval_args(parser)
    return parser.parse_args()


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = parse_args()

    from nectar.ai.segmentation.core.configs import SegEvaluationConfig
    from nectar.ai.segmentation.evaluation.evaluator import SegmentationEvaluator
    from nectar.ai.segmentation.models.rfdetr import RFDETRSegModel
    from nectar.ai.segmentation.models.transformers import TransformersSegModel
    from nectar.ai.segmentation.models.ultralytics import UltralyticsSegModel

    logger.info("Loading %s model from %s", args.framework, args.model_path)

    if args.framework == "ultralytics":
        model = UltralyticsSegModel(args.model_path)
    elif args.framework == "transformers":
        model = TransformersSegModel(args.model_path)
    elif args.framework == "rfdetr":
        model = RFDETRSegModel(
            args.model_path,
            rfdetr_size=args.rfdetr_size,
            resolution=args.resolution,
        )
        model.update_class_names_from_dataset(args.dataset_path)
    else:
        logger.error("Unsupported framework: %s", args.framework)
        sys.exit(1)

    model.load_model()

    config = SegEvaluationConfig(
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

    logger.info("Starting evaluation on %s split", args.split)
    logger.info("Dataset: %s", args.dataset_path)
    logger.info("Output: %s", args.output_dir)

    evaluator = SegmentationEvaluator(model, config)
    metrics = evaluator.evaluate()

    logger.info("=" * 50)
    logger.info("Evaluation Results")
    logger.info("=" * 50)
    logger.info("mAP@50:      %.4f", metrics.map50)
    logger.info("mAP@50-95:   %.4f", metrics.map50_95)
    logger.info("mIoU:        %.4f", metrics.mean_iou)
    logger.info("Precision:   %.4f", metrics.precision)
    logger.info("Recall:      %.4f", metrics.recall)
    logger.info("F1-score:    %.4f", metrics.f1_score)
    logger.info("Inference:   %.4fs/img", metrics.inference_time_per_image)
    logger.info("=" * 50)
    logger.info("Results saved to %s", args.output_dir)


if __name__ == "__main__":
    main()
