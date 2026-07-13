"""CLI for evaluating classification models."""

import argparse
import logging
import sys

from nectar.ai.cli.common import add_common_eval_args


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate classification models")
    add_common_eval_args(parser)
    parser.add_argument("--topk", type=int, default=5, help="Top-k for metrics")
    parser.set_defaults(imgsz=224)
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    args = parse_args()

    from nectar.ai.classification.core.configs import ClsEvaluationConfig
    from nectar.ai.classification.evaluation.evaluator import ClassificationEvaluator
    from nectar.ai.classification.models.transformers import TransformersClsModel
    from nectar.ai.classification.models.ultralytics import UltralyticsClsModel

    logger.info("Loading %s model from %s", args.framework, args.model_path)

    if args.framework == "ultralytics":
        model = UltralyticsClsModel(args.model_path)
    elif args.framework == "transformers":
        model = TransformersClsModel(args.model_path)
    else:
        logger.error("Unsupported framework: %s (use ultralytics or transformers)", args.framework)
        sys.exit(1)

    model.load_model()

    config = ClsEvaluationConfig(
        model_path=args.model_path,
        dataset_path=args.dataset_path,
        framework=args.framework,
        output_dir=args.output_dir,
        dataset_type=args.dataset_type,
        split=args.split,
        device=args.device,
        batch_size=args.batch_size,
        num_samples=args.num_samples,
        imgsz=getattr(args, "imgsz", 224),
        topk=args.topk,
        prediction_samples_max=args.num_prediction_samples,
    )

    logger.info("Starting evaluation on %s split", args.split)
    metrics = ClassificationEvaluator(model, config).evaluate()

    logger.info("=" * 50)
    logger.info("Evaluation Results")
    logger.info("=" * 50)
    logger.info("Top-1:       %.4f", metrics.top1_accuracy)
    logger.info("Top-5:       %.4f", metrics.top5_accuracy)
    logger.info("P (macro):   %.4f", metrics.precision_macro)
    logger.info("R (macro):   %.4f", metrics.recall_macro)
    logger.info("F1 (macro):  %.4f", metrics.f1_macro)
    logger.info("Inference:   %.4fs/img", metrics.inference_time_per_image)
    logger.info("=" * 50)
    logger.info("Results saved to %s", args.output_dir)


if __name__ == "__main__":
    main()
