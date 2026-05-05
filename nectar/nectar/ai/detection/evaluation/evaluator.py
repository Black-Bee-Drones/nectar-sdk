"""Object detection evaluator"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
    from supervision.metrics.f1_score import F1Score
    from supervision.metrics.mean_average_precision import MeanAveragePrecision
    from supervision.metrics.mean_average_recall import MeanAverageRecall
    from supervision.metrics.precision import Precision
    from supervision.metrics.recall import Recall
except ImportError:
    sv = None

from tqdm import tqdm

from nectar.ai.detection.core.configs import EvaluationConfig, EvaluationMetrics
from nectar.ai.detection.core.types import DetectionInput
from nectar.ai.detection.evaluation.analysis import (
    compute_curves,
    create_error_statistics,
    process_evaluation_results,
    save_error_statistics_csv,
)
from nectar.ai.detection.evaluation.visualizations import (
    generate_evaluation_report,
    plot_confidence_curve,
    plot_confusion_matrix,
    plot_error_analysis,
    plot_metrics_summary,
    plot_performance_analysis,
    plot_pr_curve,
    plot_prediction_samples,
    save_per_class_metrics,
)
from nectar.ai.detection.models.dataset import load_detection_dataset

logger = logging.getLogger(__name__)

_RAW_CONF_THRESHOLD = 0.001


class ObjectDetectionEvaluator:
    """
    Evaluator for object detection models.

    Runs inference at a low confidence threshold to capture all predictions
    (like Ultralytics), then computes metrics at the user-specified threshold.

    Parameters
    ----------
    model : Any
        Detection model implementing predict() method.
    config : EvaluationConfig
        Evaluation configuration.
    """

    def __init__(self, model: Any, config: EvaluationConfig):
        self.model = model
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._filter_strategy = None

        if config.device != "auto":
            self.device = config.device
        elif torch and torch.cuda.is_available():
            self.device = "cuda"
        elif torch and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

    def set_post_processor(self, filter_strategy=None):
        """Attach a post-processing filter applied at the user's operating point.

        Currently supports `nectar.ai.detection.postprocess.PerClassConfidenceFilter`.
        When set, it replaces the single ``conf_threshold`` filter for P/R/F1
        reporting and for the prediction sample plot. mAP curves still use raw
        predictions.
        """
        self._filter_strategy = filter_strategy

    def evaluate(self) -> EvaluationMetrics:
        if sv is None:
            raise ImportError("supervision is required for evaluation")

        dataset = load_detection_dataset(
            self.config.dataset_path, self.config.dataset_type, self.config.split
        )

        all_paths, all_images, all_gts = [], [], []
        for path, image, gt in dataset:
            all_paths.append(path)
            all_images.append(image)
            all_gts.append(gt)

        if self.config.num_samples and self.config.num_samples < len(all_images):
            all_paths = all_paths[: self.config.num_samples]
            all_images = all_images[: self.config.num_samples]
            all_gts = all_gts[: self.config.num_samples]

        logger.info("Evaluating on %d images", len(all_images))

        # Run inference at low conf threshold to capture all predictions
        all_preds, all_times, raw_results = self._run_inference(all_images, all_paths, all_gts)

        # Save raw results (with all detections)
        with open(self.output_dir / "evaluation_results.json", "w", encoding="utf-8") as f:
            json.dump(raw_results, f, indent=2)

        # Filter predictions at user's conf_threshold for supervision metrics
        if self._filter_strategy is not None:
            filtered_preds = [self._filter_strategy.filter(p) for p in all_preds]
        else:
            filtered_preds = self._filter_by_confidence(all_preds, self.config.conf_threshold)

        # Compute supervision metrics on filtered predictions
        metrics_dict, per_class_metrics = self._compute_metrics(
            filtered_preds, all_gts, dataset.classes
        )

        avg_time = sum(all_times) / len(all_times) if all_times else 0
        metrics_dict["inference_time_per_image"] = avg_time
        metrics_dict["total_detections"] = sum(len(p) for p in filtered_preds)

        # Save overall metrics
        pd.DataFrame([metrics_dict]).to_csv(self.output_dir / "evaluation_metrics.csv", index=False)
        with open(self.output_dir / "metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2)

        save_per_class_metrics(per_class_metrics, self.output_dir)
        self._log_per_class_table(per_class_metrics)

        # Compute per-class curves from raw (unfiltered) predictions
        names = {i: n for i, n in enumerate(dataset.classes)}
        num_classes = len(dataset.classes)

        visualizations = {}

        try:
            px, py_p, py_r, py_f1, ap_curve = compute_curves(
                all_preds, all_gts, num_classes, self.config.iou_threshold
            )

            path = plot_pr_curve(px, py_p, ap_curve, names, self.output_dir)
            visualizations["PR_curve"] = path

            path = plot_confidence_curve(
                px, py_p, names, self.output_dir, "Precision", "P_curve.png"
            )
            visualizations["P_curve"] = path

            path = plot_confidence_curve(px, py_r, names, self.output_dir, "Recall", "R_curve.png")
            visualizations["R_curve"] = path

            path = plot_confidence_curve(px, py_f1, names, self.output_dir, "F1", "F1_curve.png")
            visualizations["F1_curve"] = path
        except Exception as e:
            logger.error("Failed to generate curve plots: %s", e)

        try:
            path = plot_metrics_summary(metrics_dict, self.output_dir)
            visualizations["results"] = path
        except Exception as e:
            logger.error("Failed to generate metrics summary: %s", e)

        try:
            cm = sv.ConfusionMatrix.from_detections(
                predictions=all_preds,
                targets=all_gts,
                classes=dataset.classes,
                conf_threshold=self.config.conf_threshold,
                iou_threshold=self.config.iou_threshold,
            )
            path = plot_confusion_matrix(cm, self.output_dir, dataset.classes)
            visualizations["confusion_matrix"] = path
        except Exception as e:
            logger.error("Failed to generate confusion matrix: %s", e)

        try:
            cm_matrix, fps, fns = create_error_statistics(
                self.output_dir,
                dataset.classes,
                self.config.iou_threshold,
                self.config.conf_threshold,
            )
            path = plot_error_analysis(cm_matrix, fps, fns, dataset.classes, self.output_dir)
            visualizations["error_analysis"] = path
            save_error_statistics_csv(self.output_dir, dataset.classes, fps, fns)
        except Exception as e:
            logger.error("Failed to generate error analysis: %s", e)

        try:
            pr_curves = process_evaluation_results(self.output_dir, dataset.classes)
            if pr_curves:
                rows = []
                for cid, data in pr_curves.items():
                    name = dataset.classes[cid] if cid < len(dataset.classes) else f"class_{cid}"
                    rows.append(
                        {
                            "class_id": cid,
                            "class_name": name,
                            "total_gt": data["total_gt"],
                            "total_predictions": data["total_predictions"],
                            "ap": data["ap"],
                            "optimal_threshold": data["optimal_threshold"],
                            "optimal_f1": data["optimal_f1"],
                            "optimal_precision": data.get("optimal_precision", 0),
                            "optimal_recall": data.get("optimal_recall", 0),
                        }
                    )
                pd.DataFrame(rows).sort_values("ap", ascending=False).to_csv(
                    self.output_dir / "pr_analysis_results.csv", index=False
                )
        except Exception as e:
            logger.error("Failed to generate PR analysis CSV: %s", e)

        try:
            df = pd.DataFrame(per_class_metrics)
            path = plot_performance_analysis(df, self.output_dir)
            if path:
                visualizations["performance_analysis"] = path
        except Exception as e:
            logger.error("Failed to generate performance analysis: %s", e)

        try:
            path = plot_prediction_samples(
                all_images,
                filtered_preds,
                all_gts,
                all_paths,
                dataset.classes,
                self.output_dir,
                max_samples=self.config.prediction_samples_max,
            )
            if path:
                visualizations["prediction_samples"] = path
        except Exception as e:
            logger.error("Failed to generate prediction samples: %s", e)

        try:
            config_dict = {
                "model_path": self.config.model_path,
                "dataset_path": self.config.dataset_path,
                "framework": self.config.framework,
                "split": self.config.split,
                "conf_threshold": self.config.conf_threshold,
                "iou_threshold": self.config.iou_threshold,
                "device": self.config.device,
                "batch_size": self.config.batch_size,
                "class_names": dataset.classes,
            }
            generate_evaluation_report(metrics_dict, config_dict, self.output_dir, raw_results)
        except Exception as e:
            logger.error("Failed to generate evaluation report: %s", e)

        logger.info("mAP@50: %.4f", metrics_dict["map50"])
        logger.info("mAP@50-95: %.4f", metrics_dict["map50_95"])
        logger.info("Precision: %.4f", metrics_dict["precision"])
        logger.info("Recall: %.4f", metrics_dict["recall"])
        logger.info("F1: %.4f", metrics_dict["f1_score"])

        return EvaluationMetrics(
            map50=metrics_dict["map50"],
            map50_95=metrics_dict["map50_95"],
            mar50=metrics_dict.get("mar_100", 0),
            mar50_95=metrics_dict.get("mar_10", 0),
            precision=metrics_dict["precision"],
            recall=metrics_dict["recall"],
            f1_score=metrics_dict["f1_score"],
            inference_time_per_image=avg_time,
            total_detections=metrics_dict["total_detections"],
            visualizations=visualizations,
        )

    def _run_inference(self, images, paths, gts):
        preds = []
        times = []
        results = []

        for i in tqdm(range(0, len(images), self.config.batch_size), desc="Evaluating"):
            batch_imgs = images[i : i + self.config.batch_size]
            batch_paths = paths[i : i + self.config.batch_size]
            batch_gts = gts[i : i + self.config.batch_size]

            # Pass file paths to inference. Each model wrapper loads with the
            # correct color order itself (cv2/BGR for Ultralytics, PIL/RGB for
            # transformers/rfdetr); passing the RGB np.ndarray we hold for
            # plotting silently feeds RGB to BGR-expecting models.
            detection_input = DetectionInput(
                image=batch_paths,
                conf_threshold=_RAW_CONF_THRESHOLD,
                iou_threshold=self.config.iou_threshold,
                device=self.device,
                imgsz=self.config.imgsz,
            )

            start = time.time()
            prediction = self.model.predict(detection_input)
            elapsed = time.time() - start

            batch_preds = prediction.batch_detections or [prediction.detections]
            preds.extend(batch_preds)

            per_image_time = elapsed / len(batch_paths)
            for _ in batch_paths:
                times.append(per_image_time)

            for pred, gt, path in zip(batch_preds, batch_gts, batch_paths):
                results.append(
                    {
                        "image_path": str(path),
                        "ground_truth": self._detections_to_list(gt),
                        "predictions": self._detections_to_list(pred),
                        "inference_time": per_image_time,
                    }
                )

        return preds, times, results

    @staticmethod
    def _filter_by_confidence(preds, conf_threshold):
        filtered = []
        for pred in preds:
            if pred.confidence is not None and len(pred) > 0:
                mask = pred.confidence >= conf_threshold
                filtered.append(pred[mask])
            else:
                filtered.append(pred)
        return filtered

    def _compute_metrics(self, preds, gts, classes):
        map_metric = MeanAveragePrecision()
        map_metric.update(predictions=preds, targets=gts)
        map_result = map_metric.compute()

        mar_metric = MeanAverageRecall()
        mar_metric.update(predictions=preds, targets=gts)
        mar_result = mar_metric.compute()

        precision_metric = Precision()
        recall_metric = Recall()
        f1_metric = F1Score()
        precision_metric.update(predictions=preds, targets=gts)
        recall_metric.update(predictions=preds, targets=gts)
        f1_metric.update(predictions=preds, targets=gts)
        precision_result = precision_metric.compute()
        recall_result = recall_metric.compute()
        f1_result = f1_metric.compute()

        for name, result in [
            ("map_metrics", map_result),
            ("mar_metrics", mar_result),
            ("precision_metrics", precision_result),
            ("recall_metrics", recall_result),
            ("f1_metrics", f1_result),
        ]:
            try:
                result.to_pandas().to_csv(self.output_dir / f"{name}.csv", index=False)
            except Exception:
                pass

        metrics_dict = {
            "map50": float(map_result.map50),
            "map50_95": float(map_result.map50_95),
            "mar_100": float(mar_result.mAR_at_100),
            "mar_10": float(mar_result.mAR_at_10),
            "mar_1": float(mar_result.mAR_at_1),
            "precision": float(precision_result.precision_at_50),
            "recall": float(recall_result.recall_at_50),
            "f1_score": float(f1_result.f1_50),
        }

        num_classes = len(classes)

        def _extract(arr, n, iou_idx=0):
            if arr is None or arr.size == 0:
                return np.zeros(n)
            if arr.ndim == 2:
                arr = arr[:, min(iou_idx, arr.shape[1] - 1)]
            out = np.zeros(n)
            copy_len = min(len(arr), n)
            out[:copy_len] = arr[:copy_len]
            return out

        ap50 = _extract(map_result.ap_per_class, num_classes)
        if map_result.ap_per_class is not None and map_result.ap_per_class.ndim == 2:
            ap50_95_raw = np.mean(map_result.ap_per_class, axis=1)
            ap50_95 = np.zeros(num_classes)
            ap50_95[: min(len(ap50_95_raw), num_classes)] = ap50_95_raw[:num_classes]
        else:
            ap50_95 = ap50.copy()

        prec_pc = _extract(precision_result.precision_per_class, num_classes)
        rec_pc = _extract(recall_result.recall_per_class, num_classes)
        f1_pc = _extract(f1_result.f1_per_class, num_classes)

        per_class = []
        for i, cls_name in enumerate(classes):
            per_class.append(
                {
                    "class_id": i,
                    "class_name": cls_name,
                    "ap50": float(ap50[i]),
                    "ap50_95": float(ap50_95[i]),
                    "precision": float(prec_pc[i]),
                    "recall": float(rec_pc[i]),
                    "f1_score": float(f1_pc[i]),
                }
            )

        return metrics_dict, per_class

    def _log_per_class_table(self, per_class_metrics):
        logger.info("Per-class metrics:")
        logger.info(
            "%-20s %8s %10s %12s %10s %8s",
            "Class",
            "AP@50",
            "AP@50-95",
            "Precision@50",
            "Recall@50",
            "F1@50",
        )
        for m in per_class_metrics:
            logger.info(
                "%-20s %8.3f %10.3f %12.3f %10.3f %8.3f",
                m["class_name"],
                m["ap50"],
                m["ap50_95"],
                m["precision"],
                m["recall"],
                m["f1_score"],
            )

    @staticmethod
    def _detections_to_list(detections: "sv.Detections") -> List[Dict]:
        result = []
        for i in range(len(detections)):
            d = {
                "box": detections.xyxy[i].tolist(),
                "label": (int(detections.class_id[i]) if detections.class_id is not None else 0),
            }
            if detections.confidence is not None:
                d["confidence"] = float(detections.confidence[i])
            result.append(d)
        return result
