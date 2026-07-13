"""Confidence/PR analysis and error statistics for classification evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


def topk_accuracy(probs: np.ndarray, labels: np.ndarray, k: int = 5) -> float:
    if len(labels) == 0:
        return 0.0
    k = min(k, probs.shape[1])
    topk = np.argsort(probs, axis=1)[:, -k:]
    correct = np.any(topk == labels.reshape(-1, 1), axis=1)
    return float(correct.mean())


def confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if p < 0:
            continue
        if 0 <= t < n_classes and 0 <= p < n_classes:
            cm[t, p] += 1
    return cm


def precision_recall_f1(
    cm: np.ndarray,
    average: str = "macro",
) -> Tuple[float, float, float]:
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


def apply_confidence_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
    conf_threshold: float = 0.0,
) -> np.ndarray:
    """Return predicted class ids; -1 means abstain (max prob below threshold)."""
    if len(y_true) == 0:
        return np.zeros(0, dtype=np.int64)
    pred_ids = np.argmax(probs, axis=1).astype(np.int64)
    confidences = probs[np.arange(len(probs)), pred_ids]
    pred_ids = pred_ids.copy()
    pred_ids[confidences < conf_threshold] = -1
    return pred_ids


def per_class_metrics_from_cm(
    cm: np.ndarray,
    class_names: Dict[int, str],
) -> List[Dict]:
    n_classes = cm.shape[0]
    rows = []
    for i in range(n_classes):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        support = int(cm[i, :].sum())
        precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) else 0.0
        f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        rows.append(
            {
                "class_id": i,
                "class_name": class_names.get(i, f"class_{i}"),
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": support,
            }
        )
    return rows


def _prf_at_threshold(
    y_true: np.ndarray,
    pred_ids: np.ndarray,
    confidences: np.ndarray,
    threshold: float,
    n_classes: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-class P/R/F1 when accepting predictions with conf >= threshold."""
    accepted = confidences >= threshold
    active_pred = np.where(accepted, pred_ids, -1)

    precision = np.zeros(n_classes, dtype=np.float64)
    recall = np.zeros(n_classes, dtype=np.float64)
    f1 = np.zeros(n_classes, dtype=np.float64)

    for cls in range(n_classes):
        support = int(np.sum(y_true == cls))
        tp = int(np.sum((y_true == cls) & (active_pred == cls)))
        fp = int(np.sum((y_true != cls) & (active_pred == cls)))
        p = tp / (tp + fp) if (tp + fp) else (1.0 if support == 0 else 0.0)
        r = tp / support if support else 0.0
        precision[cls] = p
        recall[cls] = r
        f1[cls] = 2 * p * r / (p + r) if (p + r) else 0.0

    return precision, recall, f1


def compute_confidence_curves(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_classes: Optional[int] = None,
    n_points: int = 1000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Sweep confidence thresholds for top-1 classification with abstention.

    Returns (px, py_precision, py_recall, py_f1) with py_* shape (n_classes, n_points).
    """
    if n_classes is None:
        n_classes = probs.shape[1] if probs.ndim == 2 else 0
    px = np.linspace(0, 1, n_points)
    py_p = np.zeros((n_classes, n_points))
    py_r = np.zeros((n_classes, n_points))
    py_f1 = np.zeros((n_classes, n_points))

    if len(y_true) == 0 or n_classes == 0:
        return px, py_p, py_r, py_f1

    pred_ids = np.argmax(probs, axis=1).astype(np.int64)
    confidences = probs[np.arange(len(probs)), pred_ids]

    for ci, conf in enumerate(px):
        p, r, f = _prf_at_threshold(y_true, pred_ids, confidences, float(conf), n_classes)
        py_p[:, ci] = p
        py_r[:, ci] = r
        py_f1[:, ci] = f

    return px, py_p, py_r, py_f1


def compute_pr_curves(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_classes: Optional[int] = None,
    n_points: int = 1000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    One-vs-rest precision-recall curves from class probability scores.

    Returns (px, py, ap) where px is confidence axis, py is (n_classes, n_points)
    precision values vs recall=1-px (Ultralytics PR plot convention), and ap is
    per-class average precision.
    """
    if n_classes is None:
        n_classes = probs.shape[1] if probs.ndim == 2 else 0
    px = np.linspace(0, 1, n_points)
    py = np.zeros((n_classes, n_points))
    ap = np.zeros(n_classes)

    if len(y_true) == 0 or n_classes == 0:
        return px, py, ap

    for cls in range(n_classes):
        scores = probs[:, cls]
        positives = y_true == cls
        total_gt = int(positives.sum())
        if total_gt == 0:
            continue

        order = np.argsort(-scores)
        scores_sorted = scores[order]
        tp_arr = positives[order].astype(np.float64)

        tp_cum = np.cumsum(tp_arr)
        fp_cum = np.cumsum(1.0 - tp_arr)
        recall_curve = tp_cum / total_gt
        precision_curve = tp_cum / np.maximum(tp_cum + fp_cum, 1e-12)

        for ci, conf in enumerate(px):
            mask = scores_sorted >= conf
            if not mask.any():
                py[cls, ci] = 1.0 if ci == 0 else py[cls, max(ci - 1, 0)]
                continue
            idx = int(mask.sum()) - 1
            py[cls, ci] = float(precision_curve[idx])

        mrec = np.concatenate(([0.0], recall_curve, [1.0]))
        mpre = np.concatenate(([1.0], precision_curve, [0.0]))
        for i in range(len(mpre) - 1, 0, -1):
            mpre[i - 1] = max(mpre[i - 1], mpre[i])
        x = np.where(mrec[1:] != mrec[:-1])[0]
        ap[cls] = float(np.sum((mrec[x + 1] - mrec[x]) * mpre[x + 1]))

    return px, py, ap


def create_error_statistics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_classes: int,
) -> Tuple[np.ndarray, List[Tuple], List[Tuple]]:
    """
    Confusion matrix plus false positive / false negative lists.

    FP entries: (pred_class, confidence_placeholder, sample_idx)
    FN entries: (true_class, sample_idx) — includes abstains and misclassifications.
    """
    cm = confusion_matrix(y_true, y_pred, n_classes)
    false_positives: List[Tuple] = []
    false_negatives: List[Tuple] = []

    for idx, (t, p) in enumerate(zip(y_true.tolist(), y_pred.tolist())):
        t = int(t)
        p = int(p)
        if p < 0:
            false_negatives.append((t, idx))
            continue
        if t == p:
            continue
        false_positives.append((p, 1.0, idx))
        false_negatives.append((t, idx))

    return cm, false_positives, false_negatives


def save_error_statistics_csv(
    eval_dir: Path,
    class_names: Sequence[str],
    false_positives: List[Tuple],
    false_negatives: List[Tuple],
) -> Optional[str]:
    num_classes = len(class_names)
    fp_by_class: Dict[int, Dict] = {}
    fn_by_class: Dict[int, Dict] = {}

    for cls, conf, _ in false_positives:
        if cls not in fp_by_class:
            fp_by_class[cls] = {"count": 0, "confidences": []}
        fp_by_class[cls]["count"] += 1
        fp_by_class[cls]["confidences"].append(conf)

    for cls, _ in false_negatives:
        fn_by_class[cls] = fn_by_class.get(cls, {"count": 0})
        fn_by_class[cls]["count"] += 1

    rows = []
    for cls_id in range(num_classes):
        fp_count = fp_by_class.get(cls_id, {"count": 0})["count"]
        fp_confs = fp_by_class.get(cls_id, {"confidences": []}).get("confidences", [])
        fn_count = fn_by_class.get(cls_id, {"count": 0})["count"]
        total = fp_count + fn_count
        rows.append(
            {
                "class_id": cls_id,
                "class_name": class_names[cls_id]
                if cls_id < len(class_names)
                else f"class_{cls_id}",
                "false_positives": fp_count,
                "false_negatives": fn_count,
                "total_errors": total,
                "fp_rate": fp_count / total if total > 0 else 0,
                "fn_rate": fn_count / total if total > 0 else 0,
                "avg_fp_confidence": float(np.mean(fp_confs)) if fp_confs else 0,
                "min_fp_confidence": float(min(fp_confs)) if fp_confs else 0,
                "max_fp_confidence": float(max(fp_confs)) if fp_confs else 0,
            }
        )

    df = pd.DataFrame(rows).sort_values("total_errors", ascending=False)
    path = Path(eval_dir) / "error_statistics.csv"
    df.to_csv(path, index=False)
    return str(path)


def process_evaluation_results(
    eval_dir: Path,
    class_names: Sequence[str],
    n_points: int = 101,
) -> Dict[int, Dict]:
    """Per-class optimal confidence threshold from evaluation_results.json."""
    results_path = Path(eval_dir) / "evaluation_results.json"
    if not results_path.exists():
        return {}

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    n_classes = len(class_names)
    labels = []
    confidences = []
    pred_ids = []
    for row in results:
        gt = row.get("ground_truth") or {}
        pred = row.get("predictions") or {}
        if isinstance(gt, list):
            label = int(gt[0]["label"]) if gt else -1
        else:
            label = int(gt.get("label", -1))
        if isinstance(pred, list):
            if not pred:
                continue
            pred_id = int(pred[0]["label"])
            conf = float(pred[0].get("confidence", 0.0))
        else:
            pred_id = int(pred.get("label", -1))
            conf = float(pred.get("confidence", 0.0))
        if label < 0:
            continue
        labels.append(label)
        pred_ids.append(pred_id)
        confidences.append(conf)

    if not labels:
        return {}

    y_true = np.asarray(labels, dtype=np.int64)
    pred_ids_arr = np.asarray(pred_ids, dtype=np.int64)
    conf_arr = np.asarray(confidences, dtype=np.float64)
    thresholds = np.linspace(0, 1, n_points)

    out: Dict[int, Dict] = {}
    for class_id in range(n_classes):
        total_gt = int(np.sum(y_true == class_id))
        total_predictions = int(np.sum(pred_ids_arr == class_id))
        f1_scores = []
        precisions = []
        recalls = []
        for thresh in thresholds:
            p, r, f = _prf_at_threshold(y_true, pred_ids_arr, conf_arr, float(thresh), n_classes)
            precisions.append(float(p[class_id]))
            recalls.append(float(r[class_id]))
            f1_scores.append(float(f[class_id]))

        f1_arr = np.asarray(f1_scores)
        best_idx = int(np.argmax(f1_arr)) if len(f1_arr) else 0
        prec_arr = np.asarray(precisions)
        rec_arr = np.asarray(recalls)
        sort_idx = np.argsort(rec_arr)
        ap = float(np.trapz(prec_arr[sort_idx], rec_arr[sort_idx])) if len(rec_arr) > 1 else 0.0

        out[class_id] = {
            "ap": ap,
            "optimal_threshold": float(thresholds[best_idx]),
            "optimal_f1": float(f1_arr[best_idx]) if len(f1_arr) else 0.0,
            "optimal_precision": float(prec_arr[best_idx]) if len(prec_arr) else 0.0,
            "optimal_recall": float(rec_arr[best_idx]) if len(rec_arr) else 0.0,
            "total_predictions": total_predictions,
            "total_gt": total_gt,
        }

    return out
