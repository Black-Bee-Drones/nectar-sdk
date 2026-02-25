"""Augmentation builder: config presets and image generation."""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import yaml

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
            Number of augmented copies per image.
        splits : list of str, optional
            Splits to augment. Defaults to ["train"].

        Returns
        -------
        str
            Path to augmented dataset.
        """
        from nectar.ai.detection.datasets.format import FormatDetector

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        fmt = FormatDetector(str(input_path)).detect()
        if splits is None:
            splits = ["train"]

        if fmt == "yolo":
            return self._apply_yolo(input_path, output_path, num_augmented, splits)
        elif fmt == "coco":
            return self._apply_coco(input_path, output_path, num_augmented, splits)
        else:
            raise ValueError(f"Cannot detect dataset format at {input_path}")

    def _apply_yolo(
        self, input_path: Path, output_path: Path, num_augmented: int, splits: List[str]
    ) -> str:
        compose = self._build_compose("yolo")
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
            logger.info(
                "Augmenting %d images in %s split (%dx)", len(image_files), split, num_augmented
            )

            for img_path in image_files:
                label_path = labels_dir / f"{img_path.stem}.txt"
                shutil.copy2(img_path, out_images / img_path.name)
                if label_path.exists():
                    shutil.copy2(label_path, out_labels / label_path.name)

                image = cv2.imread(str(img_path))
                if image is None:
                    continue
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                bboxes, class_labels = [], []
                if label_path.exists():
                    with open(label_path) as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                class_labels.append(int(parts[0]))
                                bboxes.append([float(x) for x in parts[1:5]])

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
                            f.write(
                                f"{cls_id} {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n"
                            )

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
        self, input_path: Path, output_path: Path, num_augmented: int, splits: List[str]
    ) -> str:
        compose = self._build_compose("coco")

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

            img_id_to_anns = {}
            for ann in coco_data["annotations"]:
                img_id_to_anns.setdefault(ann["image_id"], []).append(ann)

            new_images = list(coco_data["images"])
            new_annotations = list(coco_data["annotations"])
            next_img_id = max((img["id"] for img in coco_data["images"]), default=0) + 1
            next_ann_id = max((ann["id"] for ann in coco_data["annotations"]), default=0) + 1

            logger.info(
                "Augmenting %d images in %s split (%dx)",
                len(coco_data["images"]),
                split,
                num_augmented,
            )

            for img_info in coco_data["images"]:
                src_img = split_dir / img_info["file_name"]
                if not src_img.exists():
                    src_img = split_dir / "images" / img_info["file_name"]
                shutil.copy2(src_img, out_dir / img_info["file_name"])

                image = cv2.imread(str(src_img))
                if image is None:
                    continue
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

                anns = img_id_to_anns.get(img_info["id"], [])
                bboxes = [ann["bbox"] for ann in anns]
                class_labels = [ann["category_id"] for ann in anns]

                for aug_idx in range(num_augmented):
                    try:
                        result = compose(image=image, bboxes=bboxes, class_labels=class_labels)
                    except Exception:
                        continue

                    aug_name = f"{Path(img_info['file_name']).stem}_aug{aug_idx}{Path(img_info['file_name']).suffix}"
                    aug_img = cv2.cvtColor(result["image"], cv2.COLOR_RGB2BGR)
                    cv2.imwrite(str(out_dir / aug_name), aug_img)

                    aug_img_id = next_img_id
                    next_img_id += 1
                    new_images.append(
                        {
                            "id": aug_img_id,
                            "file_name": aug_name,
                            "width": result["image"].shape[1],
                            "height": result["image"].shape[0],
                        }
                    )

                    for cls_id, bbox in zip(result["class_labels"], result["bboxes"]):
                        new_annotations.append(
                            {
                                "id": next_ann_id,
                                "image_id": aug_img_id,
                                "category_id": cls_id,
                                "bbox": list(bbox),
                                "area": bbox[2] * bbox[3],
                                "iscrowd": 0,
                            }
                        )
                        next_ann_id += 1

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
