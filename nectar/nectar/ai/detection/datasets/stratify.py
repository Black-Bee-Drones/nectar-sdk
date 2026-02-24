"""Dataset stratification utilities."""

import json
import logging
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml
from tqdm import tqdm

from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector

logger = logging.getLogger(__name__)


class Stratifier:
    """
    Split datasets into train/val/test with balanced class distribution.

    Parameters
    ----------
    source_dir : str
        Path to source dataset directory.
    target_dir : str
        Path to target output directory.
    seed : int, optional
        Random seed for reproducibility. Defaults to 42.
    verbose : bool, optional
        Print progress information. Defaults to True.
    """

    def __init__(self, source_dir: str, target_dir: str, seed: int = 42, verbose: bool = True):
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.seed = seed
        self.verbose = verbose
        self.target_dir.mkdir(parents=True, exist_ok=True)

        random.seed(seed)

    def _print(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def stratify(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.2,
        test_ratio: float = 0.0,
        target_format: Optional[str] = None,
    ) -> str:
        """
        Create stratified splits from unsplit dataset.

        Parameters
        ----------
        train_ratio : float, optional
            Training split ratio. Defaults to 0.8.
        val_ratio : float, optional
            Validation split ratio. Defaults to 0.2.
        test_ratio : float, optional
            Test split ratio. Defaults to 0.0.
        target_format : str, optional
            Target format ("coco" or "yolo"). Auto-detects if None.

        Returns
        -------
        str
            Path to stratified dataset directory.
        """
        detector = FormatDetector(str(self.source_dir))
        source_format = detector.detect()

        if source_format == "unknown":
            raise ValueError(f"Could not detect format in {self.source_dir}")

        if source_format == "coco":
            return self._stratify_coco(train_ratio, val_ratio, test_ratio)
        elif source_format == "yolo":
            result = self._stratify_yolo(train_ratio, val_ratio, test_ratio)
            if target_format == "coco":
                converter = FormatConverter(str(result), str(self.target_dir / "coco"))
                converter.yolo_to_coco()
                return str(self.target_dir / "coco")
            return result
        else:
            raise ValueError(f"Unsupported format: {source_format}")

    def _stratify_coco(self, train_ratio: float, val_ratio: float, test_ratio: float) -> str:
        """Stratify COCO format dataset."""
        images_dir = self.source_dir / "images"
        dataset_json = self.source_dir / "dataset.json"

        if not dataset_json.exists():
            potential = list(self.source_dir.glob("*.json"))
            if potential:
                dataset_json = potential[0]
            else:
                raise FileNotFoundError(f"No annotations found in {self.source_dir}")

        if not images_dir.exists():
            raise FileNotFoundError(f"No images directory: {images_dir}")

        with open(dataset_json) as f:
            coco_data = json.load(f)

        total = train_ratio + val_ratio + test_ratio
        train_ratio /= total
        val_ratio /= total
        test_ratio /= total

        train_ids, val_ids, test_ids = self._stratified_split_coco(
            coco_data, train_ratio, val_ratio, test_ratio
        )

        for split_name, ids in [
            ("train", train_ids),
            ("val", val_ids),
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
                json.dump(split_data, f, indent=2)

            split_images_dir = split_dir / "images"
            split_images_dir.mkdir(parents=True, exist_ok=True)

            for img in tqdm(split_data["images"], desc=f"Copying {split_name}"):
                src = images_dir / img["file_name"]
                if src.exists():
                    shutil.copy2(src, split_images_dir / img["file_name"])

        self._print(f"Stratified split saved to: {self.target_dir}")
        return str(self.target_dir)

    def _stratify_yolo(self, train_ratio: float, val_ratio: float, test_ratio: float) -> str:
        """Stratify YOLO format dataset."""
        images_dir = self.source_dir / "images"
        labels_dir = self.source_dir / "labels"

        if not images_dir.exists() or not labels_dir.exists():
            raise FileNotFoundError(
                f"YOLO format requires 'images' and 'labels' directories in {self.source_dir}"
            )

        image_files = list(images_dir.glob("*.*"))
        image_to_classes = defaultdict(set)
        class_to_images = defaultdict(list)

        for img_path in image_files:
            label_path = labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue

            try:
                with open(label_path) as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            class_id = int(parts[0])
                            image_to_classes[img_path].add(class_id)
                            class_to_images[class_id].append(img_path)
            except Exception as e:
                self._print(f"Warning: {label_path} - {e}")

        total = train_ratio + val_ratio + test_ratio
        train_ratio /= total
        val_ratio /= total
        test_ratio /= total

        train_images, val_images, test_images = self._stratified_split_yolo(
            list(image_to_classes.keys()),
            image_to_classes,
            class_to_images,
            train_ratio,
            val_ratio,
            test_ratio,
        )

        yaml_data = {"path": str(self.target_dir.absolute()), "names": {}, "nc": 0}

        for split_name, images in [
            ("train", train_images),
            ("val", val_images),
            ("test", test_images),
        ]:
            if not images:
                continue

            split_dir = self.target_dir / split_name
            split_images_dir = split_dir / "images"
            split_labels_dir = split_dir / "labels"
            split_images_dir.mkdir(parents=True, exist_ok=True)
            split_labels_dir.mkdir(parents=True, exist_ok=True)

            categories = set()

            for img_path in tqdm(images, desc=f"Copying {split_name}"):
                shutil.copy2(img_path, split_images_dir / img_path.name)

                label_path = labels_dir / f"{img_path.stem}.txt"
                if label_path.exists():
                    shutil.copy2(label_path, split_labels_dir / label_path.name)

                    with open(label_path) as f:
                        for line in f:
                            parts = line.strip().split()
                            if parts:
                                categories.add(int(parts[0]))

            yaml_data[split_name] = f"{split_name}/images"

        if categories:
            max_cat = max(categories)
            yaml_data["names"] = {i: f"class_{i}" for i in range(max_cat + 1)}
            yaml_data["nc"] = max_cat + 1

        yaml_path = self.target_dir / "data.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        self._print(f"Stratified split saved to: {self.target_dir}")
        return str(self.target_dir)

    def _stratified_split_coco(
        self,
        coco_data: Dict,
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
    ) -> Tuple[Set[int], Set[int], Set[int]]:
        """Perform stratified splitting for COCO format."""
        random.seed(self.seed)

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

    def _stratified_split_yolo(
        self,
        images: List[Path],
        image_to_classes: Dict[Path, Set[int]],
        class_to_images: Dict[int, List[Path]],
        train_ratio: float,
        val_ratio: float,
        test_ratio: float,
    ) -> Tuple[List[Path], List[Path], List[Path]]:
        """Perform stratified splitting for YOLO format."""
        random.seed(self.seed)

        category_images = defaultdict(list)
        for img_path, classes in image_to_classes.items():
            if classes:
                primary = min(classes)
                category_images[primary].append(img_path)

        no_annotation = [img for img in images if img not in image_to_classes]

        train_images, val_images, test_images = [], [], []

        for cat_id, img_list in category_images.items():
            random.shuffle(img_list)
            n = len(img_list)
            n_train = max(1, int(n * train_ratio))
            n_val = max(0, int(n * val_ratio)) if val_ratio > 0 else 0

            train_images.extend(img_list[:n_train])
            val_images.extend(img_list[n_train : n_train + n_val])
            if test_ratio > 0:
                test_images.extend(img_list[n_train + n_val :])

        if no_annotation:
            random.shuffle(no_annotation)
            n = len(no_annotation)
            n_train = int(n * train_ratio)
            n_val = int(n * val_ratio)
            train_images.extend(no_annotation[:n_train])
            val_images.extend(no_annotation[n_train : n_train + n_val])
            test_images.extend(no_annotation[n_train + n_val :])

        return train_images, val_images, test_images

    def _report_distribution(
        self, coco_data: Dict, train_ids: Set[int], val_ids: Set[int], test_ids: Set[int]
    ) -> None:
        """Report class distribution across splits."""
        cat_names = {c["id"]: c["name"] for c in coco_data["categories"]}

        splits = {
            "train": {"ids": train_ids, "counts": Counter()},
            "val": {"ids": val_ids, "counts": Counter()},
            "test": {"ids": test_ids, "counts": Counter()},
        }

        for ann in coco_data["annotations"]:
            for split_data in splits.values():
                if ann["image_id"] in split_data["ids"]:
                    split_data["counts"][ann["category_id"]] += 1

        self._print("\n" + "=" * 70)
        self._print("CLASS DISTRIBUTION")
        self._print("=" * 70)
        self._print(f"{'Category':<25} {'Train':>12} {'Val':>12} {'Test':>12}")
        self._print("-" * 70)

        for cat_id in sorted(cat_names.keys()):
            name = cat_names[cat_id][:24]
            t = splits["train"]["counts"].get(cat_id, 0)
            v = splits["val"]["counts"].get(cat_id, 0)
            te = splits["test"]["counts"].get(cat_id, 0)
            self._print(f"{name:<25} {t:>12} {v:>12} {te:>12}")

        self._print("-" * 70)
        self._print(f"{'IMAGES':<25} {len(train_ids):>12} {len(val_ids):>12} {len(test_ids):>12}")
        self._print("=" * 70 + "\n")
