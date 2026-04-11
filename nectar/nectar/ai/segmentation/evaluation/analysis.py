"""PR curve analysis and error statistics for segmentation evaluation.

Adapted from the detection module. Uses box IoU for matching (the standard
approach for instance segmentation evaluation alongside mask metrics).
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)

    if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
        return 0.0

    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = box1_area + box2_area - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


def match_predictions_to_gt(
    predictions: List[Dict],
    ground_truths: List[Dict],
    iou_threshold: float = 0.5,
) -> Tuple[List[float], List[int], List[int]]:
    if not predictions:
        return [], [], []

    if not ground_truths:
        return (
            [p["confidence"] for p in predictions],
            [0] * len(predictions),
            [p["label"] for p in predictions],
        )

    sorted_preds = sorted(predictions, key=lambda x: x["confidence"], reverse=True)
    scores, true_labels, pred_labels = [], [], []
    matched_gts: set = set()

    for pred in sorted_preds:
        best_iou = 0.0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(ground_truths):
            if gt_idx in matched_gts or gt["label"] != pred["label"]:
                continue
            iou = calculate_iou(pred["box"], gt["box"])
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        scores.append(pred["confidence"])
        pred_labels.append(pred["label"])

        if best_iou >= iou_threshold:
            true_labels.append(1)
            matched_gts.add(best_gt_idx)
        else:
            true_labels.append(0)

    return scores, true_labels, pred_labels


def _metrics_at_threshold(
    scores: np.ndarray,
    true_labels: np.ndarray,
    threshold: float,
    total_gt: int,
) -> Tuple[float, float, float]:
    if len(scores) == 0:
        return 0.0, 0.0, 0.0

    mask = scores >= threshold
    tp = np.sum(mask & (true_labels == 1))
    fp = np.sum(mask & (true_labels == 0))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / total_gt if total_gt > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def process_evaluation_results(
    eval_dir: Path,
    class_names: List[str],
) -> Dict[int, Dict]:
    results_path = eval_dir / "evaluation_results.json"
    if not results_path.exists():
        return {}

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    class_data = defaultdict(lambda: {"scores": [], "true_labels": [], "total_gt": 0})

    for img_result in results:
        for gt in img_result["ground_truth"]:
            class_data[gt["label"]]["total_gt"] += 1

        scores, true_labels, pred_labels = match_predictions_to_gt(
            img_result["predictions"], img_result["ground_truth"]
        )
        for score, true_label, pred_label in zip(scores, true_labels, pred_labels):
            class_data[pred_label]["scores"].append(score)
            class_data[pred_label]["true_labels"].append(true_label)

    pr_curves: Dict[int, Dict] = {}

    for class_id in range(len(class_names)):
        data = class_data[class_id]
        if len(data["scores"]) == 0:
            pr_curves[class_id] = {
                "precision": np.array([1.0, 0.0]),
                "recall": np.array([0.0, 1.0]),
                "thresholds": np.array([1.0, 0.0]),
                "f1_scores": np.array([0.0, 0.0]),
                "ap": 0.0,
                "optimal_threshold": 0.5,
                "optimal_f1": 0.0,
                "optimal_precision": 0.0,
                "optimal_recall": 0.0,
                "total_predictions": 0,
                "total_gt": data["total_gt"],
            }
            continue

        scores_arr = np.array(data["scores"])
        tl_arr = np.array(data["true_labels"])
        total_gt = data["total_gt"]

        thresholds = np.linspace(0, 1, 101)
        precisions, recalls, f1_scores = [], [], []
        for thresh in thresholds:
            p, r, f1 = _metrics_at_threshold(scores_arr, tl_arr, thresh, total_gt)
            precisions.append(p)
            recalls.append(r)
            f1_scores.append(f1)

        precisions = np.array(precisions)
        recalls = np.array(recalls)
        f1_scores = np.array(f1_scores)

        best_idx = int(np.argmax(f1_scores))
        sort_idx = np.argsort(recalls)
        ap = float(np.trapz(precisions[sort_idx], recalls[sort_idx]))

        pr_curves[class_id] = {
            "precision": precisions,
            "recall": recalls,
            "thresholds": thresholds,
            "f1_scores": f1_scores,
            "ap": ap,
            "optimal_threshold": float(thresholds[best_idx]),
            "optimal_f1": float(f1_scores[best_idx]),
            "optimal_precision": float(precisions[best_idx]),
            "optimal_recall": float(recalls[best_idx]),
            "total_predictions": len(scores_arr),
            "total_gt": total_gt,
        }

    return pr_curves


def compute_curves(
    all_preds: list,
    all_gts: list,
    num_classes: int,
    iou_threshold: float = 0.5,
    use_masks: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute per-class P, R, F1 curves over confidence thresholds.

    Parameters
    ----------
    use_masks : bool
        If True, use mask IoU for matching instead of box IoU.
    """
    px = np.linspace(0, 1, 1000)
    py_p = np.zeros((num_classes, len(px)))
    py_r = np.zeros((num_classes, len(px)))
    py_f1 = np.zeros((num_classes, len(px)))
    ap = np.zeros(num_classes)

    for cls_id in range(num_classes):
        all_scores: list = []
        all_tp: list = []
        total_gt = 0

        for preds, gts in zip(all_preds, all_gts):
            gt_cls_mask = (
                gts.class_id == cls_id if gts.class_id is not None else np.zeros(0, dtype=bool)
            )
            gt_boxes = gts.xyxy[gt_cls_mask] if gt_cls_mask.any() else np.zeros((0, 4))
            total_gt += len(gt_boxes)

            pred_cls_mask = (
                preds.class_id == cls_id
                if preds.class_id is not None
                else np.zeros(0, dtype=bool)
            )
            if not pred_cls_mask.any():
                continue
            pred_boxes = preds.xyxy[pred_cls_mask]
            pred_conf = (
                preds.confidence[pred_cls_mask]
                if preds.confidence is not None
                else np.ones(pred_cls_mask.sum())
            )

            if len(gt_boxes) == 0:
                all_scores.extend(pred_conf.tolist())
                all_tp.extend([0] * len(pred_conf))
                continue

            if use_masks and gts.mask is not None and preds.mask is not None:
                gt_masks = gts.mask[gt_cls_mask]
                pred_masks = preds.mask[pred_cls_mask]
                if gt_masks.size > 0 and pred_masks.size > 0:
                    iou_mat = _mask_iou_matrix(gt_masks, pred_masks)
                else:
                    iou_mat = _iou_matrix(gt_boxes, pred_boxes)
            else:
                iou_mat = _iou_matrix(gt_boxes, pred_boxes)

            matched_gt: set = set()
            order = np.argsort(-pred_conf)
            for d_idx in order:
                ious = iou_mat[:, d_idx]
                best_gt = -1
                best_iou = iou_threshold
                for g_idx in range(len(gt_boxes)):
                    if g_idx in matched_gt:
                        continue
                    if ious[g_idx] > best_iou:
                        best_iou = ious[g_idx]
                        best_gt = g_idx
                all_scores.append(float(pred_conf[d_idx]))
                if best_gt >= 0:
                    all_tp.append(1)
                    matched_gt.add(best_gt)
                else:
                    all_tp.append(0)

        if not all_scores or total_gt == 0:
            continue

        scores = np.array(all_scores)
        tp_arr = np.array(all_tp)
        order = np.argsort(-scores)
        scores = scores[order]
        tp_arr = tp_arr[order]

        tp_cum = np.cumsum(tp_arr)
        fp_cum = np.cumsum(1 - tp_arr)

        recall_curve = tp_cum / total_gt
        precision_curve = tp_cum / (tp_cum + fp_cum)

        for ci, conf in enumerate(px):
            mask = scores >= conf
            if not mask.any():
                py_p[cls_id, ci] = 1.0
                continue
            idx = mask.sum() - 1
            py_p[cls_id, ci] = float(precision_curve[idx])
            py_r[cls_id, ci] = float(recall_curve[idx])

        denom = py_p[cls_id] + py_r[cls_id]
        py_f1[cls_id] = np.where(denom > 0, 2 * py_p[cls_id] * py_r[cls_id] / denom, 0)

        mrec = np.concatenate(([0.0], recall_curve, [1.0]))
        mpre = np.concatenate(([1.0], precision_curve, [0.0]))
        for i in range(len(mpre) - 1, 0, -1):
            mpre[i - 1] = max(mpre[i - 1], mpre[i])
        x = np.where(mrec[1:] != mrec[:-1])[0]
        ap[cls_id] = np.sum((mrec[x + 1] - mrec[x]) * mpre[x + 1])

    return px, py_p, py_r, py_f1, ap


def create_error_statistics(
    eval_dir: Path,
    class_names: List[str],
    iou_threshold: float = 0.5,
    conf_threshold: float = 0.3,
) -> Tuple[np.ndarray, List[Tuple], List[Tuple]]:
    results_path = eval_dir / "evaluation_results.json"
    if not results_path.exists():
        return np.zeros((len(class_names), len(class_names))), [], []

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    num_classes = len(class_names)
    cm = np.zeros((num_classes, num_classes), dtype=int)
    false_positives: List[Tuple] = []
    false_negatives: List[Tuple] = []

    for img_idx, img_result in enumerate(results):
        preds = img_result.get("predictions", [])
        gts = img_result.get("ground_truth", [])

        pred_boxes = np.array([p["box"] for p in preds], dtype=float) if preds else np.zeros((0, 4))
        pred_labels = (
            np.array([int(p["label"]) for p in preds], dtype=int)
            if preds
            else np.zeros(0, dtype=int)
        )
        pred_conf = (
            np.array([float(p.get("confidence", 1.0)) for p in preds], dtype=float)
            if preds
            else np.zeros(0)
        )

        if pred_conf.size:
            keep = pred_conf >= conf_threshold
            pred_boxes, pred_labels, pred_conf = (
                pred_boxes[keep],
                pred_labels[keep],
                pred_conf[keep],
            )

        gt_boxes = np.array([g["box"] for g in gts], dtype=float) if gts else np.zeros((0, 4))
        gt_labels = (
            np.array([int(g["label"]) for g in gts], dtype=int) if gts else np.zeros(0, dtype=int)
        )

        if gt_boxes.shape[0] == 0 and pred_boxes.shape[0] == 0:
            continue
        if gt_boxes.shape[0] == 0:
            for cls, conf in zip(pred_labels.tolist(), pred_conf.tolist()):
                false_positives.append((cls, conf, img_idx))
            continue
        if pred_boxes.shape[0] == 0:
            for cls in gt_labels.tolist():
                false_negatives.append((cls, img_idx))
            continue

        iou_mat = _iou_matrix(gt_boxes, pred_boxes)
        matches = _match_iou_matrix(iou_mat, iou_threshold)

        matched_gt = set(int(m[0]) for m in matches) if matches.size else set()
        matched_det = set(int(m[1]) for m in matches) if matches.size else set()

        for g_idx, d_idx, _ in matches:
            t_cls = int(gt_labels[int(g_idx)])
            p_cls = int(pred_labels[int(d_idx)])
            if 0 <= t_cls < num_classes and 0 <= p_cls < num_classes:
                cm[t_cls, p_cls] += 1

        for g_idx in range(gt_boxes.shape[0]):
            if g_idx not in matched_gt:
                false_negatives.append((int(gt_labels[g_idx]), img_idx))

        for d_idx in range(pred_boxes.shape[0]):
            if d_idx not in matched_det:
                false_positives.append((int(pred_labels[d_idx]), float(pred_conf[d_idx]), img_idx))

    return cm, false_positives, false_negatives


def save_error_statistics_csv(
    eval_dir: Path,
    class_names: List[str],
    false_positives: List[Tuple],
    false_negatives: List[Tuple],
) -> None:
    if not false_positives and not false_negatives:
        return

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
            }
        )

    pd.DataFrame(rows).sort_values("total_errors", ascending=False).to_csv(
        eval_dir / "error_statistics.csv",
        index=False,
    )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _mask_iou_matrix(gt_masks: np.ndarray, det_masks: np.ndarray) -> np.ndarray:
    """Compute pairwise mask IoU between ground-truth and detection masks.

    Parameters
    ----------
    gt_masks : np.ndarray
        Boolean masks of shape ``(N, H, W)``.
    det_masks : np.ndarray
        Boolean masks of shape ``(M, H, W)``.

    Returns
    -------
    np.ndarray
        IoU matrix of shape ``(N, M)``.
    """
    if gt_masks.size == 0 or det_masks.size == 0:
        return np.zeros((gt_masks.shape[0], det_masks.shape[0]))

    gt_flat = gt_masks.reshape(gt_masks.shape[0], -1).astype(bool)
    det_flat = det_masks.reshape(det_masks.shape[0], -1).astype(bool)

    intersection = np.logical_and(gt_flat[:, None, :], det_flat[None, :, :]).sum(axis=2)
    union = np.logical_or(gt_flat[:, None, :], det_flat[None, :, :]).sum(axis=2)

    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(union > 0, intersection / union, 0.0)


def _iou_matrix(gt_boxes: np.ndarray, det_boxes: np.ndarray) -> np.ndarray:
    if gt_boxes.size == 0 or det_boxes.size == 0:
        return np.zeros((gt_boxes.shape[0], det_boxes.shape[0]))

    gx1, gy1, gx2, gy2 = gt_boxes[:, 0:1], gt_boxes[:, 1:2], gt_boxes[:, 2:3], gt_boxes[:, 3:4]
    dx1, dy1, dx2, dy2 = det_boxes[:, 0], det_boxes[:, 1], det_boxes[:, 2], det_boxes[:, 3]

    ix1 = np.maximum(gx1, dx1)
    iy1 = np.maximum(gy1, dy1)
    ix2 = np.minimum(gx2, dx2)
    iy2 = np.minimum(gy2, dy2)

    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    union = (gx2 - gx1) * (gy2 - gy1) + (dx2 - dx1) * (dy2 - dy1) - inter

    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(union > 0, inter / union, 0.0)


def _match_iou_matrix(iou_mat: np.ndarray, iou_threshold: float) -> np.ndarray:
    gi, dj = np.where(iou_mat > iou_threshold)
    if gi.size == 0:
        return np.zeros((0, 3))

    matches = np.stack([gi, dj, iou_mat[gi, dj]], axis=1)
    matches = matches[matches[:, 2].argsort()[::-1]]

    _, first_idx = np.unique(matches[:, 1], return_index=True)
    matches = matches[np.sort(first_idx)]
    matches = matches[matches[:, 2].argsort()[::-1]]

    _, first_idx = np.unique(matches[:, 0], return_index=True)
    matches = matches[np.sort(first_idx)]

    return matches
