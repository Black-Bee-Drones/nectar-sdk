"""Dataset utilities for detection models."""

import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

try:
    import torch
    from torch.utils.data import Dataset
except ImportError:
    torch = None
    Dataset = object

try:
    import supervision as sv
except ImportError:
    sv = None

logger = logging.getLogger(__name__)


class CocoDetectionDataset(Dataset):
    """
    COCO format dataset for object detection.

    Parameters
    ----------
    img_dir : str
        Directory containing images.
    annotations_file : str
        Path to COCO format annotations JSON.
    image_processor : Any
        Image processor (e.g., from HuggingFace).
    train : bool, optional
        Whether this is training dataset. Defaults to True.
    max_samples : int, optional
        Maximum number of samples to use.
    seed : int, optional
        Random seed for sampling. Defaults to 42.

    Examples
    --------
    >>> from transformers import AutoImageProcessor
    >>> processor = AutoImageProcessor.from_pretrained("facebook/detr-resnet-50")
    >>> dataset = CocoDetectionDataset("data/train", "annotations.json", processor)
    """

    def __init__(
        self,
        img_dir: str,
        annotations_file: str,
        image_processor: Any,
        train: bool = True,
        max_samples: Optional[int] = None,
        seed: int = 42,
    ):
        self.img_dir = Path(img_dir)
        self.image_processor = image_processor
        self.train = train
        self.seed = seed

        # Load annotations
        with open(annotations_file, "r") as f:
            coco_data = json.load(f)

        self.images = coco_data["images"]
        self.annotations = coco_data["annotations"]
        self.categories = coco_data["categories"]

        # Build mappings
        self.id2label = {cat["id"]: cat["name"] for cat in self.categories}
        self.label2id = {cat["name"]: cat["id"] for cat in self.categories}

        # Remap to sequential IDs (0-indexed)
        cat_ids = sorted(self.id2label.keys())
        self.old_to_new_id = {old: new for new, old in enumerate(cat_ids)}
        self.id2label = {
            new: self.id2label[old] for old, new in self.old_to_new_id.items()
        }
        self.label2id = {v: k for k, v in self.id2label.items()}

        # Build image -> annotations mapping
        self.img_id_to_anns = {}
        for ann in self.annotations:
            img_id = ann["image_id"]
            if img_id not in self.img_id_to_anns:
                self.img_id_to_anns[img_id] = []
            self.img_id_to_anns[img_id].append(ann)

        # Filter images with annotations
        self.images = [img for img in self.images if img["id"] in self.img_id_to_anns]

        # Sample if needed
        if max_samples and max_samples < len(self.images):
            random.seed(seed)
            self.images = random.sample(self.images, max_samples)

        logger.info(
            f"Loaded {len(self.images)} images with {len(self.categories)} classes"
        )

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        img_info = self.images[idx]
        img_id = img_info["id"]

        # Find image file
        img_path = self._find_image_path(img_info["file_name"])
        image = Image.open(img_path).convert("RGB")
        width, height = image.size

        # Get annotations
        anns = self.img_id_to_anns.get(img_id, [])

        # Build target
        boxes = []
        class_labels = []
        areas = []

        for ann in anns:
            x, y, w, h = ann["bbox"]

            # Convert to center format (normalized)
            x_center = (x + w / 2) / width
            y_center = (y + h / 2) / height
            w_norm = w / width
            h_norm = h / height

            boxes.append([x_center, y_center, w_norm, h_norm])
            class_labels.append(self.old_to_new_id.get(ann["category_id"], 0))
            areas.append(ann.get("area", w * h))

        target = {
            "boxes": np.array(boxes, dtype=np.float32),
            "class_labels": np.array(class_labels, dtype=np.int64),
            "image_id": img_id,
            "area": np.array(areas, dtype=np.float32),
            "iscrowd": np.zeros(len(boxes), dtype=np.int64),
            "orig_size": np.array([height, width], dtype=np.int64),
            "size": np.array([height, width], dtype=np.int64),
        }

        # Process with image processor
        encoding = self.image_processor(
            images=image, annotations=[target], return_tensors="pt"
        )

        # Remove batch dimension
        pixel_values = encoding["pixel_values"].squeeze(0)
        labels = encoding["labels"][0] if "labels" in encoding else target

        return {"pixel_values": pixel_values, "labels": labels}

    def _find_image_path(self, filename: str) -> Path:
        """Find image file in directory."""
        # Try direct path
        direct_path = self.img_dir / filename
        if direct_path.exists():
            return direct_path

        # Try in images subdirectory
        images_path = self.img_dir / "images" / filename
        if images_path.exists():
            return images_path

        # Search for file
        for path in self.img_dir.rglob(filename):
            return path

        raise FileNotFoundError(f"Image not found: {filename}")


def collate_fn(batch: List[Dict]) -> Dict[str, Any]:
    """Collate function for DataLoader."""
    pixel_values = torch.stack([x["pixel_values"] for x in batch])
    labels = [x["labels"] for x in batch]
    return {"pixel_values": pixel_values, "labels": labels}


class DetectionDataset:
    """
    Generic detection dataset for evaluation.

    Supports COCO and YOLO formats.

    Parameters
    ----------
    images : List[str]
        List of image paths.
    annotations : List[sv.Detections]
        List of ground truth detections.
    classes : List[str]
        Class names.
    """

    def __init__(
        self,
        images: List[str],
        annotations: List["sv.Detections"],
        classes: List[str],
    ):
        self.images = images
        self.annotations = annotations
        self.classes = classes

    def __len__(self) -> int:
        return len(self.images)

    def __iter__(self):
        for i in range(len(self)):
            path = self.images[i]
            image = np.array(Image.open(path).convert("RGB"))
            annotation = self.annotations[i]
            yield path, image, annotation


def load_detection_dataset(
    dataset_path: str,
    dataset_type: str = "auto",
    split: str = "test",
) -> DetectionDataset:
    """
    Load detection dataset for evaluation.

    Parameters
    ----------
    dataset_path : str
        Path to dataset directory.
    dataset_type : str, optional
        Dataset type ('coco', 'yolo', 'auto'). Defaults to 'auto'.
    split : str, optional
        Dataset split. Defaults to 'test'.

    Returns
    -------
    DetectionDataset
        Loaded dataset.
    """
    dataset_path = Path(dataset_path)

    # Auto-detect format
    if dataset_type == "auto":
        if (dataset_path / split / "_annotations.coco.json").exists():
            dataset_type = "coco"
        elif (dataset_path / "data.yaml").exists():
            dataset_type = "yolo"
        else:
            dataset_type = "coco"

    if dataset_type == "coco":
        return _load_coco_dataset(dataset_path, split)
    elif dataset_type == "yolo":
        return _load_yolo_dataset(dataset_path, split)
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")


def _load_coco_dataset(dataset_path: Path, split: str) -> DetectionDataset:
    """Load COCO format dataset."""
    split_dir = dataset_path / split
    ann_file = split_dir / "_annotations.coco.json"

    if not ann_file.exists():
        raise FileNotFoundError(f"Annotations not found: {ann_file}")

    with open(ann_file) as f:
        data = json.load(f)

    # Build class list
    categories = sorted(data["categories"], key=lambda x: x["id"])
    classes = [cat["name"] for cat in categories]
    id_to_idx = {cat["id"]: i for i, cat in enumerate(categories)}

    # Build image -> annotations mapping
    img_id_to_anns = {}
    for ann in data["annotations"]:
        img_id = ann["image_id"]
        if img_id not in img_id_to_anns:
            img_id_to_anns[img_id] = []
        img_id_to_anns[img_id].append(ann)

    images = []
    annotations = []

    for img_info in data["images"]:
        # Find image
        img_path = split_dir / img_info["file_name"]
        if not img_path.exists():
            img_path = split_dir / "images" / img_info["file_name"]
        if not img_path.exists():
            continue

        images.append(str(img_path))

        # Build detections
        anns = img_id_to_anns.get(img_info["id"], [])

        if anns:
            boxes = []
            class_ids = []
            for ann in anns:
                x, y, w, h = ann["bbox"]
                boxes.append([x, y, x + w, y + h])
                class_ids.append(id_to_idx.get(ann["category_id"], 0))

            detection = sv.Detections(
                xyxy=np.array(boxes, dtype=np.float32),
                class_id=np.array(class_ids, dtype=int),
            )
        else:
            detection = sv.Detections.empty()

        annotations.append(detection)

    return DetectionDataset(images, annotations, classes)


def _load_yolo_dataset(dataset_path: Path, split: str) -> DetectionDataset:
    """Load YOLO format dataset."""
    import yaml

    yaml_path = dataset_path / "data.yaml"
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    classes = list(data.get("names", {}).values())

    # Get split directory
    split_path = data.get(split, data.get("val", "valid"))
    if not Path(split_path).is_absolute():
        split_dir = dataset_path / split_path
    else:
        split_dir = Path(split_path)

    # Get image and label directories
    images_dir = split_dir
    labels_dir = split_dir.parent / "labels"

    if not images_dir.exists():
        images_dir = split_dir / "images"
        labels_dir = split_dir / "labels"

    images = []
    annotations = []

    for img_path in sorted(images_dir.glob("*.*")):
        if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp"]:
            continue

        images.append(str(img_path))

        # Find label file
        label_path = labels_dir / f"{img_path.stem}.txt"

        if label_path.exists():
            img = Image.open(img_path)
            width, height = img.size

            boxes = []
            class_ids = []

            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        x_center = float(parts[1]) * width
                        y_center = float(parts[2]) * height
                        w = float(parts[3]) * width
                        h = float(parts[4]) * height

                        x1 = x_center - w / 2
                        y1 = y_center - h / 2
                        x2 = x_center + w / 2
                        y2 = y_center + h / 2

                        boxes.append([x1, y1, x2, y2])
                        class_ids.append(cls_id)

            if boxes:
                detection = sv.Detections(
                    xyxy=np.array(boxes, dtype=np.float32),
                    class_id=np.array(class_ids, dtype=int),
                )
            else:
                detection = sv.Detections.empty()
        else:
            detection = sv.Detections.empty()

        annotations.append(detection)

    return DetectionDataset(images, annotations, classes)
