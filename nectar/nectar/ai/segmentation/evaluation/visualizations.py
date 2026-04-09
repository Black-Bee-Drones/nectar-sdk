"""Visualization utilities for segmentation evaluation.

Adapted from the detection module. Uses ``MaskAnnotator`` for prediction
samples instead of ``BoxAnnotator``.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    import supervision as sv
except ImportError:
    sv = None

_GRAY = "#cecece"
_PURPLE = "#a559aa"
_TEAL = "#59a89c"
_GOLD = "#f0c571"
_RED = "#e02b35"
_DARK_BLUE = "#082a54"


def _smooth(y: np.ndarray, f: float = 0.05) -> np.ndarray:
    n = max(round(len(y) * f), 1)
    return np.convolve(y, np.ones(n) / n, mode="same")


# ---------------------------------------------------------------------------
# PR / confidence curves
# ---------------------------------------------------------------------------


def plot_pr_curve(
    px: np.ndarray,
    py: np.ndarray,
    ap: np.ndarray,
    names: Dict[int, str],
    output_dir: Path,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(9, 6), tight_layout=True)

    if 0 < len(names) < 21:
        for i, y in enumerate(py):
            ax.plot(1 - px, y, linewidth=1, label=f"{names.get(i, i)} {ap[i]:.3f}")
    else:
        ax.plot(1 - px, py.T, linewidth=1, color="grey", alpha=0.4)

    mean_y = py.mean(0)
    ax.plot(
        1 - px, mean_y, linewidth=3, color=_DARK_BLUE, label=f"all classes {ap.mean():.3f} mAP@0.5"
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=8)
    ax.set_title("Precision-Recall Curve (Segmentation)")

    path = output_dir / "PR_curve.png"
    fig.savefig(path, dpi=250)
    plt.close(fig)
    return str(path)


def plot_confidence_curve(
    px: np.ndarray,
    py: np.ndarray,
    names: Dict[int, str],
    output_dir: Path,
    ylabel: str = "Metric",
    filename: str = "curve.png",
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(9, 6), tight_layout=True)

    if 0 < len(names) < 21:
        for i, y in enumerate(py):
            ax.plot(px, y, linewidth=1, label=f"{names.get(i, i)}")
    else:
        ax.plot(px, py.T, linewidth=1, color="grey", alpha=0.4)

    mean_y = _smooth(py.mean(0), 0.05)
    best_val = mean_y.max()
    best_conf = px[mean_y.argmax()]
    ax.plot(
        px,
        mean_y,
        linewidth=3,
        color=_DARK_BLUE,
        label=f"all classes {best_val:.2f} at {best_conf:.3f}",
    )
    ax.set_xlabel("Confidence")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=8)
    ax.set_title(f"{ylabel}-Confidence Curve")

    path = output_dir / filename
    fig.savefig(path, dpi=250)
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------


def plot_confusion_matrix(
    cm: "sv.ConfusionMatrix",
    output_dir: Path,
    classes: List[str],
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig = cm.plot(classes=classes)
    fig.set_size_inches(12, 10)
    plt.tight_layout()
    path = output_dir / "confusion_matrix.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Error analysis
# ---------------------------------------------------------------------------


def plot_error_analysis(
    cm_matrix: np.ndarray,
    false_positives: List[Tuple],
    false_negatives: List[Tuple],
    class_names: List[str],
    output_dir: Path,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    num_classes = len(class_names)

    fp_by_class = np.zeros(num_classes, dtype=int)
    fn_by_class = np.zeros(num_classes, dtype=int)
    for cls, _, _ in false_positives:
        if 0 <= cls < num_classes:
            fp_by_class[cls] += 1
    for cls, _ in false_negatives:
        if 0 <= cls < num_classes:
            fn_by_class[cls] += 1

    fig, axes = plt.subplots(2, 2, figsize=(20, 16))

    # 1. Raw CM + FP/FN
    cm_ext = np.zeros((num_classes + 1, num_classes + 1), dtype=int)
    cm_ext[:num_classes, :num_classes] = cm_matrix
    cm_ext[:num_classes, num_classes] = fn_by_class
    cm_ext[num_classes, :num_classes] = fp_by_class

    im1 = axes[0, 0].imshow(cm_ext, cmap="Blues", aspect="auto")
    ticks = list(range(num_classes + 1))
    labels = class_names + ["FN"]
    axes[0, 0].set_xticks(ticks)
    axes[0, 0].set_yticks(ticks)
    axes[0, 0].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axes[0, 0].set_yticklabels(class_names + ["FP"], fontsize=8)
    axes[0, 0].set_xlabel("Predicted", fontsize=10, fontweight="bold")
    axes[0, 0].set_ylabel("True", fontsize=10, fontweight="bold")
    axes[0, 0].set_title("Confusion Matrix (+FP/FN)", fontsize=12, fontweight="bold")
    plt.colorbar(im1, ax=axes[0, 0], fraction=0.046, pad=0.04)
    for i in range(num_classes + 1):
        for j in range(num_classes + 1):
            if cm_ext[i, j] > 0:
                color = "white" if cm_ext[i, j] > cm_ext.max() / 2 else "black"
                axes[0, 0].text(
                    j, i, str(cm_ext[i, j]), ha="center", va="center", color=color, fontsize=7
                )

    # 2. Normalized CM
    cm_norm = cm_ext.astype(float).copy()
    for i in range(num_classes):
        row_sum = cm_norm[i, :].sum()
        if row_sum > 0:
            cm_norm[i, :] /= row_sum
    cm_norm[num_classes, :] = 0

    im2 = axes[0, 1].imshow(cm_norm, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1.0)
    axes[0, 1].set_xticks(ticks)
    axes[0, 1].set_yticks(ticks)
    axes[0, 1].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axes[0, 1].set_yticklabels(class_names + ["FP"], fontsize=8)
    axes[0, 1].set_xlabel("Predicted", fontsize=10, fontweight="bold")
    axes[0, 1].set_ylabel("True", fontsize=10, fontweight="bold")
    axes[0, 1].set_title("Normalized Confusion Matrix", fontsize=12, fontweight="bold")
    plt.colorbar(im2, ax=axes[0, 1], fraction=0.046, pad=0.04)
    for i in range(num_classes):
        for j in range(num_classes + 1):
            if cm_norm[i, j] > 0.05:
                axes[0, 1].text(
                    j,
                    i,
                    f"{cm_norm[i, j]:.2f}",
                    ha="center",
                    va="center",
                    color="white" if cm_norm[i, j] > 0.5 else "black",
                    fontsize=7,
                )

    # 3. FP/FN bars
    error_df = pd.DataFrame({"Class": class_names, "FP": fp_by_class, "FN": fn_by_class})
    error_df["Total"] = error_df["FP"] + error_df["FN"]
    error_df = error_df.sort_values("Total", ascending=False)
    x = np.arange(len(error_df))
    w = 0.35
    axes[1, 0].bar(x - w / 2, error_df["FP"], w, label="False Positives", color=_RED, alpha=0.85)
    axes[1, 0].bar(
        x + w / 2, error_df["FN"], w, label="False Negatives", color=_DARK_BLUE, alpha=0.85
    )
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(error_df["Class"], rotation=45, ha="right", fontsize=8)
    axes[1, 0].set_ylabel("Count", fontsize=10, fontweight="bold")
    axes[1, 0].set_title("FP & FN by Class", fontsize=12, fontweight="bold")
    axes[1, 0].legend()

    # 4. Top confusions
    pairs = []
    for i in range(num_classes):
        for j in range(num_classes):
            if i != j and cm_matrix[i, j] > 0:
                pairs.append((i, j, cm_matrix[i, j]))
    pairs.sort(key=lambda p: p[2], reverse=True)
    top = pairs[:15]
    if top:
        pair_labels = [f"{class_names[t][:12]} -> {class_names[p][:12]}" for t, p, _ in top]
        counts = [c for _, _, c in top]
        axes[1, 1].barh(range(len(pair_labels)), counts, color=_RED, alpha=0.85)
        axes[1, 1].set_yticks(range(len(pair_labels)))
        axes[1, 1].set_yticklabels(pair_labels, fontsize=8)
        axes[1, 1].set_xlabel("Count", fontsize=10, fontweight="bold")
    else:
        axes[1, 1].text(0.5, 0.5, "No class confusions", ha="center", va="center", fontsize=12)
    axes[1, 1].set_title("Top Class Confusions", fontsize=12, fontweight="bold")

    plt.suptitle("Error Analysis (Segmentation)", fontsize=16, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    path = output_dir / "error_analysis.png"
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Performance analysis
# ---------------------------------------------------------------------------


def plot_performance_analysis(per_class_df: pd.DataFrame, output_dir: Path) -> str:
    if per_class_df.empty or "ap50" not in per_class_df.columns:
        return ""

    output_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    df_sorted = per_class_df.sort_values("ap50", ascending=True)

    def _color(ap):
        if ap >= 0.8:
            return _TEAL
        if ap >= 0.5:
            return _GOLD
        return _RED

    colors = [_color(v) for v in df_sorted["ap50"]]
    bars = axes[0].barh(
        df_sorted["class_name"],
        df_sorted["ap50"],
        color=colors,
        alpha=0.9,
        edgecolor="black",
        linewidth=0.3,
    )
    for bar, val in zip(bars, df_sorted["ap50"]):
        axes[0].text(
            val + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}",
            va="center",
            fontsize=9,
            fontweight="bold",
        )
    axes[0].axvline(x=0.5, color=_GOLD, linestyle="--", alpha=0.5, label="0.5")
    axes[0].axvline(x=0.8, color=_TEAL, linestyle="--", alpha=0.5, label="0.8")
    axes[0].set_xlabel("AP@50", fontsize=12, fontweight="bold")
    axes[0].set_title("Class Performance (Segmentation)", fontsize=13, fontweight="bold")
    axes[0].set_xlim([0, 1.05])
    axes[0].legend(loc="lower right")
    axes[0].grid(True, alpha=0.2, axis="x")

    if "precision" in per_class_df.columns and "recall" in per_class_df.columns:
        scatter = axes[1].scatter(
            per_class_df["recall"],
            per_class_df["precision"],
            s=per_class_df["ap50"] * 300 + 30,
            c=per_class_df["ap50"],
            cmap="RdYlGn",
            vmin=0,
            vmax=1,
            alpha=0.85,
            edgecolors="black",
            linewidth=0.8,
        )
        for _, row in per_class_df.iterrows():
            axes[1].annotate(
                row["class_name"][:10],
                (row["recall"], row["precision"]),
                fontsize=8,
                ha="center",
                xytext=(0, 7),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.7),
            )
        axes[1].set_xlabel("Recall", fontsize=12, fontweight="bold")
        axes[1].set_ylabel("Precision", fontsize=12, fontweight="bold")
        axes[1].set_title(
            "Precision-Recall Balance (size/color = AP@50)", fontsize=13, fontweight="bold"
        )
        axes[1].set_xlim([0, 1.05])
        axes[1].set_ylim([0, 1.05])
        axes[1].grid(True, alpha=0.2)
        plt.colorbar(scatter, ax=axes[1], shrink=0.8, label="AP@50")

    plt.tight_layout()
    path = output_dir / "performance_analysis.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Metrics summary
# ---------------------------------------------------------------------------


def plot_metrics_summary(metrics: Dict[str, float], output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(10, 5), tight_layout=True)

    items = {
        "mAP@50": metrics.get("map50", 0),
        "mAP@50-95": metrics.get("map50_95", 0),
        "Precision": metrics.get("precision", 0),
        "Recall": metrics.get("recall", 0),
        "F1": metrics.get("f1_score", 0),
    }
    colors = [_DARK_BLUE, _GOLD, _TEAL, _RED, _PURPLE]
    bars = ax.bar(items.keys(), items.values(), color=colors, edgecolor="black", linewidth=0.3)
    for bar, v in zip(bars, items.values()):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            v + 0.02,
            f"{v:.3f}",
            ha="center",
            fontsize=10,
            fontweight="bold",
        )
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Score")
    ax.set_title("Segmentation Evaluation Metrics", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.2, axis="y")

    path = output_dir / "results.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Prediction samples (with mask overlays)
# ---------------------------------------------------------------------------


def plot_prediction_samples(
    images: List[np.ndarray],
    predictions: List,
    targets: List,
    paths: List[str],
    classes: List[str],
    output_dir: Path,
    max_samples: int = 4,
) -> Optional[str]:
    if not images or sv is None:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    n = min(max_samples, len(images))
    indices = np.random.choice(len(images), n, replace=False)

    mask_ann = sv.MaskAnnotator(opacity=0.45)
    box_ann = sv.BoxAnnotator(thickness=1)
    label_ann = sv.LabelAnnotator(text_scale=0.4, text_thickness=1)

    annotated, titles = [], []
    for idx in indices:
        gt_img = images[idx].copy()
        pred_img = images[idx].copy()
        gt, pred = targets[idx], predictions[idx]

        if len(gt) > 0:
            gt_labels = [classes[int(c)] if int(c) < len(classes) else "?" for c in gt.class_id]
            if gt.mask is not None and len(gt.mask) > 0:
                gt_img = mask_ann.annotate(gt_img, gt)
            gt_img = box_ann.annotate(gt_img, gt)
            gt_img = label_ann.annotate(gt_img, gt, gt_labels)

        if len(pred) > 0:
            pred_labels = [
                f"{classes[int(c)] if int(c) < len(classes) else '?'}: {conf:.2f}"
                for c, conf in zip(
                    pred.class_id,
                    pred.confidence if pred.confidence is not None else np.ones(len(pred)),
                )
            ]
            if pred.mask is not None and len(pred.mask) > 0:
                pred_img = mask_ann.annotate(pred_img, pred)
            pred_img = box_ann.annotate(pred_img, pred)
            pred_img = label_ann.annotate(pred_img, pred, pred_labels)

        annotated.extend([gt_img, pred_img])
        name = Path(paths[idx]).name
        titles.extend([f"GT: {name} ({len(gt)})", f"Pred: {name} ({len(pred)})"])

    rows = len(indices)
    fig, axes = plt.subplots(rows, 2, figsize=(18, 4.5 * rows))
    if rows == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    for i, ax in enumerate(axes):
        if i < len(annotated):
            img = annotated[i]
            if img.ndim == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            ax.imshow(img)
            ax.set_title(titles[i], fontsize=10)
        ax.axis("off")

    plt.suptitle("Prediction Samples – GT vs Pred (Segmentation)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = output_dir / "prediction_samples.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(path)


# ---------------------------------------------------------------------------
# Per-class metrics CSV / JSON
# ---------------------------------------------------------------------------


def save_per_class_metrics(per_class_metrics: List[Dict], output_dir: Path) -> Tuple[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(per_class_metrics)
    csv_path = output_dir / "per_class_metrics.csv"
    json_path = output_dir / "per_class_metrics.json"
    df.to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(per_class_metrics, f, indent=2)
    return str(csv_path), str(json_path)


# ---------------------------------------------------------------------------
# Evaluation report
# ---------------------------------------------------------------------------


def generate_evaluation_report(
    metrics: Dict[str, float],
    config: Dict,
    output_dir: Path,
    raw_results: Optional[List[Dict]] = None,
) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)

    visualizations = {}
    for f in list(output_dir.glob("*.png")) + list(output_dir.glob("*.csv")):
        visualizations[f.stem] = str(f)

    report = {
        "metrics": metrics,
        "config": config,
        "visualizations": visualizations,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    report_path = output_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return str(report_path)
