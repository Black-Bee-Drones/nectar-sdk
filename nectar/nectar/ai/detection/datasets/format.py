"""Dataset format detection and conversion utilities."""

import json
import logging
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)


class FormatDetector:
    """
    Detect dataset format (COCO or YOLO).

    Parameters
    ----------
    dataset_path : str
        Path to dataset directory.
    """

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)

    def detect(self) -> str:
        """
        Detect dataset format.

        Returns
        -------
        str
            Detected format: "coco", "yolo", or "unknown".

        Examples
        --------
        >>> detector = FormatDetector("datasets/my_dataset")
        >>> format_type = detector.detect()
        >>> print(format_type)  # "coco" or "yolo"
        """
        if (self.dataset_path / "data.yaml").exists():
            return "yolo"

        for split_dir in self.dataset_path.iterdir():
            if split_dir.is_dir():
                if (split_dir / "_annotations.coco.json").exists():
                    return "coco"
                if (split_dir / "images").exists() and (split_dir / "labels").exists():
                    return "yolo"

        if (self.dataset_path / "images").exists():
            potential_json = list(self.dataset_path.glob("*.json"))
            if potential_json:
                return "coco"

        return "unknown"

    def validate(self, format_type: Optional[str] = None) -> bool:
        """
        Validate dataset structure.

        Parameters
        ----------
        format_type : str, optional
            Expected format. Auto-detects if None.

        Returns
        -------
        bool
            True if valid, False otherwise.
        """
        if format_type is None:
            format_type = self.detect()

        if format_type == "yolo":
            return self._validate_yolo()
        elif format_type == "coco":
            return self._validate_coco()
        return False

    def _validate_yolo(self) -> bool:
        """Validate YOLO format structure."""
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            return False

        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            if "names" not in data:
                return False
        except Exception:
            return False

        for split_dir in self.dataset_path.iterdir():
            if split_dir.is_dir():
                if not (split_dir / "images").exists():
                    continue
                if not (split_dir / "labels").exists():
                    return False
        return True

    def _validate_coco(self) -> bool:
        """Validate COCO format structure."""
        for split_dir in self.dataset_path.iterdir():
            if split_dir.is_dir():
                ann_file = split_dir / "_annotations.coco.json"
                if ann_file.exists():
                    try:
                        with open(ann_file) as f:
                            data = json.load(f)
                        if "images" not in data or "annotations" not in data:
                            return False
                    except Exception:
                        return False

        if (self.dataset_path / "images").exists():
            potential_json = list(self.dataset_path.glob("*.json"))
            if potential_json:
                try:
                    with open(potential_json[0]) as f:
                        data = json.load(f)
                    if "images" not in data or "annotations" not in data:
                        return False
                except Exception:
                    return False

        return True


class FormatConverter:
    """
    Convert datasets between COCO and YOLO formats.

    Parameters
    ----------
    source_dir : str
        Path to source dataset directory.
    target_dir : str
        Path to target output directory.
    verbose : bool, optional
        Print progress information. Defaults to True.
    """

    def __init__(self, source_dir: str, target_dir: str, verbose: bool = True):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.verbose = verbose
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def convert(
        self,
        target_format: str,
        splits: Optional[List[str]] = None,
        copy_images: bool = True,
    ) -> str:
        """
        Convert dataset to target format.

        Parameters
        ----------
        target_format : str
            Target format: "coco" or "yolo".
        splits : List[str], optional
            Splits to convert. Auto-detects if None.
        copy_images : bool, optional
            Copy images to target. Defaults to True.

        Returns
        -------
        str
            Path to converted dataset directory or generated config file.
        """
        detector = FormatDetector(str(self.source_dir))
        source_format = detector.detect()

        if source_format == "unknown":
            raise ValueError(f"Could not detect format in {self.source_dir}")

        if source_format == target_format:
            self._print(f"Dataset already in {target_format} format")
            return str(self.target_dir)

        if target_format == "yolo":
            return self.coco_to_yolo(splits=splits, copy_images=copy_images)
        elif target_format == "coco":
            return self.yolo_to_coco(splits=splits, copy_images=copy_images)
        else:
            raise ValueError(f"Unsupported target format: {target_format}")

    def coco_to_yolo(self, splits: Optional[List[str]] = None, copy_images: bool = True) -> str:
        """
        Convert COCO format to YOLO format.

        Parameters
        ----------
        splits : List[str], optional
            Splits to convert. Auto-detects if None.
        copy_images : bool, optional
            Copy images to target. Defaults to True.

        Returns
        -------
        str
            Path to generated data.yaml.
        """
        if splits is None:
            splits = [
                d.name
                for d in self.source_dir.iterdir()
                if d.is_dir() and (d / "_annotations.coco.json").exists()
            ]

        if not splits:
            if (self.source_dir / "images").exists():
                potential_json = list(self.source_dir.glob("*.json"))
                if potential_json:
                    splits = ["all"]
                    self._convert_single_coco_to_yolo(
                        self.source_dir, potential_json[0], copy_images
                    )
                    return self._create_yolo_yaml()
            raise ValueError(f"No COCO splits found in {self.source_dir}")

        self._print(f"Converting COCO to YOLO. Splits: {splits}")

        categories_dict = {}

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

            with open(annotations_file) as f:
                coco_data = json.load(f)

            if not categories_dict:
                categories_dict = {
                    cat["id"]: {"id": idx, "name": cat["name"]}
                    for idx, cat in enumerate(coco_data["categories"])
                }

            image_annotations = defaultdict(list)
            for ann in coco_data["annotations"]:
                image_annotations[ann["image_id"]].append(ann)

            for img in tqdm(coco_data["images"], desc=f"Converting {split}"):
                img_id = img["id"]
                img_filename = img["file_name"]
                img_width, img_height = img["width"], img["height"]

                if img_id not in image_annotations:
                    continue

                yolo_annotations = []
                for ann in image_annotations[img_id]:
                    if "bbox" not in ann:
                        continue

                    cat_id = ann["category_id"]
                    yolo_class = categories_dict[cat_id]["id"]

                    x, y, w, h = ann["bbox"]
                    x_center = (x + w / 2) / img_width
                    y_center = (y + h / 2) / img_height
                    width = w / img_width
                    height = h / img_height

                    yolo_annotations.append(f"{yolo_class} {x_center} {y_center} {width} {height}")

                if not yolo_annotations:
                    continue

                base_name = Path(img_filename).stem
                label_path = target_labels / f"{base_name}.txt"
                with open(label_path, "w") as f:
                    f.write("\n".join(yolo_annotations))

                if copy_images:
                    src = image_source_dir / Path(img_filename).name
                    if src.exists():
                        shutil.copy2(src, target_images / Path(img_filename).name)

        yaml_path = self._create_yolo_yaml()
        self._print(f"Saved: {yaml_path}")
        return str(yaml_path)

    def _convert_single_coco_to_yolo(
        self, source_dir: Path, json_file: Path, copy_images: bool
    ) -> None:
        """Convert single COCO JSON file to YOLO format."""
        with open(json_file) as f:
            coco_data = json.load(f)

        target_images = self.target_dir / "all" / "images"
        target_labels = self.target_dir / "all" / "labels"
        target_images.mkdir(parents=True, exist_ok=True)
        target_labels.mkdir(parents=True, exist_ok=True)

        categories_dict = {
            cat["id"]: {"id": idx, "name": cat["name"]}
            for idx, cat in enumerate(coco_data["categories"])
        }

        image_annotations = defaultdict(list)
        for ann in coco_data["annotations"]:
            image_annotations[ann["image_id"]].append(ann)

        images_dir = source_dir / "images"
        if not images_dir.exists():
            images_dir = source_dir

        for img in tqdm(coco_data["images"], desc="Converting"):
            img_id = img["id"]
            img_filename = img["file_name"]
            img_path = images_dir / img_filename

            if not img_path.exists():
                continue

            try:
                with Image.open(img_path) as im:
                    img_width, img_height = im.size
            except Exception as e:
                self._print(f"Warning: {img_path} - {e}")
                continue

            if img_id not in image_annotations:
                continue

            yolo_annotations = []
            for ann in image_annotations[img_id]:
                if "bbox" not in ann:
                    continue

                cat_id = ann["category_id"]
                yolo_class = categories_dict[cat_id]["id"]

                x, y, w, h = ann["bbox"]
                x_center = (x + w / 2) / img_width
                y_center = (y + h / 2) / img_height
                width = w / img_width
                height = h / img_height

                yolo_annotations.append(f"{yolo_class} {x_center} {y_center} {width} {height}")

            if yolo_annotations:
                base_name = Path(img_filename).stem
                label_path = target_labels / f"{base_name}.txt"
                with open(label_path, "w") as f:
                    f.write("\n".join(yolo_annotations))

                if copy_images:
                    shutil.copy2(img_path, target_images / img_filename)

    def yolo_to_coco(
        self, splits: Optional[List[str]] = None, copy_images: bool = True
    ) -> Dict[str, str]:
        """
        Convert YOLO format to COCO format.

        Parameters
        ----------
        splits : List[str], optional
            Splits to convert. Auto-detects if None.
        copy_images : bool, optional
            Copy images to target. Defaults to True.

        Returns
        -------
        Dict[str, str]
            Mapping of split names to annotation file paths.
        """
        yaml_path = self.source_dir / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path) as f:
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

        self._print(f"Converting YOLO to COCO. Splits: {splits}")

        result_paths = {}

        for split in splits:
            self._print(f"Processing: {split}")

            images_dir = self.source_dir / split / "images"
            labels_dir = self.source_dir / split / "labels"

            target_name = "valid" if split == "val" else split
            target_split = self.target_dir / target_name
            target_split.mkdir(parents=True, exist_ok=True)

            coco_data = {"images": [], "annotations": [], "categories": categories}

            image_paths = [
                p
                for p in images_dir.glob("*.*")
                if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]
            ]

            annotation_id = 1

            for img_idx, img_path in enumerate(tqdm(image_paths, desc=f"Converting {split}")):
                img_id = img_idx + 1

                try:
                    with Image.open(img_path) as img:
                        img_width, img_height = img.size
                except Exception as e:
                    self._print(f"Warning: {img_path} - {e}")
                    continue

                coco_data["images"].append(
                    {
                        "id": img_id,
                        "file_name": img_path.name,
                        "width": img_width,
                        "height": img_height,
                    }
                )

                label_path = labels_dir / f"{img_path.stem}.txt"
                if not label_path.exists():
                    continue

                with open(label_path) as f:
                    yolo_annotations = f.read().strip().split("\n")

                for yolo_ann in yolo_annotations:
                    if not yolo_ann.strip():
                        continue

                    parts = yolo_ann.strip().split()
                    if len(parts) < 5:
                        continue

                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])

                    x = (x_center - width / 2) * img_width
                    y = (y_center - height / 2) * img_height
                    w = width * img_width
                    h = height * img_height

                    coco_data["annotations"].append(
                        {
                            "id": annotation_id,
                            "image_id": img_id,
                            "category_id": class_id,
                            "bbox": [x, y, w, h],
                            "area": w * h,
                            "iscrowd": 0,
                        }
                    )
                    annotation_id += 1

                target_img = target_split / img_path.name
                if not target_img.exists():
                    if copy_images:
                        shutil.copy2(img_path, target_img)
                    else:
                        os.symlink(img_path.resolve(), target_img)

            annotation_path = target_split / "_annotations.coco.json"
            with open(annotation_path, "w") as f:
                json.dump(coco_data, f, indent=2)

            result_paths[split] = str(annotation_path)

        self._print(f"Saved to: {self.target_dir}")
        return result_paths

    def _create_yolo_yaml(self) -> Path:
        """Create YOLO data.yaml file."""
        yaml_data = {
            "path": str(self.target_dir.absolute()),
            "names": {},
            "nc": 0,
        }

        categories = set()
        split_mapping = {"valid": "val"}

        for split_dir in self.target_dir.iterdir():
            if not split_dir.is_dir():
                continue

            split_name = split_dir.name
            yolo_split = split_mapping.get(split_name, split_name)

            if (split_dir / "images").exists():
                yaml_data[yolo_split] = f"{split_name}/images"

                labels_dir = split_dir / "labels"
                if labels_dir.exists():
                    for label_file in labels_dir.glob("*.txt"):
                        with open(label_file) as f:
                            for line in f:
                                parts = line.strip().split()
                                if parts:
                                    categories.add(int(parts[0]))

        if categories:
            max_cat = max(categories)
            yaml_data["names"] = {i: f"class_{i}" for i in range(max_cat + 1)}
            yaml_data["nc"] = max_cat + 1

        yaml_path = self.target_dir / "data.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        return yaml_path
