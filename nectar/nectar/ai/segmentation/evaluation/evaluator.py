"""Segmentation model evaluator.

Follows the same flow as the detection evaluator:
1. Load ground truth with masks via ``load_segmentation_dataset``
2. Run inference at a low confidence threshold to capture all predictions
3. Save raw results JSON
4. Filter at user-specified confidence threshold
5. Compute metrics (torchmetrics for mAP, supervision for P/R/F1/mAR)
6. Generate Box and Mask evaluation visualizations
"""

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
    from supervision.metrics.core import MetricTarget
    from supervision.metrics.f1_score import F1Score
    from supervision.metrics.mean_average_recall import MeanAverageRecall
    from supervision.metrics.precision import Precision
    from supervision.metrics.recall import Recall
except ImportError:
    sv = None

try:
    from torchmetrics.detection.mean_ap import MeanAveragePrecision as TorchMeanAP
except ImportError:
    TorchMeanAP = None

from tqdm import tqdm

from nectar.ai.segmentation.core.configs import SegEvaluationConfig, SegEvaluationMetrics
from nectar.ai.segmentation.core.types import SegmentationInput
from nectar.ai.segmentation.evaluation.analysis import (
    compute_curves,
    create_error_statistics,
    process_evaluation_results,
    save_error_statistics_csv,
)
from nectar.ai.segmentation.evaluation.visualizations import (
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
from nectar.ai.segmentation.models.dataset import load_segmentation_dataset

logger = logging.getLogger(__name__)

_RAW_CONF_THRESHOLD = 0.001


class SegmentationEvaluator:
    """
    Evaluator for segmentation models.

    Runs inference at a low confidence threshold (like Ultralytics), then
    computes metrics at the user-specified threshold and generates rich
    evaluation visualizations.

    Parameters
    ----------
    model : Any
        Segmentation model implementing ``predict(SegmentationInput)``.
    config : SegEvaluationConfig
        Evaluation configuration.
    """

    def __init__(self, model: Any, config: SegEvaluationConfig):
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

        Currently supports `nectar.ai.detection.postprocess.PerClassConfidenceFilter`
        (the same instance type used by the detection evaluator). When set, it
        replaces the single ``conf_threshold`` filter for P/R/F1 reporting and
        for the prediction sample plot. mAP curves still use raw predictions.
        """
        self._filter_strategy = filter_strategy

    def evaluate(self) -> SegEvaluationMetrics:
        if sv is None:
            raise ImportError("supervision is required for evaluation")

        dataset = load_segmentation_dataset(
            self.config.dataset_path,
            self.config.dataset_type,
            self.config.split,
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

        all_preds, all_times, raw_results = self._run_inference(
            all_images,
            all_paths,
            all_gts,
        )

        with open(self.output_dir / "evaluation_results.json", "w", encoding="utf-8") as f:
            json.dump(raw_results, f, indent=2)

        if self._filter_strategy is not None:
            filtered_preds = [self._filter_strategy.filter(p) for p in all_preds]
        else:
            filtered_preds = self._filter_by_confidence(all_preds, self.config.conf_threshold)

        metrics_dict, per_class_metrics = self._compute_metrics(
            filtered_preds,
            all_gts,
            dataset.classes,
        )

        avg_time = sum(all_times) / len(all_times) if all_times else 0
        metrics_dict["inference_time_per_image"] = avg_time
        metrics_dict["total_detections"] = sum(len(p) for p in filtered_preds)

        pd.DataFrame([metrics_dict]).to_csv(
            self.output_dir / "evaluation_metrics.csv",
            index=False,
        )
        with open(self.output_dir / "metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2)

        save_per_class_metrics(per_class_metrics, self.output_dir)
        self._log_per_class_table(per_class_metrics)

        names = {i: n for i, n in enumerate(dataset.classes)}
        num_classes = len(dataset.classes)

        visualizations: Dict[str, str] = {}

        has_masks = self._has_masks(all_preds) and self._has_masks(all_gts)
        curve_variants = [("Box", False)]
        if has_masks:
            curve_variants.append(("Mask", True))

        for prefix, use_masks in curve_variants:
            try:
                px, py_p, py_r, py_f1, ap_curve = compute_curves(
                    all_preds,
                    all_gts,
                    num_classes,
                    self.config.iou_threshold,
                    use_masks=use_masks,
                )
                visualizations[f"{prefix}PR_curve"] = plot_pr_curve(
                    px,
                    py_p,
                    ap_curve,
                    names,
                    self.output_dir,
                    title=f"{prefix} Precision-Recall Curve",
                    filename=f"{prefix}PR_curve.png",
                )
                for metric, data, fname in [
                    ("Precision", py_p, f"{prefix}P_curve.png"),
                    ("Recall", py_r, f"{prefix}R_curve.png"),
                    ("F1", py_f1, f"{prefix}F1_curve.png"),
                ]:
                    visualizations[f"{prefix}{metric[0]}_curve"] = plot_confidence_curve(
                        px,
                        data,
                        names,
                        self.output_dir,
                        metric,
                        fname,
                    )
            except Exception as e:
                logger.error("Failed to generate %s curve plots: %s", prefix, e)

        try:
            visualizations["results"] = plot_metrics_summary(metrics_dict, self.output_dir)
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
            visualizations["confusion_matrix"] = plot_confusion_matrix(
                cm,
                self.output_dir,
                dataset.classes,
            )
        except Exception as e:
            logger.error("Failed to generate confusion matrix: %s", e)

        try:
            cm_matrix, fps, fns = create_error_statistics(
                self.output_dir,
                dataset.classes,
                self.config.iou_threshold,
                self.config.conf_threshold,
            )
            visualizations["error_analysis"] = plot_error_analysis(
                cm_matrix,
                fps,
                fns,
                dataset.classes,
                self.output_dir,
            )
            save_error_statistics_csv(self.output_dir, dataset.classes, fps, fns)
        except Exception as e:
            logger.error("Failed to generate error analysis: %s", e)

        try:
            pr_curves = process_evaluation_results(self.output_dir, dataset.classes)
            if pr_curves:
                rows = []
                for cid, data in pr_curves.items():
                    cname = dataset.classes[cid] if cid < len(dataset.classes) else f"class_{cid}"
                    rows.append(
                        {
                            "class_id": cid,
                            "class_name": cname,
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
                    self.output_dir / "pr_analysis_results.csv",
                    index=False,
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

        return SegEvaluationMetrics(
            map50=metrics_dict["map50"],
            map50_95=metrics_dict["map50_95"],
            mar50=metrics_dict.get("mar_100", 0),
            mar50_95=metrics_dict.get("mar_10", 0),
            precision=metrics_dict["precision"],
            recall=metrics_dict["recall"],
            f1_score=metrics_dict["f1_score"],
            mean_iou=metrics_dict.get("mean_iou", 0.0),
            inference_time_per_image=avg_time,
            total_segmentations=metrics_dict["total_detections"],
            visualizations=visualizations,
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_inference(self, images, paths, gts):
        preds: list = []
        times: list = []
        results: list = []

        for i in tqdm(range(len(images)), desc="Evaluating"):
            img_path = paths[i]
            gt = gts[i]

            # Pass file path to inference. The model wrapper loads with the
            # correct color order itself (cv2/BGR for Ultralytics); passing the
            # RGB np.ndarray we hold for plotting silently feeds RGB to a
            # BGR-expecting model and predictions land in the wrong place.
            seg_input = SegmentationInput(
                image=img_path,
                conf_threshold=_RAW_CONF_THRESHOLD,
                iou_threshold=self.config.iou_threshold,
                device=self.device,
                imgsz=self.config.imgsz,
            )

            start = time.time()
            prediction = self.model.predict(seg_input)
            elapsed = time.time() - start

            pred_dets = (
                prediction.detections
                if prediction.detections is not None
                else sv.Detections.empty()
            )
            preds.append(pred_dets)
            times.append(elapsed)

            results.append(
                {
                    "image_path": str(img_path),
                    "ground_truth": self._detections_to_list(gt),
                    "predictions": self._detections_to_list(pred_dets),
                    "inference_time": elapsed,
                }
            )

        return preds, times, results

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

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

    @staticmethod
    def _has_masks(detections_list):
        return any(d.mask is not None and len(d) > 0 for d in detections_list)

    @staticmethod
    def _compute_mean_iou(preds, gts):
        """Compute mean IoU between predicted and ground-truth masks."""
        ious = []
        for pred, gt in zip(preds, gts):
            if pred.mask is None or gt.mask is None or len(pred) == 0 or len(gt) == 0:
                continue
            for p_mask in pred.mask:
                best_iou = 0.0
                for g_mask in gt.mask:
                    intersection = np.logical_and(p_mask, g_mask).sum()
                    union = np.logical_or(p_mask, g_mask).sum()
                    if union > 0:
                        best_iou = max(best_iou, intersection / union)
                ious.append(best_iou)
        return float(np.mean(ious)) if ious else 0.0

    def _compute_metrics(self, preds, gts, classes):
        has_masks = self._has_masks(preds) and self._has_masks(gts)
        target = MetricTarget.MASKS if has_masks else MetricTarget.BOXES

        # -- mAP via torchmetrics (correctly supports iou_type="segm") ------
        mask_map_dict, box_map_dict = self._compute_map_torchmetrics(preds, gts, has_masks)

        # -- P / R / F1 / mAR via supervision (correctly branches on masks) -
        mar_metric = MeanAverageRecall(metric_target=target)
        mar_metric.update(predictions=preds, targets=gts)
        mar_result = mar_metric.compute()

        precision_metric = Precision(metric_target=target)
        recall_metric = Recall(metric_target=target)
        f1_metric = F1Score(metric_target=target)
        precision_metric.update(predictions=preds, targets=gts)
        recall_metric.update(predictions=preds, targets=gts)
        f1_metric.update(predictions=preds, targets=gts)
        precision_result = precision_metric.compute()
        recall_result = recall_metric.compute()
        f1_result = f1_metric.compute()

        for name, result in [
            ("mar_metrics", mar_result),
            ("precision_metrics", precision_result),
            ("recall_metrics", recall_result),
            ("f1_metrics", f1_result),
        ]:
            try:
                result.to_pandas().to_csv(self.output_dir / f"{name}.csv", index=False)
            except Exception:
                pass

        primary = mask_map_dict if has_masks else box_map_dict
        metrics_dict = {
            "map50": primary["map50"],
            "map50_95": primary["map50_95"],
            "mar_100": float(mar_result.mAR_at_100),
            "mar_10": float(mar_result.mAR_at_10),
            "mar_1": float(mar_result.mAR_at_1),
            "precision": float(precision_result.precision_at_50),
            "recall": float(recall_result.recall_at_50),
            "f1_score": float(f1_result.f1_50),
            "metric_target": target.value,
        }

        if has_masks:
            metrics_dict["box_map50"] = box_map_dict["map50"]
            metrics_dict["box_map50_95"] = box_map_dict["map50_95"]
            metrics_dict["mean_iou"] = self._compute_mean_iou(preds, gts)

        num_classes = len(classes)

        def _extract(arr, n):
            if arr is None or arr.size == 0:
                return np.zeros(n)
            if arr.ndim == 2:
                arr = arr[:, 0]
            out = np.zeros(n)
            copy_len = min(len(arr), n)
            out[:copy_len] = arr[:copy_len]
            return out

        prec_pc = _extract(precision_result.precision_per_class, num_classes)
        rec_pc = _extract(recall_result.recall_per_class, num_classes)
        f1_pc = _extract(f1_result.f1_per_class, num_classes)

        ap50_pc = primary.get("ap50_per_class", [])
        ap50_95_pc = primary.get("ap50_95_per_class", [])
        if not isinstance(ap50_pc, (list, np.ndarray)):
            ap50_pc = [ap50_pc]
        if not isinstance(ap50_95_pc, (list, np.ndarray)):
            ap50_95_pc = [ap50_95_pc]

        per_class = []
        for i, cls_name in enumerate(classes):
            per_class.append(
                {
                    "class_id": i,
                    "class_name": cls_name,
                    "ap50": float(ap50_pc[i]) if i < len(ap50_pc) else 0.0,
                    "ap50_95": float(ap50_95_pc[i]) if i < len(ap50_95_pc) else 0.0,
                    "precision": float(prec_pc[i]),
                    "recall": float(rec_pc[i]),
                    "f1_score": float(f1_pc[i]),
                }
            )

        return metrics_dict, per_class

    def _compute_map_torchmetrics(self, preds, gts, has_masks):
        """Compute mAP using torchmetrics for both box and mask IoU."""
        if TorchMeanAP is None:
            logger.warning("torchmetrics not available, falling back to zeros")
            empty = {"map50": 0.0, "map50_95": 0.0, "ap50_per_class": [], "ap50_95_per_class": []}
            return empty, empty

        tm_preds, tm_targets = self._sv_to_torchmetrics(preds, gts, has_masks)

        results = {}
        iou_types = ["segm", "bbox"] if has_masks else ["bbox"]
        for iou_type in iou_types:
            # class_metrics=True is required to populate map_per_class;
            # otherwise torchmetrics returns -1 for every class.
            metric = TorchMeanAP(iou_type=iou_type, class_metrics=True)
            metric.update(tm_preds, tm_targets)
            r = metric.compute()

            ap50_pc = r.get("map_per_class", torch.tensor([])).numpy()
            ap50_pc = np.where(ap50_pc < 0, 0.0, ap50_pc)

            results[iou_type] = {
                "map50": float(r["map_50"]),
                "map50_95": float(r["map"]),
                "ap50_per_class": ap50_pc.tolist() if ap50_pc.size else [],
                "ap50_95_per_class": ap50_pc.tolist() if ap50_pc.size else [],
            }

        mask_result = results.get("segm", results["bbox"])
        box_result = results["bbox"]
        return mask_result, box_result

    @staticmethod
    def _sv_to_torchmetrics(preds, gts, has_masks):
        """Convert sv.Detections lists to torchmetrics format."""
        tm_preds = []
        tm_targets = []

        for pred, gt in zip(preds, gts):
            p = {
                "boxes": torch.tensor(pred.xyxy, dtype=torch.float32)
                if len(pred) > 0
                else torch.zeros((0, 4), dtype=torch.float32),
                "scores": torch.tensor(pred.confidence, dtype=torch.float32)
                if pred.confidence is not None and len(pred) > 0
                else torch.zeros(0, dtype=torch.float32),
                "labels": torch.tensor(pred.class_id, dtype=torch.int64)
                if pred.class_id is not None and len(pred) > 0
                else torch.zeros(0, dtype=torch.int64),
            }
            t = {
                "boxes": torch.tensor(gt.xyxy, dtype=torch.float32)
                if len(gt) > 0
                else torch.zeros((0, 4), dtype=torch.float32),
                "labels": torch.tensor(gt.class_id, dtype=torch.int64)
                if gt.class_id is not None and len(gt) > 0
                else torch.zeros(0, dtype=torch.int64),
            }

            if has_masks:
                if pred.mask is not None and len(pred) > 0:
                    p["masks"] = torch.tensor(pred.mask, dtype=torch.bool)
                else:
                    h = gt.mask.shape[1] if gt.mask is not None and len(gt) > 0 else 1
                    w = gt.mask.shape[2] if gt.mask is not None and len(gt) > 0 else 1
                    p["masks"] = torch.zeros((0, h, w), dtype=torch.bool)

                if gt.mask is not None and len(gt) > 0:
                    t["masks"] = torch.tensor(gt.mask, dtype=torch.bool)
                else:
                    t["masks"] = torch.zeros((0, 1, 1), dtype=torch.bool)

            tm_preds.append(p)
            tm_targets.append(t)

        return tm_preds, tm_targets

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
            d: Dict[str, Any] = {
                "box": detections.xyxy[i].tolist(),
                "label": int(detections.class_id[i]) if detections.class_id is not None else 0,
            }
            if detections.confidence is not None:
                d["confidence"] = float(detections.confidence[i])
            result.append(d)
        return result
