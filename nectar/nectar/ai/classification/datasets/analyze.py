"""Classification dataset analysis."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from nectar.ai.classification.datasets.format import ImageFolderDetector

logger = logging.getLogger(__name__)


class ClsDatasetAnalyzer:
    """Analyze ImageFolder classification datasets."""

    def __init__(self, dataset_path: str, output_dir: Optional[str] = None):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir) if output_dir else self.dataset_path / "analysis"
        self.detector = ImageFolderDetector(str(self.dataset_path))

    def analyze(self) -> Dict[str, Any]:
        """Compute class distribution stats and optionally write JSON/plots."""
        if not self.detector.is_imagefolder():
            raise ValueError(f"Not an ImageFolder dataset: {self.dataset_path}")

        counts = self.detector.count_samples()
        results: Dict[str, Any] = {
            "dataset_path": str(self.dataset_path),
            "format": "imagefolder",
            "splits": {},
        }

        for split, class_counts in counts.items():
            total = sum(class_counts.values())
            results["splits"][split] = {
                "num_images": total,
                "num_classes": len(class_counts),
                "per_class": class_counts,
                "imbalance_ratio": (
                    max(class_counts.values()) / max(min(class_counts.values()), 1)
                    if class_counts
                    else 0.0
                ),
            }

        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_json = self.output_dir / "dataset_analysis.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info("Wrote analysis to %s", out_json)

        try:
            self._plot_distribution(counts)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not plot distribution: %s", e)

        return results

    def _plot_distribution(self, counts: Dict[str, Dict[str, int]]) -> None:
        import matplotlib.pyplot as plt

        for split, class_counts in counts.items():
            if not class_counts:
                continue
            names = list(class_counts.keys())
            values = list(class_counts.values())
            fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.4), 4))
            ax.bar(names, values)
            ax.set_title(f"Class distribution — {split}")
            ax.set_ylabel("Images")
            ax.tick_params(axis="x", rotation=90)
            fig.tight_layout()
            out = self.output_dir / f"class_distribution_{split}.png"
            fig.savefig(out, dpi=120)
            plt.close(fig)
            logger.info("Wrote %s", out)
