"""CLI for training segmentation models."""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from nectar.ai.cli.common import (
    add_common_train_args,
    add_rfdetr_args,
    add_ultralytics_args,
    collect_common_train_params,
    detect_framework,
    load_config,
    merge_config_with_args,
    resolve_paths,
)


def parse_args():
    """Parse command line arguments for segmentation training."""
    parser = argparse.ArgumentParser(description="Train segmentation models")
    add_common_train_args(parser)
    return parser.parse_args()


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = parse_args()

    config = {}
    if args.config:
        logger.info("Loading config: %s", args.config)
        config = load_config(args.config)

    params = merge_config_with_args(config, args)

    model = params.get("model")
    dataset = params.get("dataset_path")

    if not model:
        logger.error("Model is required (--model or config train.model)")
        sys.exit(1)
    if not dataset:
        logger.error("Dataset is required (--dataset or config data.dataset_path)")
        sys.exit(1)

    dataset, output_dir_raw = resolve_paths(dataset, params.get("output_dir", "outputs"))

    framework = params.get("framework") or detect_framework(model, task="segmentation")
    logger.info("Framework: %s", framework)

    from nectar.ai.core.utils.callbacks import HF_SYNC_IGNORE_PATTERNS
    from nectar.ai.core.utils.tensorboard import TensorBoardManager
    from nectar.ai.segmentation import Segmentor
    from nectar.ai.segmentation.core.configs import SegEvaluationConfig
    from nectar.ai.segmentation.evaluation.evaluator import SegmentationEvaluator
    from nectar.ai.segmentation.training.config import (
        RFDETRSegTrainingConfig,
        TransformersSegTrainingConfig,
        UltralyticsSegTrainingConfig,
    )

    common_args = collect_common_train_params(params, dataset, output_dir_raw)

    if framework == "ultralytics":
        add_ultralytics_args(common_args, params)
        training_config = UltralyticsSegTrainingConfig(model=model, **common_args)
    elif framework == "transformers":
        training_config = TransformersSegTrainingConfig(model=model, **common_args)
    elif framework == "rfdetr":
        add_rfdetr_args(common_args, params)
        training_config = RFDETRSegTrainingConfig(model=model, **common_args)
    else:
        logger.error("Unsupported framework: %s", framework)
        sys.exit(1)

    output_path = Path(output_dir_raw)
    output_path.mkdir(parents=True, exist_ok=True)
    config_save_path = output_path / "experiment.config.yaml"
    training_config.to_yaml(str(config_save_path))

    run_name = output_path.name

    logger.info("Model: %s", model)
    logger.info("Dataset: %s", dataset)
    logger.info("Output: %s", output_dir_raw)

    tb_manager = TensorBoardManager()
    start_tb = params.get("start_tensorboard")
    if start_tb is None:
        start_tb = bool(params.get("tensorboard"))
    if params.get("tensorboard") and start_tb:
        tb_manager.start_server(log_dir=output_dir_raw, port=params.get("tensorboard_port", 6006))

    segmentor = Segmentor(model, framework=framework, device=params.get("device", "auto"))
    segmentor.load()

    logger.info("Starting training...")
    training_start_time = time.time()

    eval_metrics: Optional[Any] = None
    eval_time: Optional[float] = None

    try:
        result = segmentor.train(training_config)
        training_time = time.time() - training_start_time
        logger.info("Training completed in %.2f seconds", training_time)
        logger.info("Model saved: %s", result.get("model_path", "N/A"))

        if params.get("evaluate"):
            eval_start = time.time()
            eval_split = params.get("eval_split", "test")
            eval_output = str(Path(output_dir_raw) / "evaluation")

            eval_dataset = dataset
            if Path(eval_dataset).suffix in (".yaml", ".yml"):
                eval_dataset = str(Path(eval_dataset).parent)

            eval_config = SegEvaluationConfig(
                model_path=result["model_path"],
                dataset_path=eval_dataset,
                framework=framework,
                output_dir=eval_output,
                split=eval_split,
                conf_threshold=params.get("conf_threshold", 0.25),
                iou_threshold=params.get("iou_threshold", 0.5),
                device=params.get("device", "auto"),
                batch_size=params.get("batch_size", 1),
                imgsz=params.get("imgsz"),
            )

            evaluator = SegmentationEvaluator(segmentor.model, eval_config)
            eval_metrics = evaluator.evaluate()
            eval_time = time.time() - eval_start

            logger.info("mAP@50: %.4f", eval_metrics.map50)
            logger.info("mIoU: %.4f", eval_metrics.mean_iou)
            logger.info("Evaluation completed in %.2f seconds", eval_time)

            if params.get("push_to_hub") and params.get("hub_model_id"):
                logger.info("Uploading evaluation results to HuggingFace Hub...")
                try:
                    from nectar.ai.core.utils.huggingface import HuggingFaceUploader

                    eval_uploader = HuggingFaceUploader(
                        repo_id=params["hub_model_id"],
                        local_dir=eval_output,
                        repo_type="model",
                    )
                    eval_uploader.upload(
                        commit_message="Add evaluation results",
                        path_in_repo="evaluation",
                        ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                    )
                except Exception as e:
                    logger.error("Failed to upload evaluation results: %s", e)

        run_info = {
            "run_name": run_name,
            "timestamp": datetime.now().isoformat(),
            "task": "segmentation",
            "framework": framework,
            "model": model,
            "dataset_path": dataset,
            "config": training_config.to_dict(),
            "training": {
                "model_path": result.get("model_path", "N/A"),
                "training_time_seconds": training_time,
                "metrics": result.get("metrics", {}),
            },
        }
        if eval_metrics:
            run_info["evaluation"] = {
                "metrics": eval_metrics.to_dict(),
                "evaluation_time_seconds": eval_time,
            }

        run_info_path = output_path / f"{run_name}_run_info.json"
        with open(run_info_path, "w", encoding="utf-8") as f:
            json.dump(run_info, f, indent=2, default=str)

        if params.get("push_to_hub") and params.get("hub_model_id"):
            try:
                from nectar.ai.core.utils.huggingface import HuggingFaceUploader

                logger.info("Uploading to HuggingFace Hub: %s", params["hub_model_id"])
                uploader = HuggingFaceUploader(
                    repo_id=params["hub_model_id"],
                    local_dir=output_dir_raw,
                )
                uploader.upload(
                    commit_message="Upload complete training results",
                    ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                )
                logger.info("Successfully uploaded to %s", params["hub_model_id"])
            except Exception as e:
                logger.error("Failed to upload training outputs: %s", e)

    except Exception as e:
        logger.error("Training failed: %s", e)
        raise
    finally:
        tb_manager.stop_server()


if __name__ == "__main__":
    main()
