"""Classification evaluation visualizations."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

_PURPLE = "#a559aa"
_TEAL = "#59a89c"
_GOLD = "#f0c571"
_RED = "#e02b35"
_DARK_BLUE = "#082a54"


def _smooth(y: np.ndarray, f: float = 0.05) -> np.ndarray:
    n = max(round(len(y) * f), 1)
    return np.convolve(y, np.ones(n) / n, mode="same")


def plot_pr_curve(
    px: np.ndarray,
    py: np.ndarray,
    ap: np.ndarray,
    names: Dict[int, str],
    output_dir: Path,
) -> str:
    """One-vs-rest Precision-Recall curve (Ultralytics style)."""
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(9, 6), tight_layout=True)

    if 0 < len(names) < 21:
        for i, y in enumerate(py):
            ax.plot(1 - px, y, linewidth=1, label=f"{names.get(i, i)} {ap[i]:.3f}")
    else:
        ax.plot(1 - px, py.T, linewidth=1, color="grey", alpha=0.4)

    mean_y = py.mean(0)
    ax.plot(
        1 - px,
        mean_y,
        linewidth=3,
        color=_DARK_BLUE,
        label=f"all classes {ap.mean():.3f} mAP",
    )
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.05)
    ax.legend(bbox_to_anchor=(1.04, 1), loc="upper left", fontsize=8)
    ax.set_title("Precision-Recall Curve")

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
    """Metric-vs-confidence curve (Ultralytics mc_curve style)."""
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(9, 6), tight_layout=True)

    if 0 < len(names) < 21:
        for i, y in enumerate(py):
            ax.plot(px, y, linewidth=1, label=f"{names.get(i, i)}")
    else:
        ax.plot(px, py.T, linewidth=1, color="grey", alpha=0.4)

    mean_y = _smooth(py.mean(0), 0.05)
    best_val = float(mean_y.max())
    best_conf = float(px[mean_y.argmax()])
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


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: Dict[int, str],
    output_path: str,
    normalize: bool = False,
) -> str:
    """Save a confusion matrix heatmap (counts by default)."""
    import matplotlib.pyplot as plt

    matrix = cm.astype(np.float64)
    if normalize and matrix.sum() > 0:
        row_sums = matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        matrix = matrix / row_sums

    labels = [class_names.get(i, str(i)) for i in range(cm.shape[0])]
    n = len(labels)
    fig, ax = plt.subplots(figsize=(max(6, n * 0.55), max(5, n * 0.55)))
    im = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Predicted", fontweight="bold")
    ax.set_ylabel("True", fontweight="bold")
    ax.set_title("Confusion Matrix" + (" (normalized)" if normalize else ""))

    show_values = n <= 20
    if show_values:
        vmax = matrix.max() if matrix.size else 1
        for i in range(n):
            for j in range(n):
                val = matrix[i, j]
                if val <= 0:
                    continue
                text = f"{val:.2f}" if normalize else str(int(val))
                ax.text(
                    j,
                    i,
                    text,
                    ha="center",
                    va="center",
                    color="white" if val > vmax / 2 else "black",
                    fontsize=7,
                )

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_error_analysis(
    cm_matrix: np.ndarray,
    false_positives: List[Tuple],
    false_negatives: List[Tuple],
    class_names: Sequence[str],
    output_dir: Path,
) -> str:
    import matplotlib.pyplot as plt
    import pandas as pd

    output_dir = Path(output_dir)
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

    cm_ext = np.zeros((num_classes + 1, num_classes + 1), dtype=int)
    cm_ext[:num_classes, :num_classes] = cm_matrix
    cm_ext[:num_classes, num_classes] = fn_by_class
    cm_ext[num_classes, :num_classes] = fp_by_class

    im1 = axes[0, 0].imshow(cm_ext, cmap="Blues", aspect="auto")
    ticks = list(range(num_classes + 1))
    labels = list(class_names) + ["FN"]
    axes[0, 0].set_xticks(ticks)
    axes[0, 0].set_yticks(ticks)
    axes[0, 0].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axes[0, 0].set_yticklabels(list(class_names) + ["FP"], fontsize=8)
    axes[0, 0].set_xlabel("Predicted", fontsize=10, fontweight="bold")
    axes[0, 0].set_ylabel("True", fontsize=10, fontweight="bold")
    axes[0, 0].set_title("Confusion Matrix (+FP/FN)", fontsize=12, fontweight="bold")
    plt.colorbar(im1, ax=axes[0, 0], fraction=0.046, pad=0.04)
    if num_classes <= 15:
        for i in range(num_classes + 1):
            for j in range(num_classes + 1):
                if cm_ext[i, j] > 0:
                    color = "white" if cm_ext[i, j] > cm_ext.max() / 2 else "black"
                    axes[0, 0].text(
                        j, i, str(cm_ext[i, j]), ha="center", va="center", color=color, fontsize=7
                    )

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
    axes[0, 1].set_yticklabels(list(class_names) + ["FP"], fontsize=8)
    axes[0, 1].set_xlabel("Predicted", fontsize=10, fontweight="bold")
    axes[0, 1].set_ylabel("True", fontsize=10, fontweight="bold")
    axes[0, 1].set_title("Normalized Confusion Matrix", fontsize=12, fontweight="bold")
    plt.colorbar(im2, ax=axes[0, 1], fraction=0.046, pad=0.04)

    error_df = pd.DataFrame({"Class": list(class_names), "FP": fp_by_class, "FN": fn_by_class})
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

    pairs = []
    for i in range(num_classes):
        for j in range(num_classes):
            if i != j and cm_matrix[i, j] > 0:
                pairs.append((i, j, int(cm_matrix[i, j])))
    pairs.sort(key=lambda x: x[2], reverse=True)
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

    plt.suptitle("Error Analysis", fontsize=16, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    path = output_dir / "error_analysis.png"
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def plot_performance_analysis(
    per_class: List[Dict],
    output_dir: Path,
) -> str:
    if not per_class:
        return ""

    import matplotlib.pyplot as plt
    import pandas as pd

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(per_class)
    if "f1_score" not in df.columns:
        return ""

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    df_sorted = df.sort_values("f1_score", ascending=True)

    x = np.arange(len(df_sorted))
    w = 0.25
    axes[0].barh(
        x + w,
        df_sorted["precision"],
        w,
        label="Precision",
        color=_TEAL,
        alpha=0.9,
        edgecolor="black",
        linewidth=0.3,
    )
    axes[0].barh(
        x,
        df_sorted["recall"],
        w,
        label="Recall",
        color=_GOLD,
        alpha=0.9,
        edgecolor="black",
        linewidth=0.3,
    )
    axes[0].barh(
        x - w,
        df_sorted["f1_score"],
        w,
        label="F1",
        color=_DARK_BLUE,
        alpha=0.9,
        edgecolor="black",
        linewidth=0.3,
    )
    axes[0].set_yticks(x)
    axes[0].set_yticklabels(df_sorted["class_name"], fontsize=8)
    axes[0].set_xlabel("Score", fontsize=12, fontweight="bold")
    axes[0].set_title("Per-class Precision / Recall / F1", fontsize=13, fontweight="bold")
    axes[0].set_xlim([0, 1.05])
    axes[0].legend(loc="lower right")
    axes[0].grid(True, alpha=0.2, axis="x")

    scatter = axes[1].scatter(
        df["recall"],
        df["precision"],
        s=df["f1_score"] * 300 + 30,
        c=df["f1_score"],
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        alpha=0.85,
        edgecolors="black",
        linewidth=0.8,
    )
    for _, row in df.iterrows():
        axes[1].annotate(
            str(row["class_name"])[:10],
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
        "Precision-Recall Balance (size/color = F1)",
        fontsize=13,
        fontweight="bold",
    )
    axes[1].set_xlim([0, 1.05])
    axes[1].set_ylim([0, 1.05])
    axes[1].grid(True, alpha=0.2)
    plt.colorbar(scatter, ax=axes[1], shrink=0.8, label="F1")

    plt.tight_layout()
    path = output_dir / "performance_analysis.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def plot_metrics_summary(metrics: Dict[str, float], output_dir: Path) -> str:
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(10, 5), tight_layout=True)

    items = {
        "Top-1": metrics.get("top1_accuracy", 0),
        "Top-k": metrics.get("top5_accuracy", 0),
        "Precision": metrics.get("precision_macro", 0),
        "Recall": metrics.get("recall_macro", 0),
        "F1": metrics.get("f1_macro", 0),
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
    ax.set_title("Evaluation Metrics Summary", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.2, axis="y")

    path = output_dir / "results.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path)


def plot_prediction_samples(
    samples: List[Dict],
    output_path: str,
    max_samples: int = 16,
) -> Optional[str]:
    """Grid of sample images with true vs predicted labels (errors preferred)."""
    if not samples:
        return None

    import matplotlib.pyplot as plt
    from PIL import Image

    wrong = [s for s in samples if s.get("true_id") != s.get("pred_id") or s.get("pred_id", -1) < 0]
    correct = [
        s for s in samples if s.get("true_id") == s.get("pred_id") and s.get("pred_id", -1) >= 0
    ]
    selected: List[Dict] = []
    half = max(max_samples // 2, 1)
    selected.extend(wrong[:half])
    remaining = max_samples - len(selected)
    selected.extend(correct[:remaining])
    if len(selected) < max_samples:
        leftovers = [s for s in samples if s not in selected]
        selected.extend(leftovers[: max_samples - len(selected)])
    samples = selected[:max_samples]

    cols = min(4, len(samples))
    rows = (len(samples) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
    axes = np.array(axes).reshape(-1)

    for ax in axes:
        ax.axis("off")

    for ax, sample in zip(axes, samples):
        try:
            img = Image.open(sample["image_path"]).convert("RGB")
        except Exception:
            continue
        ax.imshow(img)
        correct_pred = (
            sample.get("true_id") == sample.get("pred_id") and sample.get("pred_id", -1) >= 0
        )
        color = "green" if correct_pred else "red"
        pred_name = sample.get("pred_name") or ("abstain" if sample.get("pred_id", -1) < 0 else "?")
        ax.set_title(
            f"T:{sample.get('true_name')}\nP:{pred_name} ({sample.get('confidence', 0):.2f})",
            color=color,
            fontsize=8,
        )
        ax.axis("off")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path


def save_per_class_metrics(per_class: List[Dict], output_dir: Path) -> Tuple[str, str]:
    import pandas as pd

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "per_class_metrics.csv"
    json_path = output_dir / "per_class_metrics.json"
    pd.DataFrame(per_class).to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(per_class, f, indent=2)
    return str(csv_path), str(json_path)


def generate_evaluation_report(
    metrics: Dict,
    config: Dict,
    output_dir: Path,
) -> str:
    output_dir = Path(output_dir)
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
