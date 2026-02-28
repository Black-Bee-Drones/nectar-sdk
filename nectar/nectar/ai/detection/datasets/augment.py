"""Augmentation builder: config presets and image generation."""

import json
import logging
import os
import random
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
import yaml
from tqdm import tqdm

logger = logging.getLogger(__name__)


AUG_CONSERVATIVE = {
    "HorizontalFlip": {"p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.2, "contrast_limit": 0.2, "p": 0.5},
}

AUG_AGGRESSIVE = {
    "HorizontalFlip": {"p": 0.5},
    "VerticalFlip": {"p": 0.3},
    "Rotate": {"limit": 45, "p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.3, "contrast_limit": 0.3, "p": 0.5},
    "ShiftScaleRotate": {"shift_limit": 0.1, "scale_limit": 0.2, "rotate_limit": 15, "p": 0.5},
    "GaussianBlur": {"blur_limit": 3, "p": 0.3},
    "GaussNoise": {"var_limit": 10.0, "p": 0.3},
}

AUG_AERIAL = {
    "HorizontalFlip": {"p": 0.5},
    "VerticalFlip": {"p": 0.5},
    "Rotate": {"limit": 90, "p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.3, "contrast_limit": 0.3, "p": 0.5},
    "HueSaturationValue": {
        "hue_shift_limit": 20,
        "sat_shift_limit": 30,
        "val_shift_limit": 20,
        "p": 0.5,
    },
    "CLAHE": {"clip_limit": 2.0, "tile_grid_size": (8, 8), "p": 0.3},
}

AUG_INDUSTRIAL = {
    "HorizontalFlip": {"p": 0.5},
    "RandomBrightnessContrast": {"brightness_limit": 0.2, "contrast_limit": 0.2, "p": 0.5},
    "GaussianBlur": {"blur_limit": 3, "p": 0.2},
    "MotionBlur": {"blur_limit": 3, "p": 0.2},
    "GaussNoise": {"var_limit": 10.0, "p": 0.2},
    "CLAHE": {"clip_limit": 2.0, "tile_grid_size": (8, 8), "p": 0.3},
}

PRESETS = {
    "conservative": AUG_CONSERVATIVE,
    "aggressive": AUG_AGGRESSIVE,
    "aerial": AUG_AERIAL,
    "industrial": AUG_INDUSTRIAL,
}


def _build_compose_from_config(config: Dict, bbox_format: str = "coco"):
    """Build albumentations compose from config dict."""
    import albumentations as A

    transforms = []
    for name, params in config.items():
        if not hasattr(A, name):
            raise ValueError(f"Unknown albumentations transform: {name}")
        transforms.append(getattr(A, name)(**params))

    label_fields = ["class_labels"]
    if bbox_format == "yolo":
        return A.Compose(
            transforms,
            bbox_params=A.BboxParams(format="yolo", label_fields=label_fields, min_visibility=0.3),
        )
    return A.Compose(
        transforms,
        bbox_params=A.BboxParams(format="coco", label_fields=label_fields, min_visibility=0.3),
    )


def _augment_coco_image_worker(
    img_info: Dict,
    split_dir: str,
    out_dir: str,
    img_id_to_anns: Dict,
    aug_config: Dict,
    num_augmented: int,
    start_img_id: int,
    start_ann_id: int,
) -> Tuple[List[Dict], List[Dict]]:
    """Worker function to augment a single COCO image."""
    split_dir = Path(split_dir)
    out_dir = Path(out_dir)
    compose = _build_compose_from_config(aug_config, "coco")
    new_images = []
    new_annotations = []

    src_img = split_dir / img_info["file_name"]
    if not src_img.exists():
        src_img = split_dir / "images" / img_info["file_name"]

    try:
        image = cv2.imread(str(src_img))
        if image is None:
            return [], []
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    except Exception:
        return [], []

    anns = img_id_to_anns.get(img_info["id"], [])
    if not anns:
        return [], []

    bboxes_xywh = [ann["bbox"] for ann in anns]
    bboxes_pascal = [[x, y, x + w, y + h] for x, y, w, h in bboxes_xywh]

    image_height, image_width = image.shape[:2]
    normalized_bboxes = []
    for x1, y1, x2, y2 in bboxes_pascal:
        normalized_bboxes.append(
            [
                x1 / image_width,
                y1 / image_height,
                x2 / image_width,
                y2 / image_height,
            ]
        )

    class_labels = [ann["category_id"] for ann in anns]

    results = []
    for i in range(num_augmented):
        try:
            augmented = compose(image=image, bboxes=normalized_bboxes, class_labels=class_labels)
            aug_image = augmented["image"]
            aug_bboxes = augmented["bboxes"]

            if not aug_bboxes:
                continue

            results.append((i, aug_image, aug_bboxes, augmented["class_labels"]))
        except Exception:
            continue

    for i, aug_image, aug_bboxes, aug_class_ids in results:
        aug_img_id = start_img_id + i
        aug_name = f"{Path(img_info['file_name']).stem}_aug{i}{Path(img_info['file_name']).suffix}"
        save_path = out_dir / aug_name

        cv2.imwrite(str(save_path), cv2.cvtColor(aug_image, cv2.COLOR_RGB2BGR))

        new_images.append(
            {
                "id": aug_img_id,
                "file_name": aug_name,
                "width": aug_image.shape[1],
                "height": aug_image.shape[0],
            }
        )

        aug_height, aug_width = aug_image.shape[:2]
        for j, (bbox, class_id) in enumerate(zip(aug_bboxes, aug_class_ids)):
            x1_norm, y1_norm, x2_norm, y2_norm = bbox
            x1 = x1_norm * aug_width
            y1 = y1_norm * aug_height
            x2 = x2_norm * aug_width
            y2 = y2_norm * aug_height

            new_annotations.append(
                {
                    "id": start_ann_id + i * len(aug_bboxes) + j,
                    "image_id": aug_img_id,
                    "category_id": class_id,
                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                    "area": (x2 - x1) * (y2 - y1),
                    "iscrowd": 0,
                }
            )

    return new_images, new_annotations


def _augment_yolo_image_worker(
    img_path: str,
    label_path: str,
    out_images: str,
    out_labels: str,
    aug_config: Dict,
    num_augmented: int,
) -> int:
    """Worker function to augment a single YOLO image."""
    img_path = Path(img_path)
    label_path = Path(label_path)
    out_images = Path(out_images)
    out_labels = Path(out_labels)
    compose = _build_compose_from_config(aug_config, "yolo")
    try:
        shutil.copy2(img_path, out_images / img_path.name)
        if label_path.exists():
            shutil.copy2(label_path, out_labels / label_path.name)

        image = cv2.imread(str(img_path))
        if image is None:
            return 0
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        bboxes, class_labels = [], []
        if label_path.exists():
            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_labels.append(int(parts[0]))
                        bboxes.append([float(x) for x in parts[1:5]])

        count = 0
        for aug_idx in range(num_augmented):
            try:
                result = compose(image=image, bboxes=bboxes, class_labels=class_labels)
            except Exception:
                continue

            aug_name = f"{img_path.stem}_aug{aug_idx}{img_path.suffix}"
            aug_img = cv2.cvtColor(result["image"], cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(out_images / aug_name), aug_img)

            aug_label_path = out_labels / f"{img_path.stem}_aug{aug_idx}.txt"
            with open(aug_label_path, "w") as f:
                for cls_id, bbox in zip(result["class_labels"], result["bboxes"]):
                    f.write(f"{cls_id} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n")
            count += 1
        return count
    except Exception:
        return 0


class AugmentationBuilder:
    """
    Build augmentation configurations from presets or custom configs.

    Parameters
    ----------
    preset : str, optional
        Preset name ("conservative", "aggressive", "aerial", "industrial").
    config : Dict, optional
        Custom augmentation configuration.
    """

    def __init__(self, preset: Optional[str] = None, config: Optional[Dict] = None):
        if preset and config:
            raise ValueError("Cannot specify both preset and config")
        if preset:
            if preset.lower() not in PRESETS:
                raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESETS.keys())}")
            self.config = PRESETS[preset.lower()].copy()
            self.preset = preset.lower()
        elif config:
            self.config = config.copy()
            self.preset = None
        else:
            self.config = {}
            self.preset = None

    def add_transform(self, name: str, params: Dict) -> "AugmentationBuilder":
        """
        Add or update a transform.

        Parameters
        ----------
        name : str
            Transform name (Albumentations transform).
        params : Dict
            Transform parameters.

        Returns
        -------
        AugmentationBuilder
            Self for chaining.
        """
        self.config[name] = params
        return self

    def remove_transform(self, name: str) -> "AugmentationBuilder":
        """
        Remove a transform.

        Parameters
        ----------
        name : str
            Transform name to remove.

        Returns
        -------
        AugmentationBuilder
            Self for chaining.
        """
        if name in self.config:
            del self.config[name]
        return self

    def get_config(self) -> Dict:
        """
        Get augmentation configuration.

        Returns
        -------
        Dict
            Augmentation configuration dictionary.
        """
        return self.config.copy()

    def to_dict(self) -> Dict:
        """
        Convert to dictionary with metadata.

        Returns
        -------
        Dict
            Configuration dictionary with preset info.
        """
        result = {"transforms": self.config.copy()}
        if self.preset:
            result["preset"] = self.preset
        return result

    def to_yaml(self, path: Union[str, Path]) -> None:
        """
        Save configuration to YAML file.

        Parameters
        ----------
        path : str or Path
            Path to save YAML file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False)

    def to_json(self, path: Union[str, Path]) -> None:
        """
        Save configuration to JSON file.

        Parameters
        ----------
        path : str or Path
            Path to save JSON file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "AugmentationBuilder":
        """
        Load configuration from YAML file.

        Parameters
        ----------
        path : str or Path
            Path to YAML file.

        Returns
        -------
        AugmentationBuilder
            New AugmentationBuilder instance.
        """
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)

        if "preset" in data:
            return cls(preset=data["preset"])
        elif "transforms" in data:
            return cls(config=data["transforms"])
        else:
            return cls(config=data)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "AugmentationBuilder":
        """
        Load configuration from JSON file.

        Parameters
        ----------
        path : str or Path
            Path to JSON file.

        Returns
        -------
        AugmentationBuilder
            New AugmentationBuilder instance.
        """
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        if "preset" in data:
            return cls(preset=data["preset"])
        elif "transforms" in data:
            return cls(config=data["transforms"])
        else:
            return cls(config=data)

    def _build_compose(self, bbox_format: str = "yolo"):
        import albumentations as A

        transforms = []
        for name, params in self.config.items():
            if not hasattr(A, name):
                raise ValueError(f"Unknown albumentations transform: {name}")
            transforms.append(getattr(A, name)(**params))

        label_fields = ["class_labels"]
        if bbox_format == "yolo":
            return A.Compose(
                transforms,
                bbox_params=A.BboxParams(
                    format="yolo", label_fields=label_fields, min_visibility=0.3
                ),
            )
        return A.Compose(
            transforms,
            bbox_params=A.BboxParams(format="coco", label_fields=label_fields, min_visibility=0.3),
        )

    def apply(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        num_augmented: int = 2,
        splits: Optional[List[str]] = None,
        num_workers: Optional[int] = None,
        augmentation_ratio: Optional[float] = None,
        max_original_samples: Optional[int] = None,
        prioritize_rare_classes: bool = False,
        seed: int = 42,
    ) -> str:
        """
        Apply augmentations to a dataset, generating new augmented images.

        Parameters
        ----------
        input_path : str or Path
            Input dataset path (YOLO or COCO).
        output_path : str or Path
            Output directory for augmented dataset.
        num_augmented : int
            Number of augmented copies per original image.
            Example: With 1000 original images and num_augmented=2,
            generates 2000 augmented images (2 per original).
        splits : list of str, optional
            Splits to augment. Defaults to ["train"].
        num_workers : int, optional
            Number of parallel workers. Defaults to min(32, os.cpu_count()).
        augmentation_ratio : float, optional
            Add augmented data as fraction of train size (e.g. 0.25 = 25% extra).
            Calculates max_original_samples automatically.
            Overrides max_original_samples if provided.
        max_original_samples : int, optional
            Maximum number of original images to select for augmentation.
            Limits which original images are augmented, not total generated.
            Example: With 1000 images, max_original_samples=500, num_augmented=2:
            - All 1000 original images are kept
            - 500 original images are augmented (each produces 2 copies)
            - Total: 1000 original + 1000 augmented = 2000 images
        prioritize_rare_classes : bool
            Prioritize images with rare categories when capping samples.
        seed : int
            Random seed for reproducibility.

        Returns
        -------
        str
            Path to augmented dataset.
        """
        from nectar.ai.detection.datasets.format import FormatDetector

        random.seed(seed)
        np.random.seed(seed)

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        if num_workers is None:
            num_workers = min(32, os.cpu_count() or 1)

        fmt = FormatDetector(str(input_path)).detect()
        if splits is None:
            splits = ["train"]

        if fmt == "yolo":
            return self._apply_yolo(
                input_path,
                output_path,
                num_augmented,
                splits,
                num_workers,
                augmentation_ratio,
                max_original_samples,
                prioritize_rare_classes,
                seed,
            )
        elif fmt == "coco":
            return self._apply_coco(
                input_path,
                output_path,
                num_augmented,
                splits,
                num_workers,
                augmentation_ratio,
                max_original_samples,
                prioritize_rare_classes,
                seed,
            )
        else:
            raise ValueError(f"Cannot detect dataset format at {input_path}")

    def _apply_yolo(
        self,
        input_path: Path,
        output_path: Path,
        num_augmented: int,
        splits: List[str],
        num_workers: int,
        augmentation_ratio: Optional[float],
        max_original_samples: Optional[int],
        prioritize_rare_classes: bool,
        seed: int,
    ) -> str:
        yaml_path = input_path / "data.yaml"
        with open(yaml_path) as f:
            dataset_config = yaml.safe_load(f)

        class_names = dataset_config.get("names", {})
        yaml_dir = yaml_path.parent

        for split in splits:
            if split not in dataset_config:
                logger.warning("Split '%s' not in data.yaml, skipping", split)
                continue

            split_rel = dataset_config[split]
            images_dir = (yaml_dir / split_rel).resolve()
            labels_dir = images_dir.parent / "labels"

            if not images_dir.exists():
                images_dir = yaml_dir / split / "images"
                labels_dir = yaml_dir / split / "labels"

            if not images_dir.exists():
                logger.warning("Images dir not found for split '%s', skipping", split)
                continue

            out_images = output_path / split / "images"
            out_labels = output_path / split / "labels"
            out_images.mkdir(parents=True, exist_ok=True)
            out_labels.mkdir(parents=True, exist_ok=True)

            image_files = [
                p
                for p in sorted(images_dir.iterdir())
                if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]

            images_to_augment = image_files
            if split == "train":
                if augmentation_ratio is not None:
                    num_train = len(image_files)
                    max_original_samples = max(
                        1,
                        min(
                            num_train,
                            int(round(augmentation_ratio * num_train / num_augmented)),
                        ),
                    )
                    logger.info(
                        "Augmentation ratio %.2f: augmenting %d images (x%d) -> ~%d extra (~%.0f%% of %d)",
                        augmentation_ratio,
                        max_original_samples,
                        num_augmented,
                        max_original_samples * num_augmented,
                        100 * augmentation_ratio,
                        num_train,
                    )

                if max_original_samples and len(image_files) > max_original_samples:
                    if prioritize_rare_classes:
                        images_to_augment = self._select_rare_class_yolo_images(
                            image_files, labels_dir, max_original_samples
                        )
                    else:
                        images_to_augment = random.sample(image_files, max_original_samples)

            logger.info(
                "Augmenting %d images in %s split (%dx)",
                len(images_to_augment),
                split,
                num_augmented,
            )

            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for img_path in images_to_augment:
                    label_path = labels_dir / f"{img_path.stem}.txt"
                    futures.append(
                        executor.submit(
                            _augment_yolo_image_worker,
                            str(img_path),
                            str(label_path),
                            str(out_images),
                            str(out_labels),
                            self.config,
                            num_augmented,
                        )
                    )

                for future in tqdm(
                    as_completed(futures), total=len(futures), desc=f"Augmenting {split}"
                ):
                    future.result()

        # Copy non-augmented splits
        for split in dataset_config:
            if split in ("path", "names", "nc", "roboflow") or split in splits:
                continue
            split_rel = dataset_config[split]
            src_images = (yaml_dir / split_rel).resolve()
            src_labels = src_images.parent / "labels"
            if not src_images.exists():
                src_images = yaml_dir / split / "images"
                src_labels = yaml_dir / split / "labels"
            if not src_images.exists():
                continue

            dst_images = output_path / split / "images"
            dst_labels = output_path / split / "labels"
            dst_images.mkdir(parents=True, exist_ok=True)
            dst_labels.mkdir(parents=True, exist_ok=True)
            for p in src_images.iterdir():
                shutil.copy2(p, dst_images / p.name)
            if src_labels.exists():
                for p in src_labels.iterdir():
                    shutil.copy2(p, dst_labels / p.name)

        new_yaml = {
            "path": str(output_path.resolve()),
            "names": class_names,
            "nc": dataset_config.get("nc", len(class_names)),
        }
        for split in ["train", "val", "test"]:
            if (output_path / split / "images").exists():
                new_yaml[split] = f"{split}/images"

        with open(output_path / "data.yaml", "w") as f:
            yaml.dump(new_yaml, f, sort_keys=False)

        total = sum(
            len(list((output_path / s / "images").iterdir()))
            for s in ["train", "val", "test"]
            if (output_path / s / "images").exists()
        )
        logger.info("Augmented dataset: %d total images at %s", total, output_path)
        return str(output_path)

    def _apply_coco(
        self,
        input_path: Path,
        output_path: Path,
        num_augmented: int,
        splits: List[str],
        num_workers: int,
        augmentation_ratio: Optional[float],
        max_original_samples: Optional[int],
        prioritize_rare_classes: bool,
        seed: int,
    ) -> str:
        for split_dir in sorted(input_path.iterdir()):
            if not split_dir.is_dir():
                continue
            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            split = split_dir.name
            out_dir = output_path / split
            out_dir.mkdir(parents=True, exist_ok=True)

            with open(ann_file) as f:
                coco_data = json.load(f)

            if split not in splits:
                shutil.copytree(split_dir, out_dir, dirs_exist_ok=True)
                continue

            img_id_to_anns = defaultdict(list)
            for ann in coco_data["annotations"]:
                img_id_to_anns[ann["image_id"]].append(ann)

            all_images = coco_data["images"]
            all_annotations = coco_data["annotations"]

            images_to_augment = all_images
            if split == "train":
                if augmentation_ratio is not None:
                    num_train = len(all_images)
                    max_original_samples = max(
                        1,
                        min(
                            num_train,
                            int(round(augmentation_ratio * num_train / num_augmented)),
                        ),
                    )
                    logger.info(
                        "Augmentation ratio %.2f: augmenting %d images (x%d) -> ~%d extra (~%.0f%% of %d)",
                        augmentation_ratio,
                        max_original_samples,
                        num_augmented,
                        max_original_samples * num_augmented,
                        100 * augmentation_ratio,
                        num_train,
                    )

                if max_original_samples and len(all_images) > max_original_samples:
                    if prioritize_rare_classes:
                        images_to_augment = self._select_rare_class_images(
                            all_images, all_annotations, max_original_samples
                        )
                    else:
                        images_with_ann_count = [
                            (img, len(img_id_to_anns.get(img["id"], []))) for img in all_images
                        ]
                        images_with_ann_count.sort(key=lambda x: x[1], reverse=True)
                        top_images = [
                            img for img, _ in images_with_ann_count[: max_original_samples // 2]
                        ]
                        remaining = [
                            img for img, _ in images_with_ann_count[max_original_samples // 2 :]
                        ]
                        random_images = random.sample(
                            remaining, max_original_samples - len(top_images)
                        )
                        images_to_augment = top_images + random_images
                        random.shuffle(images_to_augment)

            new_images = list(all_images)
            new_annotations = list(all_annotations)
            next_img_id = max((img["id"] for img in all_images), default=0) + 1
            next_ann_id = max((ann["id"] for ann in all_annotations), default=0) + 1

            logger.info(
                "Augmenting %d images in %s split (%dx)",
                len(images_to_augment),
                split,
                num_augmented,
            )

            with ProcessPoolExecutor(max_workers=min(32, num_workers)) as executor:
                copy_futures = []
                for img_info in all_images:
                    src_img = split_dir / img_info["file_name"]
                    if not src_img.exists():
                        src_img = split_dir / "images" / img_info["file_name"]
                    dst_img = out_dir / img_info["file_name"]
                    if src_img.exists() and not dst_img.exists():
                        copy_futures.append(executor.submit(shutil.copy2, src_img, dst_img))

                for _ in tqdm(
                    as_completed(copy_futures),
                    total=len(copy_futures),
                    desc=f"Copying original {split} images",
                ):
                    pass

            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = []
                for img_info in images_to_augment:
                    futures.append(
                        executor.submit(
                            _augment_coco_image_worker,
                            img_info,
                            str(split_dir),
                            str(out_dir),
                            dict(img_id_to_anns),
                            self.config,
                            num_augmented,
                            next_img_id,
                            next_ann_id,
                        )
                    )
                    next_img_id += num_augmented
                    next_ann_id += num_augmented * 100

                all_new_images = []
                all_new_annotations = []
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc=f"Augmenting {split}",
                ):
                    new_imgs, new_anns = future.result()
                    all_new_images.extend(new_imgs)
                    all_new_annotations.extend(new_anns)

            new_images.extend(all_new_images)
            new_annotations.extend(all_new_annotations)

            for i, ann in enumerate(new_annotations):
                ann["id"] = i + 1

            out_ann = out_dir / "_annotations.coco.json"
            with open(out_ann, "w") as f:
                json.dump(
                    {
                        "images": new_images,
                        "annotations": new_annotations,
                        "categories": coco_data["categories"],
                    },
                    f,
                    indent=2,
                )

        logger.info("Augmented COCO dataset at %s", output_path)
        return str(output_path)

    def _select_rare_class_images(
        self, all_images: List[Dict], all_annotations: List[Dict], max_samples: int
    ) -> List[Dict]:
        category_counts = Counter()
        image_categories = defaultdict(set)

        for ann in all_annotations:
            category_counts[ann["category_id"]] += 1
            image_categories[ann["image_id"]].add(ann["category_id"])

        image_rarity_scores = []
        for img in all_images:
            img_id = img["id"]
            categories_in_image = image_categories.get(img_id, set())

            if not categories_in_image:
                rarity_score = float("inf")
            else:
                rarity_score = sum(category_counts.get(cat_id, 1) for cat_id in categories_in_image)
                rarity_score = rarity_score / len(categories_in_image)

            image_rarity_scores.append((img, rarity_score))

        image_rarity_scores.sort(key=lambda x: x[1])
        valid_scored = [(img, score) for img, score in image_rarity_scores if score != float("inf")]

        rare_sample_size = int(max_samples * 0.7)
        random_sample_size = max_samples - rare_sample_size

        if len(valid_scored) >= rare_sample_size:
            rare_images = [img for img, _ in valid_scored[:rare_sample_size]]
            remaining = [img for img, _ in valid_scored[rare_sample_size:]]
            if len(remaining) >= random_sample_size:
                random_images = random.sample(remaining, random_sample_size)
            else:
                random_images = remaining
                additional_needed = random_sample_size - len(random_images)
                if additional_needed > 0:
                    extra_rare = [
                        img
                        for img, _ in valid_scored[
                            len(rare_images) : len(rare_images) + additional_needed
                        ]
                    ]
                    random_images.extend(extra_rare)
            selected = rare_images + random_images
        else:
            selected = [img for img, _ in valid_scored[:max_samples]]

        random.shuffle(selected)
        return selected

    def _select_rare_class_yolo_images(
        self, image_files: List[Path], labels_dir: Path, max_samples: int
    ) -> List[Path]:
        category_counts = Counter()
        image_categories = defaultdict(set)

        for img_path in image_files:
            label_path = labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue
            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cat_id = int(parts[0])
                        category_counts[cat_id] += 1
                        image_categories[img_path].add(cat_id)

        image_rarity_scores = []
        for img_path in image_files:
            categories_in_image = image_categories.get(img_path, set())

            if not categories_in_image:
                rarity_score = float("inf")
            else:
                rarity_score = sum(category_counts.get(cat_id, 1) for cat_id in categories_in_image)
                rarity_score = rarity_score / len(categories_in_image)

            image_rarity_scores.append((img_path, rarity_score))

        image_rarity_scores.sort(key=lambda x: x[1])
        valid_scored = [(img, score) for img, score in image_rarity_scores if score != float("inf")]

        rare_sample_size = int(max_samples * 0.7)
        random_sample_size = max_samples - rare_sample_size

        if len(valid_scored) >= rare_sample_size:
            rare_images = [img for img, _ in valid_scored[:rare_sample_size]]
            remaining = [img for img, _ in valid_scored[rare_sample_size:]]
            if len(remaining) >= random_sample_size:
                random_images = random.sample(remaining, random_sample_size)
            else:
                random_images = remaining
                additional_needed = random_sample_size - len(random_images)
                if additional_needed > 0:
                    extra_rare = [
                        img
                        for img, _ in valid_scored[
                            len(rare_images) : len(rare_images) + additional_needed
                        ]
                    ]
                    random_images.extend(extra_rare)
            selected = rare_images + random_images
        else:
            selected = [img for img, _ in valid_scored[:max_samples]]

        random.shuffle(selected)
        return selected

    def validate(self) -> bool:
        """
        Validate augmentation configuration.

        Returns
        -------
        bool
            True if valid, False otherwise.
        """
        try:
            import albumentations as A

            transforms = []
            for name, params in self.config.items():
                if not hasattr(A, name):
                    logger.warning(f"Unknown transform: {name}")
                    return False
                transform_class = getattr(A, name)
                transforms.append(transform_class(**params))

            A.Compose(transforms)
            return True
        except ImportError:
            logger.warning("albumentations not installed, skipping validation")
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
