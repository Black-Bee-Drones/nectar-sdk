"""Classification model evaluator."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from tqdm import tqdm

from nectar.ai.classification.core.configs import ClsEvaluationConfig, ClsEvaluationMetrics
from nectar.ai.classification.core.types import ClassificationInput
from nectar.ai.classification.evaluation.visualizations import (
    generate_evaluation_report,
    plot_confusion_matrix,
    plot_per_class_bars,
    plot_prediction_samples,
    save_per_class_metrics,
)
from nectar.ai.classification.models.dataset import load_classification_dataset

logger = logging.getLogger(__name__)


def _topk_accuracy(probs: np.ndarray, labels: np.ndarray, k: int = 5) -> float:
    if len(labels) == 0:
        return 0.0
    k = min(k, probs.shape[1])
    topk = np.argsort(probs, axis=1)[:, -k:]
    correct = np.any(topk == labels.reshape(-1, 1), axis=1)
    return float(correct.mean())


def _confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < n_classes and 0 <= p < n_classes:
            cm[t, p] += 1
    return cm


def _precision_recall_f1(cm: np.ndarray, average: str = "macro"):
    n = cm.shape[0]
    precisions, recalls, f1s, supports = [], [], [], []
    for i in range(n):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        support = cm[i, :].sum()
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        supports.append(support)

    supports_arr = np.asarray(supports, dtype=np.float64)
    if average == "weighted" and supports_arr.sum() > 0:
        w = supports_arr / supports_arr.sum()
        return float(np.dot(precisions, w)), float(np.dot(recalls, w)), float(np.dot(f1s, w))
    return float(np.mean(precisions)), float(np.mean(recalls)), float(np.mean(f1s))


class ClassificationEvaluator:
    """
    Evaluator for classification models.

    Computes top-1/top-5 accuracy, precision/recall/F1, confusion matrix,
    and writes evaluation artifacts.
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

        # Prefer model class names when available
        model_names = getattr(self.model, "class_names", None) or {}
        if model_names:
            # Align folder class names to model ids when names match
            name_to_model_id = {v: k for k, v in model_names.items()}
            remapped = []
            for folder_id, path in zip(labels, image_paths):
                folder_name = class_names[folder_id]
                remapped.append(name_to_model_id.get(folder_name, folder_id))
            labels = remapped
            class_names = {int(k): v for k, v in model_names.items()}

        n_classes = max(len(class_names), (max(labels) + 1) if labels else 1)
        all_probs: List[np.ndarray] = []
        all_preds: List[int] = []
        samples: List[Dict] = []
        total_time = 0.0

        for path, true_label in tqdm(list(zip(image_paths, labels)), desc="Evaluating", unit="img"):
            cls_input = ClassificationInput(
                image=path,
                device=self.config.device,
                topk=max(self.config.topk, 5),
                imgsz=self.config.imgsz,
            )
            start = time.time()
            prediction = self.model.predict(cls_input)
            total_time += time.time() - start

            result = prediction.result or (prediction.results[0] if prediction.results else None)
            if result is None or result.probs is None:
                probs = np.zeros(n_classes, dtype=np.float32)
                pred_id = -1
                conf = 0.0
                pred_name = ""
            else:
                probs = np.asarray(result.probs, dtype=np.float32).ravel()
                if probs.shape[0] < n_classes:
                    padded = np.zeros(n_classes, dtype=np.float32)
                    padded[: probs.shape[0]] = probs
                    probs = padded
                pred_id = int(np.argmax(probs))
                conf = float(probs[pred_id])
                pred_name = class_names.get(pred_id, f"class_{pred_id}")

            all_probs.append(probs[:n_classes])
            all_preds.append(pred_id)
            if len(samples) < self.config.prediction_samples_max:
                samples.append(
                    {
                        "image_path": path,
                        "true_id": int(true_label),
                        "true_name": class_names.get(int(true_label), str(true_label)),
                        "pred_id": pred_id,
                        "pred_name": pred_name,
                        "confidence": conf,
                    }
                )

        y_true = np.asarray(labels, dtype=np.int64)
        y_pred = np.asarray(all_preds, dtype=np.int64)
        probs_matrix = np.stack(all_probs) if all_probs else np.zeros((0, n_classes))

        top1 = float((y_pred == y_true).mean()) if len(y_true) else 0.0
        top5 = _topk_accuracy(probs_matrix, y_true, k=5)
        cm = _confusion_matrix(y_true, y_pred, n_classes)
        p_macro, r_macro, f1_macro = _precision_recall_f1(cm, average="macro")
        p_w, r_w, f1_w = _precision_recall_f1(cm, average="weighted")

        per_class = []
        for i in range(n_classes):
            tp = cm[i, i]
            fp = cm[:, i].sum() - tp
            fn = cm[i, :].sum() - tp
            support = int(cm[i, :].sum())
            precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
            recall = float(tp / (tp + fn)) if (tp + fn) else 0.0
            f1 = (
                float(2 * precision * recall / (precision + recall))
                if (precision + recall)
                else 0.0
            )
            per_class.append(
                {
                    "class_id": i,
                    "class_name": class_names.get(i, f"class_{i}"),
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "support": support,
                }
            )

        visualizations: Dict[str, str] = {}
        cm_path = str(self.output_dir / "confusion_matrix.png")
        visualizations["confusion_matrix"] = plot_confusion_matrix(cm, class_names, cm_path)
        visualizations["per_class_f1"] = plot_per_class_bars(
            per_class, str(self.output_dir / "per_class_f1.png"), metric="f1"
        )
        sample_path = plot_prediction_samples(
            samples,
            str(self.output_dir / "prediction_samples.png"),
            max_samples=self.config.prediction_samples_max,
        )
        if sample_path:
            visualizations["prediction_samples"] = sample_path

        pc_paths = save_per_class_metrics(per_class, str(self.output_dir))
        visualizations.update(pc_paths)

        metrics = ClsEvaluationMetrics(
            top1_accuracy=top1,
            top5_accuracy=top5,
            precision_macro=p_macro,
            recall_macro=r_macro,
            f1_macro=f1_macro,
            precision_weighted=p_w,
            recall_weighted=r_w,
            f1_weighted=f1_w,
            inference_time_per_image=total_time / max(len(image_paths), 1),
            total_samples=len(image_paths),
            per_class_metrics=per_class,
            visualizations=visualizations,
        )

        metrics.save_json(str(self.output_dir / "metrics.json"))
        generate_evaluation_report(metrics.to_dict(), str(self.output_dir / "report.md"))

        with open(self.output_dir / "raw_predictions.json", "w", encoding="utf-8") as f:
            json.dump(samples, f, indent=2)

        np.save(self.output_dir / "confusion_matrix.npy", cm)
        self.logger.info("Evaluation complete: %s", metrics.summary())
        return metrics
