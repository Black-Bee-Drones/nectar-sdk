"""Segmentation dataset analysis and visualization."""

import importlib.util
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

from nectar.ai.detection.datasets.format import FormatDetector

MATPLOTLIB_AVAILABLE = importlib.util.find_spec("matplotlib") is not None

logger = logging.getLogger(__name__)

_DARK_BLUE = "#082a54"
_TEAL = "#59a89c"
_PURPLE = "#a559aa"
_GOLD = "#f0c571"
_RED = "#e02b35"
_GRAY = "#cecece"
_SPLIT_COLORS = {"train": _DARK_BLUE, "val": _GOLD, "test": _TEAL, "valid": _GOLD}


def _style_ax(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(True, alpha=0.15, color="#94a3b8")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


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


def _polygon_area_from_flat(flat: List[float]) -> float:
    """Shoelace area from a flat [x1,y1,x2,y2,...] list."""
    n = len(flat) // 2
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += flat[2 * i] * flat[2 * j + 1]
        area -= flat[2 * j] * flat[2 * i + 1]
    return abs(area) / 2.0


class SegDatasetAnalyzer:
    """
    Analyze segmentation dataset distribution and generate visualizations.

    Supports both YOLO-seg (polygon labels) and COCO (with segmentation field).

    Parameters
    ----------
    dataset_path : str
        Path to dataset directory.
    output_dir : str, optional
        Output directory for reports and plots.
    verbose : bool
        Print progress information.
    """

    def __init__(self, dataset_path: str, output_dir: Optional[str] = None, verbose: bool = True):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir) if output_dir else self.dataset_path / "analysis"
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, msg: str) -> None:
        if self.verbose:
            logger.info(msg)

    def analyze(self) -> Dict:
        """
        Run analysis and generate plots + JSON report.

        Returns
        -------
        dict
            Analysis results.
        """
        detector = FormatDetector(str(self.dataset_path))
        fmt = detector.detect()
        if fmt == "yolo":
            return self._analyze_yolo_seg()
        elif fmt == "coco":
            return self._analyze_coco_seg()
        raise ValueError(f"Unsupported format: {fmt}")

    # ------------------------------------------------------------------
    # YOLO-seg analysis
    # ------------------------------------------------------------------

    def _analyze_yolo_seg(self) -> Dict:
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        class_names = cfg.get("names", {})
        if isinstance(class_names, list):
            class_names = {i: n for i, n in enumerate(class_names)}

        yaml_dir = yaml_path.parent
        results: Dict = {
            "format": "yolo-seg",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
            "image_dims": [],
            "mask_areas": [],
            "image_paths": [],
            "image_polygons": [],
        }

        for split in ("train", "val", "test"):
            if split not in cfg:
                continue

            images_dir = _resolve_split_path(yaml_dir, cfg[split], split)
            if images_dir is None:
                self._print(f"Split '{split}' not found, skipping")
                continue

            labels_dir = images_dir.parent / "labels"
            if not labels_dir.exists():
                labels_dir = images_dir.parent.parent / "labels" / images_dir.name

            image_files = sorted(
                p
                for p in images_dir.iterdir()
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            )

            split_stats: Dict = {
                "images": len(image_files),
                "annotations": 0,
                "class_distribution": Counter(),
                "annotations_per_image": [],
                "mask_areas": [],
            }

            for img_path in image_files:
                try:
                    from PIL import Image as PILImage

                    with PILImage.open(img_path) as im:
                        w, h = im.size
                    results["image_dims"].append((w, h))
                except Exception:
                    w, h = 0, 0
                    results["image_dims"].append((0, 0))

                label_path = labels_dir / f"{img_path.stem}.txt"
                polygons_for_img: List[Tuple] = []

                if not label_path.exists():
                    split_stats["annotations_per_image"].append(0)
                else:
                    try:
                        with open(label_path, encoding="utf-8") as f:
                            lines = [ln.strip() for ln in f if ln.strip()]
                        count = 0
                        for line in lines:
                            parts = line.split()
                            if len(parts) < 7:
                                continue
                            cls_id = int(parts[0])
                            coords = [float(v) for v in parts[1:]]
                            if len(coords) % 2 != 0:
                                coords = coords[:-1]

                            if w > 0 and h > 0:
                                abs_coords = []
                                for i in range(0, len(coords), 2):
                                    abs_coords.extend([coords[i] * w, coords[i + 1] * h])
                                area = _polygon_area_from_flat(abs_coords)
                                rel_area = area / (w * h) if (w * h) > 0 else 0.0
                            else:
                                rel_area = 0.0

                            split_stats["class_distribution"][cls_id] += 1
                            split_stats["mask_areas"].append(rel_area)
                            results["mask_areas"].append(rel_area)
                            polygons_for_img.append((cls_id, coords))
                            count += 1

                        split_stats["annotations"] += count
                        split_stats["annotations_per_image"].append(count)
                    except Exception as e:
                        self._print(f"Warning: {label_path} - {e}")
                        split_stats["annotations_per_image"].append(0)

                results["image_paths"].append(str(img_path))
                results["image_polygons"].append(polygons_for_img)

            results["splits"][split] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        self._generate_all_plots(results, class_names)
        self._save_report(results)
        return results

    # ------------------------------------------------------------------
    # COCO-seg analysis
    # ------------------------------------------------------------------

    def _analyze_coco_seg(self) -> Dict:
        results: Dict = {
            "format": "coco-seg",
            "splits": {},
            "total_images": 0,
            "total_annotations": 0,
            "class_distribution": Counter(),
            "image_dims": [],
            "mask_areas": [],
            "image_paths": [],
            "image_polygons": [],
        }
        categories: Dict[int, str] = {}

        for split_dir in sorted(self.dataset_path.iterdir()):
            if not split_dir.is_dir():
                continue
            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            with open(ann_file, encoding="utf-8") as f:
                coco = json.load(f)

            if not categories:
                categories = {c["id"]: c["name"] for c in coco["categories"]}

            img_to_anns = defaultdict(list)
            for ann in coco["annotations"]:
                img_to_anns[ann["image_id"]].append(ann)

            split_stats: Dict = {
                "images": len(coco["images"]),
                "annotations": len(coco["annotations"]),
                "class_distribution": Counter(),
                "annotations_per_image": [],
                "mask_areas": [],
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

                polys_for_img: List[Tuple] = []
                for ann in anns:
                    split_stats["class_distribution"][ann["category_id"]] += 1

                    seg = ann.get("segmentation", [])
                    if seg and isinstance(seg, list) and isinstance(seg[0], list):
                        flat = seg[0]
                        area = _polygon_area_from_flat(flat)
                        rel_area = area / (w * h) if (w * h) > 0 else 0.0
                        norm_coords = []
                        for i in range(0, len(flat), 2):
                            norm_coords.extend([flat[i] / w, flat[i + 1] / h])
                        polys_for_img.append((ann["category_id"], norm_coords))
                    else:
                        rel_area = ann.get("area", 0.0) / (w * h) if (w * h) > 0 else 0.0

                    split_stats["mask_areas"].append(rel_area)
                    results["mask_areas"].append(rel_area)

                results["image_polygons"].append(polys_for_img)

            results["splits"][split_dir.name] = split_stats
            results["total_images"] += split_stats["images"]
            results["total_annotations"] += split_stats["annotations"]
            results["class_distribution"].update(split_stats["class_distribution"])

        self._generate_all_plots(results, categories)
        self._save_report(results)
        return results

    # ------------------------------------------------------------------
    # Visualizations
    # ------------------------------------------------------------------

    def _generate_all_plots(self, results: Dict, class_names: Dict) -> None:
        if not MATPLOTLIB_AVAILABLE:
            self._print("matplotlib not available, skipping plots")
            return

        class_ids = sorted(results["class_distribution"].keys())
        labels = [class_names.get(cid, f"class_{cid}") for cid in class_ids]
        splits = list(results["splits"].keys())

        self._plot_sample_mosaic(results, class_names)
        self._plot_class_distribution(results, class_ids, labels, splits)
        self._plot_mask_area_distribution(results)
        self._plot_annotations_per_image(results, splits)
        self._plot_dimension_insights(results)

    def _plot_sample_mosaic(self, results: Dict, class_names: Dict) -> None:
        if not MATPLOTLIB_AVAILABLE:
            return
        try:
            import supervision as sv
        except ImportError:
            self._print("supervision not available, skipping mosaic")
            return

        paths = results["image_paths"]
        all_polygons = results["image_polygons"]
        if not paths:
            return

        n = min(16, len(paths))
        indices = np.random.choice(len(paths), n, replace=False)
        cols = 4
        rows = (n + cols - 1) // cols
        cell_size = 320

        cells = []
        for idx in indices:
            img = cv2.imread(paths[idx])
            if img is None:
                cells.append(np.zeros((cell_size, cell_size, 3), dtype=np.uint8))
                continue

            polys = all_polygons[idx]
            h_img, w_img = img.shape[:2]

            if polys:
                xyxy_list = []
                class_id_list = []
                mask_list = []

                for cls_id, coords in polys:
                    pts_abs = []
                    for i in range(0, len(coords), 2):
                        px = int(coords[i] * w_img)
                        py = int(coords[i + 1] * h_img)
                        pts_abs.append([px, py])
                    pts = np.array(pts_abs, dtype=np.int32)

                    mask = np.zeros((h_img, w_img), dtype=np.uint8)
                    cv2.fillPoly(mask, [pts], 1)
                    mask_bool = mask.astype(bool)

                    ys, xs = np.where(mask_bool)
                    if len(xs) == 0:
                        continue
                    x1, y1, x2, y2 = xs.min(), ys.min(), xs.max(), ys.max()

                    xyxy_list.append([x1, y1, x2, y2])
                    class_id_list.append(cls_id)
                    mask_list.append(mask_bool)

                if xyxy_list:
                    dets = sv.Detections(
                        xyxy=np.array(xyxy_list, dtype=np.float32),
                        class_id=np.array(class_id_list, dtype=int),
                        mask=np.array(mask_list),
                    )
                    det_labels = [class_names.get(c, str(c)) for c in class_id_list]

                    mask_ann = sv.MaskAnnotator(opacity=0.4)
                    img = mask_ann.annotate(scene=img, detections=dets)
                    label_ann = sv.LabelAnnotator(text_scale=0.4, text_thickness=1)
                    img = label_ann.annotate(scene=img, detections=dets, labels=det_labels)

            cells.append(cv2.resize(img, (cell_size, cell_size), interpolation=cv2.INTER_AREA))

        while len(cells) < rows * cols:
            cells.append(np.zeros((cell_size, cell_size, 3), dtype=np.uint8))

        grid_rows = []
        for r in range(rows):
            grid_rows.append(np.hstack(cells[r * cols : (r + 1) * cols]))
        mosaic = np.vstack(grid_rows)

        path = self.output_dir / "sample_mosaic.png"
        cv2.imwrite(str(path), mosaic)
        self._print(f"Saved: {path}")

    def _plot_class_distribution(self, results: Dict, class_ids, labels, splits) -> None:
        import matplotlib.pyplot as plt

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

    def _plot_mask_area_distribution(self, results: Dict) -> None:
        areas = np.array([a for a in results.get("mask_areas", []) if a > 0])
        if len(areas) == 0:
            return

        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(areas, bins=60, color=_TEAL, alpha=0.85, edgecolor="white", linewidth=0.3)
        med = float(np.median(areas))
        ax.axvline(med, color=_RED, linestyle="--", linewidth=1.5)
        ax.text(
            med, ax.get_ylim()[1] * 0.95, f"  Median: {med:.4f}", fontsize=9, color=_RED, va="top"
        )

        _style_ax(ax, "Mask Area Distribution", "Relative Area (mask / image)", "Frequency")
        plt.tight_layout()
        path = self.output_dir / "mask_area_distribution.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    def _plot_annotations_per_image(self, results: Dict, splits) -> None:
        all_api = []
        for stats in results["splits"].values():
            all_api.extend(stats.get("annotations_per_image", []))
        if not all_api:
            return

        import matplotlib.pyplot as plt

        api = np.array(all_api)
        null_count = int(np.sum(api == 0))
        mean_val = float(np.mean(api))
        med_val = float(np.median(api))

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

        pct = null_count / len(api) * 100 if len(api) > 0 else 0
        ax.text(
            0.97,
            0.95,
            f"{null_count:,} images with 0 annotations ({pct:.1f}%)",
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

    def _plot_dimension_insights(self, results: Dict) -> None:
        dims = [(w, h) for w, h in results.get("image_dims", []) if w > 0 and h > 0]
        if not dims:
            return

        import matplotlib.pyplot as plt

        widths = np.array([d[0] for d in dims])
        heights = np.array([d[1] for d in dims])
        aspects = widths / np.maximum(heights, 1)

        fig, ax = plt.subplots(figsize=(10, 7))
        scatter = ax.scatter(
            widths, heights, c=aspects, cmap="viridis", alpha=0.5, s=15, edgecolors="none"
        )
        med_w, med_h = float(np.median(widths)), float(np.median(heights))
        ax.axvline(med_w, color=_PURPLE, linestyle="--", linewidth=1, alpha=0.7)
        ax.axhline(med_h, color=_PURPLE, linestyle="--", linewidth=1, alpha=0.7)

        w_range = widths.max() - widths.min()
        h_range = heights.max() - heights.min()
        w_pad = max(w_range * 0.3, med_w * 0.1, 20)
        h_pad = max(h_range * 0.3, med_h * 0.1, 20)
        ax.set_xlim(widths.min() - w_pad, widths.max() + w_pad)
        ax.set_ylim(heights.min() - h_pad, heights.max() + h_pad)

        _style_ax(ax, "Image Dimensions", "Width (px)", "Height (px)")
        plt.colorbar(scatter, ax=ax, label="Aspect Ratio (W/H)", shrink=0.85)
        plt.tight_layout()
        path = self.output_dir / "dimension_insights.png"
        plt.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        self._print(f"Saved: {path}")

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _save_report(self, results: Dict) -> None:
        report: Dict = {
            "dataset_path": str(self.dataset_path),
            "format": results["format"],
            "total_images": results["total_images"],
            "total_annotations": results["total_annotations"],
            "splits": {},
        }

        for name, stats in results["splits"].items():
            api = stats.get("annotations_per_image", [])
            areas = stats.get("mask_areas", [])
            report["splits"][name] = {
                "images": stats["images"],
                "annotations": stats["annotations"],
                "avg_annotations_per_image": sum(api) / len(api) if api else 0,
                "null_images": sum(1 for n in api if n == 0),
                "class_distribution": dict(stats["class_distribution"]),
                "mask_area_stats": {
                    "mean": float(np.mean(areas)) if areas else 0,
                    "median": float(np.median(areas)) if areas else 0,
                    "min": float(min(areas)) if areas else 0,
                    "max": float(max(areas)) if areas else 0,
                },
            }

        report["total_class_distribution"] = dict(results["class_distribution"])

        all_areas = results.get("mask_areas", [])
        if all_areas:
            report["mask_area_stats"] = {
                "mean": float(np.mean(all_areas)),
                "median": float(np.median(all_areas)),
                "min": float(min(all_areas)),
                "max": float(max(all_areas)),
            }

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

        out = self.output_dir / "analysis_report.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        self._print(f"Report saved to: {out}")
