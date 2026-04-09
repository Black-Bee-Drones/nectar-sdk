"""Segmentation dataset format conversion (YOLO-seg <-> COCO with masks)."""

import json
import logging
import os
import shutil
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)


def _polygon_area(xs: List[float], ys: List[float]) -> float:
    """Compute polygon area via the shoelace formula."""
    n = len(xs)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += xs[i] * ys[j]
        area -= xs[j] * ys[i]
    return abs(area) / 2.0


def _polygon_bbox(xs: List[float], ys: List[float]) -> Tuple[float, float, float, float]:
    """Compute bounding box [x, y, w, h] from polygon vertices (absolute coords)."""
    x_min, y_min = min(xs), min(ys)
    x_max, y_max = max(xs), max(ys)
    return (x_min, y_min, x_max - x_min, y_max - y_min)


def _process_yolo_seg_image_to_coco(args: Tuple) -> Optional[Dict]:
    """Worker: convert one YOLO-seg image + label to COCO annotation entries."""
    img_path_str, img_idx, labels_dir_str, target_split_str, copy_images = args

    try:
        img_path = Path(img_path_str)
        labels_dir = Path(labels_dir_str)
        target_split = Path(target_split_str)

        img_id = img_idx + 1

        with Image.open(img_path) as img:
            img_width, img_height = img.size

        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            return {
                "image": {
                    "id": img_id,
                    "file_name": img_path.name,
                    "width": img_width,
                    "height": img_height,
                },
                "annotations": [],
                "copy_success": False,
            }

        with open(label_path, encoding="utf-8") as f:
            lines = f.read().strip().split("\n")

        annotations = []
        for line in lines:
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) < 7:
                continue

            class_id = int(parts[0])
            coords = [float(v) for v in parts[1:]]
            if len(coords) % 2 != 0:
                coords = coords[:-1]

            xs_abs = [coords[i] * img_width for i in range(0, len(coords), 2)]
            ys_abs = [coords[i] * img_height for i in range(1, len(coords), 2)]

            flat_polygon = []
            for x, y in zip(xs_abs, ys_abs):
                flat_polygon.extend([round(x, 2), round(y, 2)])

            bbox = _polygon_bbox(xs_abs, ys_abs)
            area = _polygon_area(xs_abs, ys_abs)

            annotations.append(
                {
                    "image_id": img_id,
                    "category_id": class_id,
                    "segmentation": [flat_polygon],
                    "bbox": [round(v, 2) for v in bbox],
                    "area": round(area, 2),
                }
            )

        target_img = target_split / img_path.name
        copy_success = False
        if not target_img.exists():
            if copy_images:
                shutil.copy2(img_path, target_img)
            else:
                os.symlink(img_path.resolve(), target_img)
            copy_success = True

        return {
            "image": {
                "id": img_id,
                "file_name": img_path.name,
                "width": img_width,
                "height": img_height,
            },
            "annotations": annotations,
            "copy_success": copy_success,
        }
    except Exception as e:
        logger.warning("Error processing %s: %s", img_path_str, e)
        return None


def _process_coco_seg_image_to_yolo(args: Tuple) -> Optional[Tuple[str, Optional[str], bool]]:
    """Worker: convert one COCO-seg annotation set to a YOLO-seg label file."""
    (
        img_data,
        img_id,
        image_annotations,
        categories_dict,
        image_source_dir_str,
        target_labels_str,
        target_images_str,
        copy_images,
    ) = args

    try:
        image_source_dir = Path(image_source_dir_str)
        target_labels = Path(target_labels_str)
        target_images = Path(target_images_str)

        img_filename = img_data["file_name"]
        img_width, img_height = img_data["width"], img_data["height"]

        if img_id not in image_annotations:
            return None

        yolo_lines = []
        for ann in image_annotations[img_id]:
            cat_id = ann["category_id"]
            yolo_class = categories_dict[cat_id]["id"]

            segmentation = ann.get("segmentation")
            if not segmentation or not isinstance(segmentation, list):
                continue

            polygon = segmentation[0]
            if len(polygon) < 6:
                continue

            norm_parts = []
            for i in range(0, len(polygon), 2):
                nx = polygon[i] / img_width
                ny = polygon[i + 1] / img_height
                norm_parts.append(f"{nx:.6f}")
                norm_parts.append(f"{ny:.6f}")

            yolo_lines.append(f"{yolo_class} " + " ".join(norm_parts))

        if not yolo_lines:
            return None

        base_name = Path(img_filename).stem
        label_path = target_labels / f"{base_name}.txt"
        label_path.write_text("\n".join(yolo_lines), encoding="utf-8")

        if copy_images:
            src = image_source_dir / Path(img_filename).name
            if src.exists():
                dst = target_images / Path(img_filename).name
                shutil.copy2(src, dst)
                return (str(label_path), str(dst), True)

        return (str(label_path), None, True)
    except Exception as e:
        logger.warning("Error processing %s: %s", img_data.get("file_name", "unknown"), e)
        return None


class SegFormatConverter:
    """
    Convert segmentation datasets between COCO (with polygon masks) and YOLO-seg formats.

    YOLO-seg label format: ``class_id x1 y1 x2 y2 ... xN yN`` (normalized polygon).
    COCO-seg annotation: ``"segmentation": [[x1,y1,...]]``, ``"bbox"``, ``"area"``.

    Parameters
    ----------
    source_dir : str
        Path to source dataset directory.
    target_dir : str
        Path to target output directory.
    verbose : bool
        Print progress information.
    num_workers : int, optional
        Parallel workers for conversion.
    """

    def __init__(
        self,
        source_dir: str,
        target_dir: str,
        verbose: bool = True,
        num_workers: Optional[int] = None,
    ):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.verbose = verbose
        self.num_workers = num_workers if num_workers is not None else min(cpu_count(), 8)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def convert(
        self,
        target_format: str,
        splits: Optional[List[str]] = None,
        copy_images: bool = True,
        num_workers: Optional[int] = None,
    ) -> str:
        """
        Convert dataset to target format.

        Parameters
        ----------
        target_format : str
            ``"coco"`` or ``"yolo"``.
        splits : list of str, optional
            Splits to convert. Auto-detects if None.
        copy_images : bool
            Copy images to target directory.
        num_workers : int, optional
            Override parallel workers.

        Returns
        -------
        str
            Path to converted dataset or generated config file.
        """
        from nectar.ai.detection.datasets.format import FormatDetector

        detector = FormatDetector(str(self.source_dir))
        source_format = detector.detect()

        if source_format == "unknown":
            raise ValueError(f"Could not detect format in {self.source_dir}")
        if source_format == target_format:
            self._print(f"Dataset already in {target_format} format")
            return str(self.target_dir)

        workers = num_workers if num_workers is not None else self.num_workers

        if target_format == "yolo":
            return self.coco_to_yolo_seg(
                splits=splits,
                copy_images=copy_images,
                num_workers=workers,
            )
        elif target_format == "coco":
            return self.yolo_seg_to_coco(
                splits=splits,
                copy_images=copy_images,
                num_workers=workers,
            )
        else:
            raise ValueError(f"Unsupported target format: {target_format}")

    # ------------------------------------------------------------------
    # YOLO-seg -> COCO (with segmentation polygons)
    # ------------------------------------------------------------------

    def yolo_seg_to_coco(
        self,
        splits: Optional[List[str]] = None,
        copy_images: bool = True,
        num_workers: Optional[int] = None,
    ) -> str:
        """
        Convert YOLO-seg dataset to COCO format with segmentation annotations.

        Returns
        -------
        str
            Path to target directory.
        """
        yaml_path = self.source_dir / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        if "names" not in yaml_data:
            raise ValueError(f"No class names in {yaml_path}")

        class_names = yaml_data["names"]
        if isinstance(class_names, list):
            categories = [
                {"id": i, "name": n, "supercategory": "object"} for i, n in enumerate(class_names)
            ]
        else:
            categories = [
                {"id": int(k), "name": v, "supercategory": "object"} for k, v in class_names.items()
            ]

        if splits is None:
            splits = [
                d.name
                for d in self.source_dir.iterdir()
                if d.is_dir() and (d / "labels").exists() and (d / "images").exists()
            ]

        if not splits:
            raise ValueError(f"No YOLO splits found in {self.source_dir}")

        self._print(f"Converting YOLO-seg -> COCO. Splits: {splits}")
        workers = num_workers if num_workers is not None else self.num_workers

        for split in splits:
            self._print(f"Processing: {split}")

            images_dir = self.source_dir / split / "images"
            labels_dir = self.source_dir / split / "labels"

            target_name = "valid" if split == "val" else split
            target_split = self.target_dir / target_name
            target_split.mkdir(parents=True, exist_ok=True)

            image_paths = sorted(
                p
                for p in images_dir.glob("*.*")
                if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
            )

            process_args = [
                (str(img_path), idx, str(labels_dir), str(target_split), copy_images)
                for idx, img_path in enumerate(image_paths)
            ]

            if workers > 1 and len(process_args) > 10:
                with Pool(workers) as pool:
                    results = list(
                        tqdm(
                            pool.imap(_process_yolo_seg_image_to_coco, process_args),
                            total=len(process_args),
                            desc=f"Converting {split}",
                        )
                    )
            else:
                results = [
                    _process_yolo_seg_image_to_coco(a)
                    for a in tqdm(process_args, desc=f"Converting {split}")
                ]

            coco_data: Dict = {"images": [], "annotations": [], "categories": categories}
            annotation_id = 1
            for result in results:
                if result is None:
                    continue
                coco_data["images"].append(result["image"])
                for ann in result["annotations"]:
                    ann["id"] = annotation_id
                    ann["image_id"] = result["image"]["id"]
                    ann["iscrowd"] = 0
                    coco_data["annotations"].append(ann)
                    annotation_id += 1

            ann_path = target_split / "_annotations.coco.json"
            with open(ann_path, "w", encoding="utf-8") as f:
                json.dump(coco_data, f, indent=2)

            self._print(
                f"  Wrote {len(coco_data['images'])} images, "
                f"{len(coco_data['annotations'])} annotations -> {ann_path}"
            )

        self._print(f"Saved to: {self.target_dir}")
        return str(self.target_dir)

    # ------------------------------------------------------------------
    # COCO (with segmentation polygons) -> YOLO-seg
    # ------------------------------------------------------------------

    def coco_to_yolo_seg(
        self,
        splits: Optional[List[str]] = None,
        copy_images: bool = True,
        num_workers: Optional[int] = None,
    ) -> str:
        """
        Convert COCO dataset (with segmentation polygons) to YOLO-seg format.

        Returns
        -------
        str
            Path to generated ``data.yaml``.
        """
        if splits is None:
            splits = [
                d.name
                for d in self.source_dir.iterdir()
                if d.is_dir() and (d / "_annotations.coco.json").exists()
            ]

        if not splits:
            raise ValueError(f"No COCO splits found in {self.source_dir}")

        self._print(f"Converting COCO -> YOLO-seg. Splits: {splits}")
        workers = num_workers if num_workers is not None else self.num_workers
        categories_dict: Dict = {}

        for split in splits:
            self._print(f"Processing: {split}")

            split_dir = self.source_dir / split
            annotations_file = split_dir / "_annotations.coco.json"

            if not annotations_file.exists():
                raise FileNotFoundError(f"Not found: {annotations_file}")

            image_source_dir = split_dir / "images"
            if not image_source_dir.is_dir():
                image_source_dir = split_dir

            target_images = self.target_dir / split / "images"
            target_labels = self.target_dir / split / "labels"
            target_images.mkdir(parents=True, exist_ok=True)
            target_labels.mkdir(parents=True, exist_ok=True)

            with open(annotations_file, encoding="utf-8") as f:
                coco_data = json.load(f)

            if not categories_dict:
                categories_dict = {
                    cat["id"]: {"id": idx, "name": cat["name"]}
                    for idx, cat in enumerate(coco_data["categories"])
                }

            image_annotations: Dict[int, list] = defaultdict(list)
            for ann in coco_data["annotations"]:
                image_annotations[ann["image_id"]].append(ann)

            process_args = [
                (
                    img,
                    img["id"],
                    image_annotations,
                    categories_dict,
                    str(image_source_dir),
                    str(target_labels),
                    str(target_images),
                    copy_images,
                )
                for img in coco_data["images"]
            ]

            if workers > 1 and len(process_args) > 10:
                with Pool(workers) as pool:
                    for _ in tqdm(
                        pool.imap(_process_coco_seg_image_to_yolo, process_args),
                        total=len(process_args),
                        desc=f"Converting {split}",
                    ):
                        pass
            else:
                for a in tqdm(process_args, desc=f"Converting {split}"):
                    _process_coco_seg_image_to_yolo(a)

        yaml_path = self._create_yolo_yaml(categories_dict)
        self._print(f"Saved: {yaml_path}")
        return str(yaml_path)

    def _create_yolo_yaml(self, categories_dict: Optional[Dict] = None) -> Path:
        """Create YOLO data.yaml with class names."""
        names: Dict[int, str] = {}
        if categories_dict:
            names = {v["id"]: v["name"] for v in categories_dict.values()}
        else:
            categories: set = set()
            for split_dir in self.target_dir.iterdir():
                if not split_dir.is_dir():
                    continue
                labels_dir = split_dir / "labels"
                if not labels_dir.exists():
                    continue
                for label_file in labels_dir.glob("*.txt"):
                    with open(label_file, encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split()
                            if parts:
                                categories.add(int(parts[0]))
            if categories:
                names = {i: f"class_{i}" for i in range(max(categories) + 1)}

        yaml_data: Dict = {
            "path": str(self.target_dir.absolute()),
            "names": names,
            "nc": len(names),
        }

        split_mapping = {"valid": "val"}
        for split_dir in self.target_dir.iterdir():
            if not split_dir.is_dir():
                continue
            name = split_dir.name
            yolo_key = split_mapping.get(name, name)
            if (split_dir / "images").exists():
                yaml_data[yolo_key] = f"{name}/images"

        yaml_path = self.target_dir / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        return yaml_path
