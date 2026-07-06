"""Dataset utilities for detection models."""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        self.id2label = {new: self.id2label[old] for old, new in self.old_to_new_id.items()}
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

        logger.info(f"Loaded {len(self.images)} images with {len(self.categories)} classes")

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        img_info = self.images[idx]
        img_id = img_info["id"]

        # Find image file
        img_path = self._find_image_path(img_info["file_name"])
        image = Image.open(img_path).convert("RGB")

        # Get annotations
        anns = self.img_id_to_anns.get(img_id, [])

        # Build COCO-wrapped annotations (required by modern transformers processors)
        coco_annotations = []
        for ann in anns:
            coco_annotations.append(
                {
                    "image_id": img_id,
                    "category_id": self.old_to_new_id.get(ann["category_id"], 0),
                    "bbox": ann["bbox"],  # [x, y, w, h] COCO format
                    "area": ann.get("area", ann["bbox"][2] * ann["bbox"][3]),
                    "iscrowd": 0,
                }
            )

        target = {"image_id": img_id, "annotations": coco_annotations}

        # Process with image processor (pass numpy array for compatibility)
        result = self.image_processor(
            images=np.array(image), annotations=target, return_tensors="pt"
        )

        # Remove batch dimension
        return {
            k: v[0] if isinstance(v, (list, torch.Tensor)) and len(v) > 0 else v
            for k, v in result.items()
        }

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
    """Collate function for DataLoader with pixel_mask support."""
    pixel_values = torch.stack([x["pixel_values"] for x in batch])
    encoding = {"pixel_values": pixel_values}

    if "pixel_mask" in batch[0]:
        encoding["pixel_mask"] = torch.stack([x["pixel_mask"] for x in batch])

    encoding["labels"] = [x["labels"] for x in batch]
    return encoding


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

    names = data.get("names", {})
    classes = names if isinstance(names, list) else list(names.values())

    # Resolve the split's directory. Honor the YAML's optional `path:` root
    # (Ultralytics convention) and fall back to stripping leading '..'
    # segments to handle Roboflow's YOLOv8 quirk where exports contain paths
    # like '../test/images' that assume an outer datasets_dir.
    root = dataset_path
    if data.get("path"):
        p = Path(data["path"])
        root = p if p.is_absolute() else (dataset_path / p).resolve()

    split_path = data.get(split, data.get("val", "valid"))
    if Path(split_path).is_absolute():
        split_dir = Path(split_path)
    else:
        split_dir = (root / split_path).resolve()
        if not split_dir.exists():
            stripped = tuple(p for p in Path(split_path).parts if p != "..")
            split_dir = root.joinpath(*stripped) if stripped else root

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
                    if len(parts) < 5:
                        continue
                    try:
                        cls_id = int(parts[0])
                        coords = [float(x) for x in parts[1:]]
                    except ValueError:
                        continue

                    if len(coords) == 4:
                        # YOLO bbox: class cx cy w h (normalized).
                        cx, cy, bw, bh = coords
                        x1 = (cx - bw / 2) * width
                        y1 = (cy - bh / 2) * height
                        x2 = (cx + bw / 2) * width
                        y2 = (cy + bh / 2) * height
                    elif len(coords) >= 6 and len(coords) % 2 == 0:
                        # YOLO polygon (segmentation/OBB): class x1 y1 x2 y2 ...
                        # Roboflow exports segmentation projects this way even
                        # when format=yolo. Reduce to bbox via min/max.
                        xs = [coords[i] * width for i in range(0, len(coords), 2)]
                        ys = [coords[i] * height for i in range(1, len(coords), 2)]
                        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
                    else:
                        continue

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
