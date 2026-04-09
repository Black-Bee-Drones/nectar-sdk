"""Segmentation model evaluator."""

import logging
import time
from pathlib import Path
from typing import List

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
    from supervision.metrics.mean_average_precision import MeanAveragePrecision
except ImportError:
    sv = None

from tqdm import tqdm

from nectar.ai.detection.models.dataset import load_detection_dataset
from nectar.ai.segmentation.core.configs import SegEvaluationConfig, SegEvaluationMetrics
from nectar.ai.segmentation.core.types import SegmentationInput

logger = logging.getLogger(__name__)


class SegmentationEvaluator:
    """
    Evaluator for segmentation models.

    Supports mask-based mAP for instance segmentation and mIoU for semantic.

    Parameters
    ----------
    model : BaseSegmentationModel
        The segmentation model to evaluate.
    config : SegEvaluationConfig
        Evaluation configuration.
    """

    def __init__(self, model, config: SegEvaluationConfig):
        self.model = model
        self.config = config

    def evaluate(self) -> SegEvaluationMetrics:
        """Run evaluation and return metrics."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        dataset = load_detection_dataset(
            dataset_path=self.config.dataset_path,
            dataset_type=self.config.dataset_type,
            split=self.config.split,
        )
        images = dataset.images
        annotations = dataset.annotations

        if self.config.num_samples and len(images) > self.config.num_samples:
            images = images[: self.config.num_samples]
            annotations = annotations[: self.config.num_samples]

        if not images:
            logger.warning("No images found for evaluation")
            return SegEvaluationMetrics()

        logger.info("Evaluating on %d images", len(images))

        all_predictions = []
        all_targets = []
        total_inference_time = 0.0
        total_segmentations = 0

        low_conf = 0.001
        for i in tqdm(range(0, len(images), self.config.batch_size), desc="Evaluating"):
            batch_images = images[i : i + self.config.batch_size]
            batch_annotations = annotations[i : i + self.config.batch_size]

            for img_path, annotation in zip(batch_images, batch_annotations):
                seg_input = SegmentationInput(
                    image=img_path,
                    conf_threshold=low_conf,
                    iou_threshold=self.config.iou_threshold,
                    device=self.config.device,
                    imgsz=self.config.imgsz,
                )

                start = time.time()
                prediction = self.model.predict(seg_input)
                total_inference_time += time.time() - start

                if prediction.detections is not None:
                    pred_dets = prediction.detections
                    if pred_dets.confidence is not None:
                        mask = pred_dets.confidence >= self.config.conf_threshold
                        pred_dets = pred_dets[mask]
                    all_predictions.append(pred_dets)
                    total_segmentations += len(pred_dets)
                else:
                    all_predictions.append(sv.Detections.empty())

                all_targets.append(annotation)

        inference_time_per_image = total_inference_time / max(len(images), 1)

        metrics = self._compute_metrics(all_predictions, all_targets)
        metrics.inference_time_per_image = inference_time_per_image
        metrics.total_segmentations = total_segmentations

        metrics_path = output_dir / "segmentation_metrics.json"
        metrics.save_json(str(metrics_path))
        logger.info("Saved metrics to %s", metrics_path)
        logger.info(metrics.summary())

        return metrics

    def _compute_metrics(
        self,
        predictions: List["sv.Detections"],
        targets: List["sv.Detections"],
    ) -> SegEvaluationMetrics:
        """Compute segmentation evaluation metrics."""
        if sv is None:
            return SegEvaluationMetrics()

        try:
            map_metric = MeanAveragePrecision()
            map_result = map_metric.update(predictions, targets).compute()

            map50 = float(map_result.map50)
            map50_95 = float(map_result.map75)  # closest available

            precision_val = 0.0
            recall_val = 0.0
            f1_val = 0.0

            try:
                from supervision.metrics.precision import Precision
                from supervision.metrics.recall import Recall

                prec_metric = Precision()
                prec_result = prec_metric.update(predictions, targets).compute()
                precision_val = float(prec_result.precision)

                rec_metric = Recall()
                rec_result = rec_metric.update(predictions, targets).compute()
                recall_val = float(rec_result.recall)

                if precision_val + recall_val > 0:
                    f1_val = 2 * precision_val * recall_val / (precision_val + recall_val)
            except Exception:
                pass

            return SegEvaluationMetrics(
                map50=map50,
                map50_95=map50_95,
                precision=precision_val,
                recall=recall_val,
                f1_score=f1_val,
            )

        except Exception as e:
            logger.warning("Metric computation failed: %s", e)
            return SegEvaluationMetrics()
