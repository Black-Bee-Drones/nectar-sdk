"""Balanced subset creation utilities."""

import json
import logging
import os
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from tqdm import tqdm

from nectar.ai.detection.datasets.format import FormatDetector

logger = logging.getLogger(__name__)


class SubsetCreator:
    """
    Create balanced subsets maintaining class distribution.

    Parameters
    ----------
    dataset_path : str
        Path to source dataset directory.
    output_dir : str
        Path to output subset directory.
    seed : int, optional
        Random seed for reproducibility. Defaults to 42.
    verbose : bool, optional
        Print progress information. Defaults to True.
    """

    def __init__(self, dataset_path: str, output_dir: str, seed: int = 42, verbose: bool = True):
        self.dataset_path = Path(dataset_path)
        self.output_dir = Path(output_dir)
        self.seed = seed
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

        random.seed(seed)
        self.random_gen = random.Random(seed)

    def _print(self, message: str) -> None:
        if self.verbose:
            logger.info(message)

    def create(
        self,
        max_train_samples: Optional[int] = None,
        max_eval_samples: Optional[int] = None,
        max_test_samples: Optional[int] = None,
    ) -> str:
        """
        Create balanced subset dataset.

        Parameters
        ----------
        max_train_samples : int, optional
            Maximum samples for train split.
        max_eval_samples : int, optional
            Maximum samples for validation split.
        max_test_samples : int, optional
            Maximum samples for test split.

        Returns
        -------
        str
            Path to created subset dataset.
        """
        detector = FormatDetector(str(self.dataset_path))
        format_type = detector.detect()

        if format_type == "yolo":
            return self._create_yolo_subset(max_train_samples, max_eval_samples, max_test_samples)
        elif format_type == "coco":
            return self._create_coco_subset(max_train_samples, max_eval_samples, max_test_samples)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _create_yolo_subset(
        self,
        max_train_samples: Optional[int],
        max_eval_samples: Optional[int],
        max_test_samples: Optional[int],
    ) -> str:
        """Create subset for YOLO format dataset."""
        yaml_path = self.dataset_path / "data.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"Not found: {yaml_path}")

        with open(yaml_path) as f:
            dataset_config = yaml.safe_load(f)

        yaml_dir = yaml_path.parent
        subset_config = dataset_config.copy()
        subset_config["path"] = str(self.output_dir.resolve())

        split_limits = {
            "train": max_train_samples,
            "val": max_eval_samples,
            "test": max_test_samples,
        }

        for split, max_samples in split_limits.items():
            if max_samples is None:
                continue

            if split not in dataset_config:
                continue

            split_path = yaml_dir / dataset_config[split]
            if not split_path.exists():
                split_name = (
                    Path(dataset_config[split]).parts[-2]
                    if "/images" in dataset_config[split]
                    else Path(dataset_config[split]).name
                )
                split_path = yaml_dir / split_name / "images"
            if not split_path.exists():
                self._print(f"Split directory not found: {split_path}")
                continue

            self._create_yolo_split_subset(split, split_path, max_samples, yaml_dir)
            subset_config[split] = f"{split}/images"

        subset_yaml_path = self.output_dir / "data.yaml"
        with open(subset_yaml_path, "w") as f:
            yaml.dump(subset_config, f, sort_keys=False)

        return str(self.output_dir)

    def _create_yolo_split_subset(
        self, split: str, split_path: Path, max_samples: int, yaml_dir: Path
    ) -> None:
        """Create subset for a single YOLO split."""
        subset_split_dir = self.output_dir / split
        subset_images_dir = subset_split_dir / "images"
        subset_labels_dir = subset_split_dir / "labels"
        subset_images_dir.mkdir(parents=True, exist_ok=True)
        subset_labels_dir.mkdir(parents=True, exist_ok=True)

        original_images_dir = split_path
        if not original_images_dir.exists():
            self._print(f"Images directory not found: {original_images_dir}")
            return

        image_files = list(original_images_dir.glob("*.*"))
        valid_image_files = []
        image_to_classes = defaultdict(list)
        class_to_images = defaultdict(list)
        total_class_counts = Counter()

        self._print(f"Analyzing class distribution for {split} split...")
        labels_dir = split_path.parent / "labels"
        for img_path in image_files:
            label_path = labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue

            valid_image_files.append(img_path)

            try:
                with open(label_path, "r") as f:
                    lines = f.readlines()

                img_classes = []
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        img_classes.append(class_id)
                        class_to_images[class_id].append(img_path)

                image_to_classes[img_path] = img_classes
                total_class_counts.update(img_classes)
            except Exception as e:
                self._print(f"Error reading label file {label_path}: {e}")

        if not valid_image_files:
            self._print(f"No valid labeled images found for {split} split")
            return

        self._print(f"Found {len(valid_image_files)} valid images with labels for {split} split")
        self._print(f"Class distribution: {dict(total_class_counts)}")

        if max_samples >= len(valid_image_files):
            sampled_images = valid_image_files
        else:
            sampled_images = self._balanced_sample(
                valid_image_files,
                image_to_classes,
                class_to_images,
                total_class_counts,
                max_samples,
            )

        self._print(f"Sampling {len(sampled_images)} images for {split} split")

        for img_path in tqdm(sampled_images, desc=f"Copying {split}"):
            shutil.copy2(img_path, subset_images_dir / img_path.name)

            label_path = labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                shutil.copy2(label_path, subset_labels_dir / label_path.name)

    def _create_coco_subset(
        self,
        max_train_samples: Optional[int],
        max_eval_samples: Optional[int],
        max_test_samples: Optional[int],
    ) -> str:
        """Create subset for COCO format dataset."""
        split_limits = {
            "train": max_train_samples,
            "valid": max_eval_samples,
            "test": max_test_samples,
        }

        for split, max_samples in split_limits.items():
            if max_samples is None:
                continue

            split_dir = self.dataset_path / split
            if not split_dir.exists() and split == "valid":
                split_dir = self.dataset_path / "val"
            ann_file = split_dir / "_annotations.coco.json"

            if not ann_file.exists():
                continue

            self._create_coco_split_subset(split, split_dir, ann_file, max_samples)

        return str(self.output_dir)

    def _create_coco_split_subset(
        self, split: str, split_dir: Path, ann_file: Path, max_samples: int
    ) -> None:
        """Create subset for a single COCO split."""
        with open(ann_file) as f:
            coco_data = json.load(f)

        images = coco_data["images"]
        annotations = coco_data["annotations"]
        categories = coco_data["categories"]

        if max_samples >= len(images):
            selected_images = images
            selected_image_ids = {img["id"] for img in images}
        else:
            image_to_classes = defaultdict(set)
            for ann in annotations:
                image_to_classes[ann["image_id"]].add(ann["category_id"])

            class_to_images = defaultdict(list)
            for img in images:
                img_classes = image_to_classes.get(img["id"], set())
                for cat_id in img_classes:
                    class_to_images[cat_id].append(img)

            total_class_counts = Counter()
            for ann in annotations:
                total_class_counts[ann["category_id"]] += 1

            selected_images = self._balanced_sample_coco(
                images,
                image_to_classes,
                class_to_images,
                total_class_counts,
                max_samples,
            )
            selected_image_ids = {img["id"] for img in selected_images}

        subset_split_dir = self.output_dir / split
        subset_split_dir.mkdir(parents=True, exist_ok=True)

        subset_annotations = [ann for ann in annotations if ann["image_id"] in selected_image_ids]

        subset_data = {
            "images": selected_images,
            "annotations": subset_annotations,
            "categories": categories,
        }

        subset_ann_file = subset_split_dir / "_annotations.coco.json"
        with open(subset_ann_file, "w") as f:
            json.dump(subset_data, f, indent=2)

        # Locate source images: try split_dir directly, then split_dir/images
        images_dir = split_dir
        if not (split_dir / selected_images[0]["file_name"]).exists():
            images_dir = split_dir / "images"

        # Place images directly in split dir (rfdetr expects train/file.jpg, not train/images/file.jpg)
        for img in tqdm(selected_images, desc=f"Linking {split}"):
            src = images_dir / img["file_name"]
            dst = subset_split_dir / img["file_name"]
            if src.exists() and not dst.exists():
                os.symlink(src.resolve(), dst)

    def _balanced_sample(
        self,
        valid_images: List[Path],
        image_to_classes: Dict[Path, List[int]],
        class_to_images: Dict[int, List[Path]],
        total_class_counts: Counter,
        max_samples: int,
    ) -> List[Path]:
        """Perform balanced sampling for YOLO format."""
        num_classes = len(total_class_counts)
        if num_classes == 0:
            return self.random_gen.sample(valid_images, min(max_samples, len(valid_images)))

        min_samples_per_class = min(3, max_samples // num_classes)
        remaining_quota = max_samples - (min_samples_per_class * num_classes)

        if remaining_quota < 0:
            min_samples_per_class = max(1, max_samples // num_classes)
            remaining_quota = max_samples - (min_samples_per_class * num_classes)

        total_instances = sum(total_class_counts.values())
        class_quotas = {}

        for class_id, count in total_class_counts.items():
            base_quota = min_samples_per_class
            if total_instances > 0 and remaining_quota > 0:
                additional = int((count / total_instances) * remaining_quota)
                class_quotas[class_id] = base_quota + additional
            else:
                class_quotas[class_id] = base_quota

        total_quota = sum(class_quotas.values())
        if total_quota < max_samples:
            sorted_classes = sorted(total_class_counts.items(), key=lambda x: x[1], reverse=True)
            remaining = max_samples - total_quota
            for class_id, _ in sorted_classes:
                if remaining <= 0:
                    break
                class_quotas[class_id] += 1
                remaining -= 1

        selected_images = set()
        sorted_classes = sorted(total_class_counts.items(), key=lambda x: x[1])

        for class_id, _ in sorted_classes:
            if class_id not in class_to_images:
                continue

            quota = class_quotas.get(class_id, 0)
            candidates = [img for img in class_to_images[class_id] if img not in selected_images]
            self.random_gen.shuffle(candidates)

            selected = candidates[:quota]
            selected_images.update(selected)

            if len(selected_images) >= max_samples:
                break

        if len(selected_images) < max_samples:
            remaining = [img for img in valid_images if img not in selected_images]
            self.random_gen.shuffle(remaining)
            needed = max_samples - len(selected_images)
            selected_images.update(remaining[:needed])

        return list(selected_images)[:max_samples]

    def _balanced_sample_coco(
        self,
        images: List[Dict],
        image_to_classes: Dict[int, set],
        class_to_images: Dict[int, List[Dict]],
        total_class_counts: Counter,
        max_samples: int,
    ) -> List[Dict]:
        """Perform balanced sampling for COCO format."""
        num_classes = len(total_class_counts)
        if num_classes == 0:
            return self.random_gen.sample(images, min(max_samples, len(images)))

        min_samples_per_class = min(3, max_samples // num_classes)
        remaining_quota = max_samples - (min_samples_per_class * num_classes)

        if remaining_quota < 0:
            min_samples_per_class = max(1, max_samples // num_classes)
            remaining_quota = max_samples - (min_samples_per_class * num_classes)

        total_instances = sum(total_class_counts.values())
        class_quotas = {}

        for class_id, count in total_class_counts.items():
            base_quota = min_samples_per_class
            if total_instances > 0 and remaining_quota > 0:
                additional = int((count / total_instances) * remaining_quota)
                class_quotas[class_id] = base_quota + additional
            else:
                class_quotas[class_id] = base_quota

        total_quota = sum(class_quotas.values())
        if total_quota < max_samples:
            sorted_classes = sorted(total_class_counts.items(), key=lambda x: x[1], reverse=True)
            remaining = max_samples - total_quota
            for class_id, _ in sorted_classes:
                if remaining <= 0:
                    break
                class_quotas[class_id] += 1
                remaining -= 1

        selected_images = set()
        sorted_classes = sorted(total_class_counts.items(), key=lambda x: x[1])

        for class_id, _ in sorted_classes:
            if class_id not in class_to_images:
                continue

            quota = class_quotas.get(class_id, 0)
            candidates = [
                img for img in class_to_images[class_id] if img["id"] not in selected_images
            ]
            self.random_gen.shuffle(candidates)

            selected = candidates[:quota]
            selected_images.update(img["id"] for img in selected)

            if len(selected_images) >= max_samples:
                break

        if len(selected_images) < max_samples:
            remaining = [img for img in images if img["id"] not in selected_images]
            self.random_gen.shuffle(remaining)
            needed = max_samples - len(selected_images)
            selected_images.update(img["id"] for img in remaining[:needed])

        selected_ids = list(selected_images)[:max_samples]
        return [img for img in images if img["id"] in selected_ids]
