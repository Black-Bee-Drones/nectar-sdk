"""Dataset format converter (COCO <-> YOLO)."""

import json
import logging
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import yaml
from PIL import Image
from tqdm import tqdm

logger = logging.getLogger(__name__)


class DatasetConverter:
    """
    Convert datasets between COCO and YOLO formats.

    COCO format:
    - {split}/images and {split}/_annotations.coco.json

    YOLO format:
    - {split}/images and {split}/labels with data.yaml

    Parameters
    ----------
    source_dir : str
        Path to source dataset directory.
    target_dir : str
        Path to target output directory.
    verbose : bool, optional
        Print progress information. Defaults to True.

    Examples
    --------
    >>> converter = DatasetConverter("data/coco", "data/yolo")
    >>> converter.coco_to_yolo(splits=["train", "valid"])
    """

    def __init__(self, source_dir: str, target_dir: str, verbose: bool = True):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.verbose = verbose
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str) -> None:
        if self.verbose:
            print(message)

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

        yaml_data = {
            "path": str(self.target_dir.absolute()),
            "names": {v["id"]: v["name"] for v in categories_dict.values()},
            "nc": len(categories_dict),
        }

        if (self.target_dir / "train").exists():
            yaml_data["train"] = "train/images"
        if (self.target_dir / "valid").exists():
            yaml_data["val"] = "valid/images"
        elif (self.target_dir / "val").exists():
            yaml_data["val"] = "val/images"
        if (self.target_dir / "test").exists():
            yaml_data["test"] = "test/images"

        yaml_path = self.target_dir / "data.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        self._print(f"Saved: {yaml_path}")
        return str(yaml_path)

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
            categories = [{"id": i, "name": n} for i, n in enumerate(class_names)]
        else:
            categories = [{"id": int(k), "name": v} for k, v in class_names.items()]

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

            target_split = self.target_dir / split
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

                if copy_images:
                    shutil.copy2(img_path, target_split / img_path.name)

            annotation_path = target_split / "_annotations.coco.json"
            with open(annotation_path, "w") as f:
                json.dump(coco_data, f, indent=2)

            result_paths[split] = str(annotation_path)

        self._print(f"Saved to: {self.target_dir}")
        return result_paths

    def stratified_split(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.2,
        test_ratio: float = 0.0,
        seed: int = 42,
        copy_images: bool = True,
    ) -> str:
        """
        Split single COCO dataset with stratification.

        Parameters
        ----------
        train_ratio : float
            Training split ratio. Defaults to 0.8.
        val_ratio : float
            Validation split ratio. Defaults to 0.2.
        test_ratio : float
            Test split ratio. Defaults to 0.0.
        seed : int
            Random seed. Defaults to 42.
        copy_images : bool
            Copy images. Defaults to True.

        Returns
        -------
        str
            Path to output directory.
        """
        random.seed(seed)
        np.random.seed(seed)

        images_dir = self.source_dir / "images"
        dataset_json = self.source_dir / "dataset.json"

        if not dataset_json.exists():
            potential = list(self.source_dir.glob("*.json"))
            if potential:
                dataset_json = potential[0]
            else:
                raise FileNotFoundError(f"No annotations in {self.source_dir}")

        if not images_dir.exists():
            raise FileNotFoundError(f"No images dir: {images_dir}")

        with open(dataset_json) as f:
            coco_data = json.load(f)

        total = train_ratio + val_ratio + test_ratio
        train_ratio /= total
        val_ratio /= total
        test_ratio /= total

        train_ids, val_ids, test_ids = self._stratified_split(
            coco_data, train_ratio, val_ratio, test_ratio, seed
        )

        for split_name, ids in [
            ("train", train_ids),
            ("valid", val_ids),
            ("test", test_ids),
        ]:
            if not ids:
                continue

            split_dir = self.target_dir / split_name
            split_dir.mkdir(parents=True, exist_ok=True)

            split_data = {
                "images": [i for i in coco_data["images"] if i["id"] in ids],
                "annotations": [a for a in coco_data["annotations"] if a["image_id"] in ids],
                "categories": coco_data["categories"],
            }

            with open(split_dir / "_annotations.coco.json", "w") as f:
                json.dump(split_data, f)

            if copy_images:
                for img in tqdm(split_data["images"], desc=f"{split_name}"):
                    src = images_dir / img["file_name"]
                    if src.exists():
                        shutil.copy2(src, split_dir / img["file_name"])

        self._print(f"Stratified split saved to: {self.target_dir}")
        return str(self.target_dir)

    def _stratified_split(
        self,
        coco_data: Dict,
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
        seed: int,
    ) -> Tuple[set, set, set]:
        """Perform stratified splitting maintaining class balance."""
        random.seed(seed)

        image_to_categories = defaultdict(set)
        for ann in coco_data["annotations"]:
            image_to_categories[ann["image_id"]].add(ann["category_id"])

        category_images = defaultdict(list)
        for img_id, cats in image_to_categories.items():
            if cats:
                category_counts = Counter(
                    ann["category_id"]
                    for ann in coco_data["annotations"]
                    if ann["image_id"] == img_id
                )
                primary = category_counts.most_common(1)[0][0]
                category_images[primary].append(img_id)

        no_annotation = [
            img["id"] for img in coco_data["images"] if img["id"] not in image_to_categories
        ]

        train_ids, val_ids, test_ids = set(), set(), set()

        for cat_id, img_ids in category_images.items():
            random.shuffle(img_ids)
            n = len(img_ids)
            n_train = max(1, int(n * train_ratio))
            n_val = max(0, int(n * val_ratio)) if val_ratio > 0 else 0

            train_ids.update(img_ids[:n_train])
            val_ids.update(img_ids[n_train : n_train + n_val])
            if test_ratio > 0:
                test_ids.update(img_ids[n_train + n_val :])

        if no_annotation:
            random.shuffle(no_annotation)
            n = len(no_annotation)
            n_train = int(n * train_ratio)
            n_val = int(n * val_ratio)
            train_ids.update(no_annotation[:n_train])
            val_ids.update(no_annotation[n_train : n_train + n_val])
            test_ids.update(no_annotation[n_train + n_val :])

        if self.verbose:
            self._report_distribution(coco_data, train_ids, val_ids, test_ids)

        return train_ids, val_ids, test_ids

    def _report_distribution(
        self, coco_data: Dict, train_ids: set, val_ids: set, test_ids: set
    ) -> None:
        """Report class distribution across splits."""
        cat_names = {c["id"]: c["name"] for c in coco_data["categories"]}

        splits = {
            "train": {"ids": train_ids, "counts": Counter()},
            "valid": {"ids": val_ids, "counts": Counter()},
            "test": {"ids": test_ids, "counts": Counter()},
        }

        for ann in coco_data["annotations"]:
            for split_data in splits.values():
                if ann["image_id"] in split_data["ids"]:
                    split_data["counts"][ann["category_id"]] += 1

        print("\n" + "=" * 70)
        print("CLASS DISTRIBUTION")
        print("=" * 70)
        print(f"{'Category':<25} {'Train':>12} {'Valid':>12} {'Test':>12}")
        print("-" * 70)

        for cat_id in sorted(cat_names.keys()):
            name = cat_names[cat_id][:24]
            t = splits["train"]["counts"].get(cat_id, 0)
            v = splits["valid"]["counts"].get(cat_id, 0)
            te = splits["test"]["counts"].get(cat_id, 0)
            print(f"{name:<25} {t:>12} {v:>12} {te:>12}")

        print("-" * 70)
        print(f"{'IMAGES':<25} {len(train_ids):>12} {len(val_ids):>12} {len(test_ids):>12}")
        print("=" * 70 + "\n")
