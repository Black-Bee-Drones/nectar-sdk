"""Classification model evaluator."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm

from nectar.ai.classification.core.configs import ClsEvaluationConfig, ClsEvaluationMetrics
from nectar.ai.classification.core.types import ClassificationInput
from nectar.ai.classification.evaluation import analysis as cls_analysis
from nectar.ai.classification.evaluation.visualizations import (
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
from nectar.ai.classification.models.dataset import load_classification_dataset

logger = logging.getLogger(__name__)


class ClassificationEvaluator:
    """
    Evaluator for classification models.

    curves, confusion matrix, error/performance analysis, JSON/CSV reports.
    """

    def __init__(self, model: Any, config: ClsEvaluationConfig):
        self.model = model
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(self.__class__.__name__)

    def evaluate(self) -> ClsEvaluationMetrics:
        image_paths, labels, class_names = load_classification_dataset(
            self.config.dataset_path,
            split=self.config.split,
            num_samples=self.config.num_samples,
        )

        model_names = getattr(self.model, "class_names", None) or {}
        if model_names:
            name_to_model_id = {v: k for k, v in model_names.items()}
            remapped = []
            for folder_id, path in zip(labels, image_paths):
                folder_name = class_names[folder_id]
                remapped.append(name_to_model_id.get(folder_name, folder_id))
            labels = remapped
            class_names = {int(k): v for k, v in model_names.items()}

        n_classes = max(len(class_names), (max(labels) + 1) if labels else 1)
        class_name_list = [class_names.get(i, f"class_{i}") for i in range(n_classes)]

        raw_results: List[Dict] = []
        all_probs: List[np.ndarray] = []
        sample_rows: List[Dict] = []
        total_time = 0.0

        self.logger.info("Evaluating on %d images", len(image_paths))
        for path, true_label in tqdm(list(zip(image_paths, labels)), desc="Evaluating", unit="img"):
            cls_input = ClassificationInput(
                image=path,
                device=self.config.device,
                topk=max(self.config.topk, 5),
                imgsz=self.config.imgsz,
            )
            start = time.time()
            prediction = self.model.predict(cls_input)
            elapsed = time.time() - start
            total_time += elapsed

            result = prediction.result or (prediction.results[0] if prediction.results else None)
            if result is None or result.probs is None:
                probs = np.zeros(n_classes, dtype=np.float32)
                pred_id = -1
                conf = 0.0
            else:
                probs = np.asarray(result.probs, dtype=np.float32).ravel()
                if probs.shape[0] < n_classes:
                    padded = np.zeros(n_classes, dtype=np.float32)
                    padded[: probs.shape[0]] = probs
                    probs = padded
                pred_id = int(np.argmax(probs[:n_classes]))
                conf = float(probs[pred_id])

            probs = probs[:n_classes]
            all_probs.append(probs)
            pred_name = class_names.get(pred_id, f"class_{pred_id}") if pred_id >= 0 else ""
            true_name = class_names.get(int(true_label), str(true_label))

            raw_results.append(
                {
                    "image_path": path,
                    "ground_truth": {"label": int(true_label), "class_name": true_name},
                    "predictions": {
                        "label": pred_id,
                        "class_name": pred_name,
                        "confidence": conf,
                    },
                    "probs": probs.tolist(),
                    "inference_time": elapsed,
                }
            )
            sample_rows.append(
                {
                    "image_path": path,
                    "true_id": int(true_label),
                    "true_name": true_name,
                    "pred_id": pred_id,
                    "pred_name": pred_name,
                    "confidence": conf,
                }
            )

        with open(self.output_dir / "evaluation_results.json", "w", encoding="utf-8") as f:
            json.dump(raw_results, f, indent=2)

        y_true = np.asarray(labels, dtype=np.int64)
        probs_matrix = np.stack(all_probs) if all_probs else np.zeros((0, n_classes))
        y_pred = cls_analysis.apply_confidence_threshold(
            y_true, probs_matrix, self.config.conf_threshold
        )

        for row, pred_id in zip(sample_rows, y_pred.tolist()):
            row["pred_id"] = int(pred_id)
            if pred_id < 0:
                row["pred_name"] = "abstain"
                row["confidence"] = 0.0
            else:
                row["pred_name"] = class_names.get(int(pred_id), f"class_{pred_id}")

        accepted = y_pred >= 0
        top1 = float(np.mean((y_pred == y_true) & accepted)) if len(y_true) else 0.0
        topk = cls_analysis.topk_accuracy(probs_matrix, y_true, k=self.config.topk)
        cm = cls_analysis.confusion_matrix(y_true, y_pred, n_classes)
        p_macro, r_macro, f1_macro = cls_analysis.precision_recall_f1(cm, average="macro")
        p_w, r_w, f1_w = cls_analysis.precision_recall_f1(cm, average="weighted")
        per_class = cls_analysis.per_class_metrics_from_cm(cm, class_names)

        metrics_dict = {
            "top1_accuracy": top1,
            "top5_accuracy": topk,
            "topk": self.config.topk,
            "precision_macro": p_macro,
            "recall_macro": r_macro,
            "f1_macro": f1_macro,
            "precision_weighted": p_w,
            "recall_weighted": r_w,
            "f1_weighted": f1_w,
            "inference_time_per_image": total_time / max(len(image_paths), 1),
            "total_samples": len(image_paths),
            "conf_threshold": self.config.conf_threshold,
        }

        with open(self.output_dir / "metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2)
        pd.DataFrame([metrics_dict]).to_csv(self.output_dir / "evaluation_metrics.csv", index=False)

        self._log_per_class_table(per_class)

        visualizations: Dict[str, str] = {}

        try:
            path = plot_confusion_matrix(
                cm, class_names, str(self.output_dir / "confusion_matrix.png"), normalize=False
            )
            visualizations["confusion_matrix"] = path
        except Exception as e:
            logger.error("Failed to generate confusion matrix: %s", e)

        try:
            px, py_p, py_r, py_f1 = cls_analysis.compute_confidence_curves(
                y_true, probs_matrix, n_classes=n_classes
            )
            names = {i: class_names.get(i, str(i)) for i in range(n_classes)}
            visualizations["P_curve"] = plot_confidence_curve(
                px, py_p, names, self.output_dir, ylabel="Precision", filename="P_curve.png"
            )
            visualizations["R_curve"] = plot_confidence_curve(
                px, py_r, names, self.output_dir, ylabel="Recall", filename="R_curve.png"
            )
            visualizations["F1_curve"] = plot_confidence_curve(
                px, py_f1, names, self.output_dir, ylabel="F1", filename="F1_curve.png"
            )
        except Exception as e:
            logger.error("Failed to generate confidence curves: %s", e)

        try:
            px, py, ap = cls_analysis.compute_pr_curves(y_true, probs_matrix, n_classes=n_classes)
            names = {i: class_names.get(i, str(i)) for i in range(n_classes)}
            visualizations["PR_curve"] = plot_pr_curve(px, py, ap, names, self.output_dir)
        except Exception as e:
            logger.error("Failed to generate PR curve: %s", e)

        try:
            cm_err, fps, fns = cls_analysis.create_error_statistics(y_true, y_pred, n_classes)
            visualizations["error_analysis"] = plot_error_analysis(
                cm_err, fps, fns, class_name_list, self.output_dir
            )
            cls_analysis.save_error_statistics_csv(self.output_dir, class_name_list, fps, fns)
        except Exception as e:
            logger.error("Failed to generate error analysis: %s", e)

        try:
            pr_analysis = cls_analysis.process_evaluation_results(self.output_dir, class_name_list)
            if pr_analysis:
                rows = []
                for cid, data in pr_analysis.items():
                    rows.append(
                        {
                            "class_id": cid,
                            "class_name": class_name_list[cid]
                            if cid < len(class_name_list)
                            else f"class_{cid}",
                            "total_gt": data["total_gt"],
                            "total_predictions": data["total_predictions"],
                            "ap": data["ap"],
                            "optimal_threshold": data["optimal_threshold"],
                            "optimal_f1": data["optimal_f1"],
                            "optimal_precision": data["optimal_precision"],
                            "optimal_recall": data["optimal_recall"],
                        }
                    )
                pd.DataFrame(rows).sort_values("ap", ascending=False).to_csv(
                    self.output_dir / "pr_analysis_results.csv", index=False
                )
        except Exception as e:
            logger.error("Failed to generate PR analysis CSV: %s", e)

        try:
            path = plot_performance_analysis(per_class, self.output_dir)
            if path:
                visualizations["performance_analysis"] = path
        except Exception as e:
            logger.error("Failed to generate performance analysis: %s", e)

        try:
            visualizations["results"] = plot_metrics_summary(metrics_dict, self.output_dir)
        except Exception as e:
            logger.error("Failed to generate metrics summary plot: %s", e)

        try:
            sample_path = plot_prediction_samples(
                sample_rows,
                str(self.output_dir / "prediction_samples.png"),
                max_samples=self.config.prediction_samples_max,
            )
            if sample_path:
                visualizations["prediction_samples"] = sample_path
        except Exception as e:
            logger.error("Failed to generate prediction samples: %s", e)

        try:
            csv_path, json_path = save_per_class_metrics(per_class, self.output_dir)
            visualizations["per_class_metrics_csv"] = csv_path
            visualizations["per_class_metrics_json"] = json_path
        except Exception as e:
            logger.error("Failed to save per-class metrics: %s", e)

        try:
            config_dict = {
                "model_path": self.config.model_path,
                "dataset_path": self.config.dataset_path,
                "framework": self.config.framework,
                "split": self.config.split,
                "conf_threshold": self.config.conf_threshold,
                "topk": self.config.topk,
                "device": self.config.device,
                "batch_size": self.config.batch_size,
                "class_names": class_name_list,
            }
            generate_evaluation_report(metrics_dict, config_dict, self.output_dir)
        except Exception as e:
            logger.error("Failed to generate evaluation report: %s", e)

        metrics = ClsEvaluationMetrics(
            top1_accuracy=top1,
            top5_accuracy=topk,
            precision_macro=p_macro,
            recall_macro=r_macro,
            f1_macro=f1_macro,
            precision_weighted=p_w,
            recall_weighted=r_w,
            f1_weighted=f1_w,
            inference_time_per_image=metrics_dict["inference_time_per_image"],
            total_samples=len(image_paths),
            per_class_metrics=per_class,
            visualizations=visualizations,
        )
        metrics.save_json(str(self.output_dir / "metrics.json"))

        self.logger.info("Top-1: %.4f", top1)
        self.logger.info("Top-%d: %.4f", self.config.topk, topk)
        self.logger.info("Precision (macro): %.4f", p_macro)
        self.logger.info("Recall (macro): %.4f", r_macro)
        self.logger.info("F1 (macro): %.4f", f1_macro)
        self.logger.info("Evaluation complete: %s", metrics.summary())
        return metrics

    def _log_per_class_table(self, per_class: List[Dict]) -> None:
        self.logger.info("Per-class metrics:")
        self.logger.info(
            "%-20s %8s %8s %8s %8s",
            "Class",
            "P",
            "R",
            "F1",
            "Support",
        )
        for row in per_class:
            self.logger.info(
                "%-20s %8.3f %8.3f %8.3f %8d",
                str(row.get("class_name", ""))[:20],
                row.get("precision", 0.0),
                row.get("recall", 0.0),
                row.get("f1_score", 0.0),
                row.get("support", 0),
            )
