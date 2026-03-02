"""Dataset analysis and visualization."""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Optional

import yaml

try:
    import cv2
    import matplotlib.pyplot as plt
    import numpy as np

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from nectar.ai.detection.datasets.format import FormatDetector

logger = logging.getLogger(__name__)

_GRAY = "#cecece"
_PURPLE = "#a559aa"
_TEAL = "#59a89c"
_GOLD = "#f0c571"
_RED = "#e02b35"
_DARK_BLUE = "#082a54"
_PALETTE = [_DARK_BLUE, _TEAL, _PURPLE, _GOLD, _RED, _GRAY]
_SPLIT_COLORS = {"train": _DARK_BLUE, "val": _GOLD, "test": _TEAL, "valid": _GOLD}


def _resolve_split_path(yaml_dir: Path, split_rel: str, split_name: str) -> Optional[Path]:
    candidate = (yaml_dir / split_rel).resolve()
    if candidate.exists():
        return candidate
    direct = yaml_dir / split_name / "images"
    if direct.exists():
        return direct
    if split_name == "val":
        alt = yaml_dir / "valid" / "images"
        if alt.exists():
            return alt
    return None


def _style_ax(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.15, color="#94a3b8")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


class DatasetAnalyzer:
    """Analyze dataset distribution and generate individual visualizations."""

    def __init__(self, dataset_path: str, output_dir: Optional[str] = None, verbose: bool = True):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir) if output_dir else self.dataset_path / "analysis"
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, msg: str) -> None:
        if self.verbose:
            logger.info(msg)

    def analyze(self) -> Dict:
        detector = FormatDetector(str(self.dataset_path))
        fmt = detector.detect()
        if fmt == "yolo":
            return self._analyze_yolo()
        elif fmt == "coco":
            return self._analyze_coco()
        raise ValueError(f"Unsupported format: {fmt}")

    def _analyze_yolo(self) -> Dict:
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path) as f:
            cfg = yaml.safe_load(f)

        class_names = cfg.get("names", {})
        if isinstance(class_names, list):
            class_names = {i: n for i, n in enumerate(class_names)}

        yaml_dir = yaml_path.parent
        results = {
            "format": "yolo",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
            "image_dims": [],
            "bbox_centers": [],
            "image_paths": [],
            "image_labels": [],
        }

        for split in ["train", "val", "test"]:
            if split not in cfg:
                continue

            images_dir = _resolve_split_path(yaml_dir, cfg[split], split)
            if images_dir is None:
                self._print(f"Split '{split}' path not found, skipping")
                continue

            labels_dir = images_dir.parent / "labels"
            if not labels_dir.exists():
                labels_dir = images_dir.parent.parent / "labels" / images_dir.name

            image_files = [
                p
                for p in sorted(images_dir.iterdir())
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            ]
            split_stats = {
                "images": len(image_files),
                "annotations": 0,
                "class_distribution": Counter(),
                "annotations_per_image": [],
                "bbox_sizes": [],
            }

            for img_path in image_files:
                try:
                    from PIL import Image as PILImage

                    with PILImage.open(img_path) as im:
                        w, h = im.size
                    results["image_dims"].append((w, h))
                except Exception:
                    results["image_dims"].append((0, 0))

                label_path = labels_dir / f"{img_path.stem}.txt"
                bboxes_for_img = []
                labels_for_img = []

                if not label_path.exists():
                    split_stats["annotations_per_image"].append(0)
                else:
                    try:
                        with open(label_path) as f:
                            lines = [ln.strip() for ln in f if ln.strip()]
                        split_stats["annotations"] += len(lines)
                        split_stats["annotations_per_image"].append(len(lines))
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 5:
                                cls_id = int(parts[0])
                                cx, cy, bw, bh = (float(x) for x in parts[1:5])
                                split_stats["class_distribution"][cls_id] += 1
                                split_stats["bbox_sizes"].append(bw * bh)
                                results["bbox_centers"].append((cx, cy))
                                bboxes_for_img.append((cx, cy, bw, bh))
                                labels_for_img.append(cls_id)
                    except Exception as e:
                        self._print(f"Warning: {label_path} - {e}")
                        split_stats["annotations_per_image"].append(0)

                results["image_paths"].append(str(img_path))
                results["image_labels"].append((bboxes_for_img, labels_for_img))

            results["splits"][split] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        self._generate_all_plots(results, class_names)
        self._save_report(results)
        return results

    def _analyze_coco(self) -> Dict:
        results = {
            "format": "coco",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
            "image_dims": [],
            "bbox_centers": [],
            "image_paths": [],
            "image_labels": [],
        }
        categories = {}

        for split_dir in sorted(self.dataset_path.iterdir()):
            if not split_dir.is_dir():
                continue
            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            with open(ann_file) as f:
                coco = json.load(f)

            if not categories:
                categories = {c["id"]: c["name"] for c in coco["categories"]}

            img_to_anns = defaultdict(list)
            for ann in coco["annotations"]:
                img_to_anns[ann["image_id"]].append(ann)

            split_stats = {
                "images": len(coco["images"]),
                "annotations": len(coco["annotations"]),
                "class_distribution": Counter(),
                "annotations_per_image": [],
                "bbox_sizes": [],
            }

            for img in coco["images"]:
                w, h = img.get("width", 1), img.get("height", 1)
                results["image_dims"].append((w, h))
                anns = img_to_anns.get(img["id"], [])
                split_stats["annotations_per_image"].append(len(anns))

                img_file = split_dir / img["file_name"]
                if not img_file.exists():
                    img_file = split_dir / "images" / img["file_name"]
                results["image_paths"].append(str(img_file))

                bboxes_for_img = []
                labels_for_img = []
                for ann in anns:
                    split_stats["class_distribution"][ann["category_id"]] += 1
                    bx, by, bw, bh = ann["bbox"]
                    split_stats["bbox_sizes"].append((bw * bh) / max(w * h, 1))
                    cx_norm = (bx + bw / 2) / max(w, 1)
                    cy_norm = (by + bh / 2) / max(h, 1)
                    results["bbox_centers"].append((cx_norm, cy_norm))
                    bboxes_for_img.append((cx_norm, cy_norm, bw / max(w, 1), bh / max(h, 1)))
                    labels_for_img.append(ann["category_id"])

                results["image_labels"].append((bboxes_for_img, labels_for_img))

            results["splits"][split_dir.name] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        self._generate_all_plots(results, categories)
        self._save_report(results)
        return results

    def _generate_all_plots(self, results: Dict, class_names: Dict) -> None:
        if not MATPLOTLIB_AVAILABLE:
            return

        class_ids = sorted(results["class_distribution"].keys())
        labels = [class_names.get(cid, f"class_{cid}") for cid in class_ids]
        splits = list(results["splits"].keys())

        self._plot_sample_mosaic(results, class_names)
        self._plot_class_distribution(results, class_ids, labels, splits)
        self._plot_annotation_heatmap(results)
        self._plot_dimension_insights(results)
        self._plot_bbox_size_distribution(results)
        self._plot_annotations_per_image(results, splits)

    def _plot_sample_mosaic(self, results: Dict, class_names: Dict) -> None:
        try:
            import supervision as sv
        except ImportError:
            self._print("supervision not available, skipping mosaic")
            return

        paths = results["image_paths"]
        all_labels = results["image_labels"]
        if not paths:
            return

        n = min(16, len(paths))
        indices = np.random.choice(len(paths), n, replace=False)
        cols = 4
        rows = (n + cols - 1) // cols
        cell_size = 320

        box_ann = sv.BoxAnnotator(thickness=2)
        label_ann = sv.LabelAnnotator(text_scale=0.4, text_thickness=1)

        cells = []
        for idx in indices:
            img = cv2.imread(paths[idx])
            if img is None:
                cells.append(np.zeros((cell_size, cell_size, 3), dtype=np.uint8))
                continue

            bboxes, cls_ids = all_labels[idx]
            if bboxes:
                h, w = img.shape[:2]
                xyxy = []
                for cx, cy, bw, bh in bboxes:
                    xyxy.append(
                        [
                            (cx - bw / 2) * w,
                            (cy - bh / 2) * h,
                            (cx + bw / 2) * w,
                            (cy + bh / 2) * h,
                        ]
                    )
                dets = sv.Detections(
                    xyxy=np.array(xyxy, dtype=np.float32),
                    class_id=np.array(cls_ids, dtype=int),
                )
                det_labels = [class_names.get(c, str(c)) for c in cls_ids]
                img = box_ann.annotate(img, dets)
                img = label_ann.annotate(img, dets, det_labels)

            cells.append(cv2.resize(img, (cell_size, cell_size), interpolation=cv2.INTER_AREA))

        while len(cells) < rows * cols:
            cells.append(np.zeros((cell_size, cell_size, 3), dtype=np.uint8))

        grid_rows = []
        for r in range(rows):
            row_cells = cells[r * cols : (r + 1) * cols]
            grid_rows.append(np.hstack(row_cells))
        mosaic = np.vstack(grid_rows)

        path = self.output_dir / "sample_mosaic.png"
        cv2.imwrite(str(path), mosaic)
        self._print(f"Saved: {path}")

    def _plot_class_distribution(self, results: Dict, class_ids, labels, splits) -> None:
        totals = [results["class_distribution"][cid] for cid in class_ids]
        sorted_idx = np.argsort(totals)[::-1]
        sorted_labels = [labels[i] for i in sorted_idx]
        sorted_ids = [class_ids[i] for i in sorted_idx]

        fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.45)))

        if len(splits) > 1:
            lefts = np.zeros(len(sorted_ids))
            for split_name in splits:
                split_dist = results["splits"][split_name]["class_distribution"]
                vals = np.array([split_dist.get(cid, 0) for cid in sorted_ids], dtype=float)
                color = _SPLIT_COLORS.get(split_name, _GRAY)
                ax.barh(
                    sorted_labels,
                    vals,
                    left=lefts,
                    label=split_name,
                    color=color,
                    edgecolor="white",
                    linewidth=0.3,
                )
                lefts += vals
            ax.legend(fontsize=9, framealpha=0.9)
            for i, total in enumerate(lefts):
                if total > 0:
                    ax.text(
                        total + max(lefts) * 0.01,
                        i,
                        f"{int(total):,}",
                        va="center",
                        fontsize=8,
                        color=_DARK_BLUE,
                    )
        else:
            sorted_totals = [totals[i] for i in sorted_idx]
            ax.barh(
                sorted_labels, sorted_totals, color=_DARK_BLUE, edgecolor="white", linewidth=0.3
            )
            for i, val in enumerate(sorted_totals):
                ax.text(
                    val + max(sorted_totals) * 0.01,
                    i,
                    f"{val:,}",
                    va="center",
                    fontsize=8,
                    color=_DARK_BLUE,
                )

        _style_ax(ax, "Class Distribution", "Annotations")
        plt.tight_layout()
        path = self.output_dir / "class_distribution.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _plot_annotation_heatmap(self, results: Dict) -> None:
        centers = results.get("bbox_centers", [])
        if not centers:
            return

        grid_size = 100
        heatmap = np.zeros((grid_size, grid_size))
        for cx, cy in centers:
            gx = min(int(cx * grid_size), grid_size - 1)
            gy = min(int(cy * grid_size), grid_size - 1)
            if 0 <= gx < grid_size and 0 <= gy < grid_size:
                heatmap[gy, gx] += 1

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(heatmap, cmap="managua", aspect="equal", interpolation="lanczos")
        ax.set_xticks([0, grid_size // 2, grid_size - 1])
        ax.set_xticklabels(["0", "0.5", "1.0"])
        ax.set_yticks([0, grid_size // 2, grid_size - 1])
        ax.set_yticklabels(["0", "0.5", "1.0"])
        _style_ax(ax, "Annotation Center Heatmap", "X (normalized)", "Y (normalized)")
        ax.spines["left"].set_visible(True)
        ax.spines["bottom"].set_visible(True)
        plt.colorbar(im, ax=ax, label="Count", shrink=0.85)
        plt.tight_layout()
        path = self.output_dir / "annotation_heatmap.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _plot_dimension_insights(self, results: Dict) -> None:
        dims = results.get("image_dims", [])
        dims = [(w, h) for w, h in dims if w > 0 and h > 0]
        if not dims:
            return

        widths = np.array([d[0] for d in dims])
        heights = np.array([d[1] for d in dims])
        aspects = widths / np.maximum(heights, 1)

        fig, ax = plt.subplots(figsize=(10, 7))
        scatter = ax.scatter(
            widths, heights, c=aspects, cmap="managua", alpha=0.5, s=15, edgecolors="none"
        )

        med_w = np.median(widths)
        med_h = np.median(heights)
        ax.axvline(med_w, color=_PURPLE, linestyle="--", linewidth=1, alpha=0.7)
        ax.axhline(med_h, color=_PURPLE, linestyle="--", linewidth=1, alpha=0.7)

        # Ensure axis range has padding so points aren't crushed when dimensions are uniform
        w_range = widths.max() - widths.min()
        h_range = heights.max() - heights.min()
        w_pad = max(w_range * 0.3, med_w * 0.1, 20)
        h_pad = max(h_range * 0.3, med_h * 0.1, 20)
        ax.set_xlim(widths.min() - w_pad, widths.max() + w_pad)
        ax.set_ylim(heights.min() - h_pad, heights.max() + h_pad)

        ax.text(
            med_w + w_pad * 0.05,
            ax.get_ylim()[1] - h_pad * 0.1,
            f"Median W: {int(med_w)} px",
            fontsize=9,
            color=_PURPLE,
            va="top",
        )
        ax.text(
            ax.get_xlim()[1] - w_pad * 0.1,
            med_h + h_pad * 0.05,
            f"Median H: {int(med_h)} px",
            fontsize=9,
            color=_PURPLE,
            ha="right",
        )

        _style_ax(ax, "Image Dimensions", "Width (px)", "Height (px)")
        plt.colorbar(scatter, ax=ax, label="Aspect Ratio (W/H)", shrink=0.85)
        plt.tight_layout()
        path = self.output_dir / "dimension_insights.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _plot_bbox_size_distribution(self, results: Dict) -> None:
        all_sizes = []
        for stats in results["splits"].values():
            all_sizes.extend(stats.get("bbox_sizes", []))
        sizes = np.array([s for s in all_sizes if s > 0]) if all_sizes else np.array([])
        if len(sizes) == 0:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(sizes, bins=60, color=_TEAL, alpha=0.85, edgecolor="white", linewidth=0.3)
        med = np.median(sizes)
        ax.axvline(med, color=_RED, linestyle="--", linewidth=1.5)
        ax.text(
            med, ax.get_ylim()[1] * 0.95, f"  Median: {med:.4f}", fontsize=9, color=_RED, va="top"
        )

        is_coco = results["format"] == "coco"
        xlabel = (
            "Relative BBox Area (bbox_area / image_area)"
            if is_coco
            else "BBox Area (w × h, normalized)"
        )
        _style_ax(ax, "Bounding Box Size Distribution", xlabel, "Frequency")
        plt.tight_layout()
        path = self.output_dir / "bbox_size_distribution.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _plot_annotations_per_image(self, results: Dict, splits) -> None:
        all_api = []
        for stats in results["splits"].values():
            all_api.extend(stats.get("annotations_per_image", []))
        if not all_api:
            return

        api = np.array(all_api)
        null_count = int(np.sum(api == 0))
        mean_val = np.mean(api)
        med_val = np.median(api)

        fig, ax = plt.subplots(figsize=(10, 5))
        max_bin = int(np.percentile(api[api > 0], 99)) + 1 if np.any(api > 0) else 10
        ax.hist(
            api,
            bins=min(60, max_bin),
            color=_DARK_BLUE,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.3,
        )
        ax.axvline(
            mean_val, color=_RED, linestyle="--", linewidth=1.2, label=f"Mean: {mean_val:.1f}"
        )
        ax.axvline(
            med_val, color=_TEAL, linestyle="--", linewidth=1.2, label=f"Median: {med_val:.1f}"
        )

        ax.text(
            0.97,
            0.95,
            f"{null_count:,} images with 0 annotations ({null_count / len(api) * 100:.1f}%)",
            transform=ax.transAxes,
            fontsize=9,
            ha="right",
            va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=_GRAY, edgecolor=_DARK_BLUE, alpha=0.5),
        )

        ax.legend(fontsize=9, framealpha=0.9)
        _style_ax(ax, "Annotations per Image", "Number of Annotations", "Number of Images")
        plt.tight_layout()
        path = self.output_dir / "annotations_per_image.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _save_report(self, results: Dict) -> None:
        report = {
            "dataset_path": str(self.dataset_path),
            "format": results["format"],
            "total_images": results["total_images"],
            "total_annotations": results["total_annotations"],
            "null_images": sum(
                1
                for stats in results["splits"].values()
                for n in stats.get("annotations_per_image", [])
                if n == 0
            ),
            "splits": {},
        }
        for name, stats in results["splits"].items():
            api = stats.get("annotations_per_image", [])
            report["splits"][name] = {
                "images": stats["images"],
                "annotations": stats["annotations"],
                "avg_annotations_per_image": sum(api) / len(api) if api else 0,
                "null_images": sum(1 for n in api if n == 0),
                "class_distribution": dict(stats["class_distribution"]),
            }
        report["total_class_distribution"] = dict(results["class_distribution"])

        dims = [(w, h) for w, h in results.get("image_dims", []) if w > 0]
        if dims:
            ws = [d[0] for d in dims]
            hs = [d[1] for d in dims]
            report["image_dimensions"] = {
                "median_width": int(np.median(ws)),
                "median_height": int(np.median(hs)),
                "min_width": int(min(ws)),
                "max_width": int(max(ws)),
                "min_height": int(min(hs)),
                "max_height": int(max(hs)),
            }

        with open(self.output_dir / "analysis_report.json", "w") as f:
            json.dump(report, f, indent=2)
        self._print(f"Report saved to: {self.output_dir / 'analysis_report.json'}")
