"""Dataset analysis and visualization utilities."""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Optional

import yaml

try:
    import matplotlib.pyplot as plt
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from nectar.ai.detection.datasets.format import FormatDetector

logger = logging.getLogger(__name__)


class DatasetAnalyzer:
    """
    Analyze dataset distribution and generate visualizations.

    Parameters
    ----------
    dataset_path : str
        Path to dataset directory.
    output_dir : str, optional
        Directory for analysis outputs. Defaults to dataset_path/analysis.
    verbose : bool, optional
        Print progress information. Defaults to True.
    """

    def __init__(
        self,
        dataset_path: str,
        output_dir: Optional[str] = None,
        verbose: bool = True,
    ):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir) if output_dir else self.dataset_path / "analysis"
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def analyze(self) -> Dict:
        """
        Analyze dataset and generate reports.

        Returns
        -------
        Dict
            Analysis results with statistics and plot paths.
        """
        detector = FormatDetector(str(self.dataset_path))
        format_type = detector.detect()

        if format_type == "yolo":
            return self._analyze_yolo()
        elif format_type == "coco":
            return self._analyze_coco()
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _analyze_yolo(self) -> Dict:
        """Analyze YOLO format dataset."""
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path) as f:
            dataset_config = yaml.safe_load(f)

        class_names = dataset_config.get("names", {})
        if isinstance(class_names, list):
            class_names = {i: name for i, name in enumerate(class_names)}

        yaml_dir = yaml_path.parent
        results = {
            "format": "yolo",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
        }

        for split in ["train", "val", "test"]:
            if split not in dataset_config:
                continue

            split_path = yaml_dir / dataset_config[split]
            if not split_path.exists():
                continue

            images_dir = split_path
            labels_dir = split_path.parent / "labels"

            if not images_dir.exists():
                continue

            image_files = list(images_dir.glob("*.*"))
            split_stats = {
                "images": len(image_files),
                "annotations": 0,
                "class_distribution": Counter(),
                "annotations_per_image": [],
            }

            for img_path in image_files:
                label_path = labels_dir / f"{img_path.stem}.txt"
                if not label_path.exists():
                    continue

                try:
                    with open(label_path) as f:
                        lines = f.readlines()
                    num_anns = len([l for l in lines if l.strip()])
                    split_stats["annotations"] += num_anns
                    split_stats["annotations_per_image"].append(num_anns)

                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            class_id = int(parts[0])
                            split_stats["class_distribution"][class_id] += 1
                except Exception as e:
                    self._print(f"Warning: {label_path} - {e}")

            results["splits"][split] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        self._generate_plots_yolo(results, class_names)
        self._save_report(results)

        return results

    def _analyze_coco(self) -> Dict:
        """Analyze COCO format dataset."""
        results = {
            "format": "coco",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
        }

        for split_dir in self.dataset_path.iterdir():
            if not split_dir.is_dir():
                continue

            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            split = split_dir.name
            with open(ann_file) as f:
                coco_data = json.load(f)

            split_stats = {
                "images": len(coco_data["images"]),
                "annotations": len(coco_data["annotations"]),
                "class_distribution": Counter(),
                "annotations_per_image": [],
            }

            image_id_to_anns = defaultdict(list)
            for ann in coco_data["annotations"]:
                image_id_to_anns[ann["image_id"]].append(ann)
                split_stats["class_distribution"][ann["category_id"]] += 1

            for img in coco_data["images"]:
                num_anns = len(image_id_to_anns.get(img["id"], []))
                split_stats["annotations_per_image"].append(num_anns)

            results["splits"][split] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        categories = {}
        for split_dir in self.dataset_path.iterdir():
            ann_file = split_dir / "_annotations.coco.json"
            if ann_file.exists():
                with open(ann_file) as f:
                    coco_data = json.load(f)
                for cat in coco_data["categories"]:
                    categories[cat["id"]] = cat["name"]
                break

        self._generate_plots_coco(results, categories)
        self._save_report(results)

        return results

    def _generate_plots_yolo(self, results: Dict, class_names: Dict) -> None:
        """Generate plots for YOLO dataset."""
        if not MATPLOTLIB_AVAILABLE:
            self._print("matplotlib not available, skipping plots")
            return

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle("Dataset Analysis", fontsize=16)

        class_ids = sorted(results["class_distribution"].keys())
        class_labels = [class_names.get(cid, f"class_{cid}") for cid in class_ids]
        class_counts = [results["class_distribution"][cid] for cid in class_ids]

        axes[0, 0].barh(class_labels, class_counts)
        axes[0, 0].set_title("Class Distribution (Total)")
        axes[0, 0].set_xlabel("Count")

        split_names = list(results["splits"].keys())
        split_counts = [results["splits"][s]["images"] for s in split_names]
        axes[0, 1].bar(split_names, split_counts)
        axes[0, 1].set_title("Images per Split")
        axes[0, 1].set_ylabel("Count")

        all_anns_per_img = []
        for split_stats in results["splits"].values():
            all_anns_per_img.extend(split_stats["annotations_per_image"])

        if all_anns_per_img:
            axes[1, 0].hist(all_anns_per_img, bins=20, edgecolor="black")
            axes[1, 0].set_title("Annotations per Image")
            axes[1, 0].set_xlabel("Number of Annotations")
            axes[1, 0].set_ylabel("Frequency")

        split_class_data = {}
        for split_name, split_stats in results["splits"].items():
            split_class_data[split_name] = [
                split_stats["class_distribution"][cid] for cid in class_ids
            ]

        if split_class_data:
            x = np.arange(len(class_ids))
            width = 0.8 / len(split_class_data)
            for i, (split_name, counts) in enumerate(split_class_data.items()):
                axes[1, 1].bar(x + i * width, counts, width, label=split_name)
            axes[1, 1].set_title("Class Distribution by Split")
            axes[1, 1].set_xlabel("Class")
            axes[1, 1].set_ylabel("Count")
            axes[1, 1].set_xticks(x + width * (len(split_class_data) - 1) / 2)
            axes[1, 1].set_xticklabels(class_labels, rotation=45, ha="right")
            axes[1, 1].legend()

        plt.tight_layout()
        plot_path = self.output_dir / "analysis_plots.png"
        plt.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close()

        self._print(f"Plots saved to: {plot_path}")

    def _generate_plots_coco(self, results: Dict, categories: Dict) -> None:
        """Generate plots for COCO dataset."""
        if not MATPLOTLIB_AVAILABLE:
            self._print("matplotlib not available, skipping plots")
            return

        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle("Dataset Analysis", fontsize=16)

        class_ids = sorted(results["class_distribution"].keys())
        class_labels = [categories.get(cid, f"class_{cid}") for cid in class_ids]
        class_counts = [results["class_distribution"][cid] for cid in class_ids]

        axes[0, 0].barh(class_labels, class_counts)
        axes[0, 0].set_title("Class Distribution (Total)")
        axes[0, 0].set_xlabel("Count")

        split_names = list(results["splits"].keys())
        split_counts = [results["splits"][s]["images"] for s in split_names]
        axes[0, 1].bar(split_names, split_counts)
        axes[0, 1].set_title("Images per Split")
        axes[0, 1].set_ylabel("Count")

        all_anns_per_img = []
        for split_stats in results["splits"].values():
            all_anns_per_img.extend(split_stats["annotations_per_image"])

        if all_anns_per_img:
            axes[1, 0].hist(all_anns_per_img, bins=20, edgecolor="black")
            axes[1, 0].set_title("Annotations per Image")
            axes[1, 0].set_xlabel("Number of Annotations")
            axes[1, 0].set_ylabel("Frequency")

        split_class_data = {}
        for split_name, split_stats in results["splits"].items():
            split_class_data[split_name] = [
                split_stats["class_distribution"][cid] for cid in class_ids
            ]

        if split_class_data:
            x = np.arange(len(class_ids))
            width = 0.8 / len(split_class_data)
            for i, (split_name, counts) in enumerate(split_class_data.items()):
                axes[1, 1].bar(x + i * width, counts, width, label=split_name)
            axes[1, 1].set_title("Class Distribution by Split")
            axes[1, 1].set_xlabel("Class")
            axes[1, 1].set_ylabel("Count")
            axes[1, 1].set_xticks(x + width * (len(split_class_data) - 1) / 2)
            axes[1, 1].set_xticklabels(class_labels, rotation=45, ha="right")
            axes[1, 1].legend()

        plt.tight_layout()
        plot_path = self.output_dir / "analysis_plots.png"
        plt.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close()

        self._print(f"Plots saved to: {plot_path}")

    def _save_report(self, results: Dict) -> None:
        """Save analysis report to JSON."""
        report_path = self.output_dir / "analysis_report.json"

        report = {
            "dataset_path": str(self.dataset_path),
            "format": results["format"],
            "total_images": results["total_images"],
            "total_annotations": results["total_annotations"],
            "splits": {},
        }

        for split_name, split_stats in results["splits"].items():
            report["splits"][split_name] = {
                "images": split_stats["images"],
                "annotations": split_stats["annotations"],
                "avg_annotations_per_image": (
                    sum(split_stats["annotations_per_image"])
                    / len(split_stats["annotations_per_image"])
                    if split_stats["annotations_per_image"]
                    else 0
                ),
                "class_distribution": dict(split_stats["class_distribution"]),
            }

        report["total_class_distribution"] = dict(results["class_distribution"])

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        self._print(f"Report saved to: {report_path}")
