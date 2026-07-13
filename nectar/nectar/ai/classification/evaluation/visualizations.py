"""Classification evaluation visualizations."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: Dict[int, str],
    output_path: str,
    normalize: bool = True,
) -> str:
    """Save a confusion matrix heatmap."""
    import matplotlib.pyplot as plt

    matrix = cm.astype(np.float64)
    if normalize and matrix.sum() > 0:
        row_sums = matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        matrix = matrix / row_sums

    labels = [class_names.get(i, str(i)) for i in range(cm.shape[0])]
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.5), max(5, len(labels) * 0.5)))
    im = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
    fig.colorbar(im, ax=ax)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=90)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Confusion Matrix" + (" (normalized)" if normalize else ""))
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path


def plot_per_class_bars(
    per_class: List[Dict],
    output_path: str,
    metric: str = "f1",
) -> str:
    """Bar chart of a per-class metric."""
    import matplotlib.pyplot as plt

    names = [row.get("class_name", str(row.get("class_id", ""))) for row in per_class]
    values = [float(row.get(metric, 0.0)) for row in per_class]
    fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.4), 4))
    ax.bar(names, values)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(metric)
    ax.set_title(f"Per-class {metric}")
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path


def plot_prediction_samples(
    samples: List[Dict],
    output_path: str,
    max_samples: int = 16,
) -> Optional[str]:
    """Grid of sample images with true vs predicted labels."""
    if not samples:
        return None

    import matplotlib.pyplot as plt
    from PIL import Image

    samples = samples[:max_samples]
    cols = min(4, len(samples))
    rows = (len(samples) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
    axes = np.array(axes).reshape(-1)

    for ax in axes:
        ax.axis("off")

    for ax, sample in zip(axes, samples):
        img = Image.open(sample["image_path"]).convert("RGB")
        ax.imshow(img)
        correct = sample.get("true_name") == sample.get("pred_name")
        color = "green" if correct else "red"
        ax.set_title(
            f"T:{sample.get('true_name')}\nP:{sample.get('pred_name')} "
            f"({sample.get('confidence', 0):.2f})",
            color=color,
            fontsize=8,
        )
        ax.axis("off")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path


def save_per_class_metrics(per_class: List[Dict], output_dir: str) -> Dict[str, str]:
    """Write per-class metrics as CSV and JSON."""
    import csv

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "per_class_metrics.json"
    csv_path = out / "per_class_metrics.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(per_class, f, indent=2)

    if per_class:
        keys = list(per_class[0].keys())
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(per_class)

    return {"json": str(json_path), "csv": str(csv_path)}


def generate_evaluation_report(metrics_dict: Dict, output_path: str) -> str:
    """Write a short markdown evaluation report."""
    lines = [
        "# Classification Evaluation Report",
        "",
        f"- Top-1 accuracy: **{metrics_dict.get('top1_accuracy', 0):.4f}**",
        f"- Top-5 accuracy: **{metrics_dict.get('top5_accuracy', 0):.4f}**",
        f"- Precision (macro): {metrics_dict.get('precision_macro', 0):.4f}",
        f"- Recall (macro): {metrics_dict.get('recall_macro', 0):.4f}",
        f"- F1 (macro): {metrics_dict.get('f1_macro', 0):.4f}",
        f"- Samples: {metrics_dict.get('total_samples', 0)}",
        f"- Inference time / image: {metrics_dict.get('inference_time_per_image', 0):.4f}s",
        "",
    ]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path
