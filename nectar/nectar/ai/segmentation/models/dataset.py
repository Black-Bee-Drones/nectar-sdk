"""Segmentation dataset loaders.

- Evaluation: YOLO-seg / COCO-seg → ``sv.Detections`` with masks
- Training (MaskFormer / Mask2Former): COCO polygons → instance maps for
  HuggingFace image processors (``segmentation_maps`` + ``instance_id_to_semantic_id``)
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
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

# Background / void in MaskFormer instance maps (processor ``ignore_index``).
_IGNORE_INDEX = 255


class SegmentationDataset:
    """
    Dataset of images + ground-truth ``sv.Detections`` with masks.

    Parameters
    ----------
    images : list of str
        Image file paths.
    annotations : list of sv.Detections
        Ground-truth detections (xyxy + class_id + mask).
    classes : list of str
        Class names indexed by class id.
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
            yield path, image, self.annotations[i]


def load_segmentation_dataset(
    dataset_path: str,
    dataset_type: str = "auto",
    split: str = "test",
) -> SegmentationDataset:
    """
    Load a segmentation dataset for evaluation.

    Parameters
    ----------
    dataset_path : str
        Root directory of the dataset.
    dataset_type : str
        ``"coco"``, ``"yolo"``, or ``"auto"`` (default).
    split : str
        Dataset split name (``"test"``, ``"valid"``, ``"train"``).

    Returns
    -------
    SegmentationDataset
    """
    dataset_path = Path(dataset_path)

    if dataset_path.suffix in (".yaml", ".yml"):
        dataset_path = dataset_path.parent

    if dataset_type == "auto":
        if (dataset_path / split / "_annotations.coco.json").exists():
            dataset_type = "coco"
        elif (dataset_path / "data.yaml").exists():
            dataset_type = "yolo"
        else:
            for name in ("valid", "val", "test", "train"):
                if (dataset_path / name / "_annotations.coco.json").exists():
                    dataset_type = "coco"
                    break
            else:
                dataset_type = "yolo"

    if dataset_type == "coco":
        return _load_coco_seg_dataset(dataset_path, split)
    elif dataset_type == "yolo":
        return _load_yolo_seg_dataset(dataset_path, split)
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")


# ---------------------------------------------------------------------------
# YOLO-seg loader
# ---------------------------------------------------------------------------


def _load_yolo_seg_dataset(dataset_path: Path, split: str) -> SegmentationDataset:
    import yaml

    yaml_path = dataset_path / "data.yaml"
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    names = data.get("names", {})
    classes = names if isinstance(names, list) else list(names.values())

    # Resolve the split's images directory. Honor the YAML's optional `path:`
    # root (Ultralytics convention) and fall back to stripping leading '..'
    # segments to handle Roboflow's YOLOv8 quirk where exports contain paths
    # like '../test/images' that assume an outer datasets_dir.
    root = dataset_path
    if data.get("path"):
        p = Path(data["path"])
        root = p if p.is_absolute() else (dataset_path / p).resolve()

    split_rel = data.get(split, data.get("val", "valid"))
    if Path(split_rel).is_absolute():
        images_dir = Path(split_rel)
    else:
        images_dir = (root / split_rel).resolve()
        if not images_dir.exists():
            stripped = tuple(p for p in Path(split_rel).parts if p != "..")
            images_dir = root.joinpath(*stripped) if stripped else root

    labels_dir = images_dir.parent / "labels"
    if not labels_dir.exists():
        labels_dir = images_dir.parent.parent / "labels" / images_dir.name

    images: List[str] = []
    annotations: List["sv.Detections"] = []

    for img_path in sorted(images_dir.glob("*.*")):
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            continue

        images.append(str(img_path))
        label_path = labels_dir / f"{img_path.stem}.txt"

        if not label_path.exists():
            annotations.append(sv.Detections.empty())
            continue

        with Image.open(img_path) as im:
            w, h = im.size

        xyxy_list, class_ids, masks = [], [], []

        with open(label_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 7:
                    continue
                cls_id = int(parts[0])
                coords = [float(v) for v in parts[1:]]
                if len(coords) % 2 != 0:
                    coords = coords[:-1]

                pts = np.array(
                    [
                        [int(coords[i] * w), int(coords[i + 1] * h)]
                        for i in range(0, len(coords), 2)
                    ],
                    dtype=np.int32,
                )
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.fillPoly(mask, [pts], 1)
                mask_bool = mask.astype(bool)

                ys, xs = np.where(mask_bool)
                if len(xs) == 0:
                    continue
                x1, y1, x2, y2 = float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())

                xyxy_list.append([x1, y1, x2, y2])
                class_ids.append(cls_id)
                masks.append(mask_bool)

        if xyxy_list:
            det = sv.Detections(
                xyxy=np.array(xyxy_list, dtype=np.float32),
                class_id=np.array(class_ids, dtype=int),
                mask=np.array(masks, dtype=bool),
            )
        else:
            det = sv.Detections.empty()

        annotations.append(det)

    return SegmentationDataset(images, annotations, classes)


# ---------------------------------------------------------------------------
# COCO-seg loader
# ---------------------------------------------------------------------------


def _load_coco_seg_dataset(dataset_path: Path, split: str) -> SegmentationDataset:
    split_dir = dataset_path / split
    ann_file = split_dir / "_annotations.coco.json"

    if not ann_file.exists():
        for alt in ("valid", "val", "test"):
            alt_file = dataset_path / alt / "_annotations.coco.json"
            if alt_file.exists():
                split_dir = dataset_path / alt
                ann_file = alt_file
                break
        else:
            raise FileNotFoundError(f"Annotations not found: {ann_file}")

    with open(ann_file, encoding="utf-8") as f:
        coco = json.load(f)

    categories = sorted(coco["categories"], key=lambda c: c["id"])
    classes = [c["name"] for c in categories]
    id_to_idx = {c["id"]: i for i, c in enumerate(categories)}

    img_id_to_anns: dict = {}
    for ann in coco["annotations"]:
        img_id_to_anns.setdefault(ann["image_id"], []).append(ann)

    images: List[str] = []
    annotations: List["sv.Detections"] = []

    for img_info in coco["images"]:
        img_path = split_dir / img_info["file_name"]
        if not img_path.exists():
            img_path = split_dir / "images" / img_info["file_name"]
        if not img_path.exists():
            img_path = split_dir / "images" / Path(img_info["file_name"]).name
        if not img_path.exists():
            continue

        images.append(str(img_path))
        anns = img_id_to_anns.get(img_info["id"], [])
        w = img_info.get("width", 1)
        h = img_info.get("height", 1)

        xyxy_list, class_ids, masks = [], [], []
        for ann in anns:
            seg = ann.get("segmentation")
            if seg and isinstance(seg, list) and len(seg) > 0 and isinstance(seg[0], list):
                flat = seg[0]
                if len(flat) < 6:
                    continue
                pts = np.array(
                    [[int(flat[i]), int(flat[i + 1])] for i in range(0, len(flat), 2)],
                    dtype=np.int32,
                )
                mask = np.zeros((h, w), dtype=np.uint8)
                cv2.fillPoly(mask, [pts], 1)
                mask_bool = mask.astype(bool)

                ys, xs = np.where(mask_bool)
                if len(xs) == 0:
                    continue
                x1, y1, x2, y2 = float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
            else:
                bx, by, bw, bh = ann.get("bbox", [0, 0, 0, 0])
                x1, y1, x2, y2 = bx, by, bx + bw, by + bh
                mask_bool = None

            xyxy_list.append([x1, y1, x2, y2])
            class_ids.append(id_to_idx.get(ann["category_id"], 0))
            if mask_bool is not None:
                masks.append(mask_bool)

        if xyxy_list:
            det_kwargs = {
                "xyxy": np.array(xyxy_list, dtype=np.float32),
                "class_id": np.array(class_ids, dtype=int),
            }
            if masks and len(masks) == len(xyxy_list):
                det_kwargs["mask"] = np.array(masks, dtype=bool)
            det = sv.Detections(**det_kwargs)
        else:
            det = sv.Detections.empty()

        annotations.append(det)

    return SegmentationDataset(images, annotations, classes)


# ---------------------------------------------------------------------------
# COCO → MaskFormer / Mask2Former training dataset
# ---------------------------------------------------------------------------


def instance_seg_collate_fn(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Collate MaskFormer-style batches (variable-length mask / class labels)."""
    encoding: Dict[str, Any] = {
        "pixel_values": torch.stack([x["pixel_values"] for x in batch]),
        "mask_labels": [x["mask_labels"] for x in batch],
        "class_labels": [x["class_labels"] for x in batch],
    }
    if "pixel_mask" in batch[0] and batch[0]["pixel_mask"] is not None:
        encoding["pixel_mask"] = torch.stack([x["pixel_mask"] for x in batch])
    return encoding


class CocoInstanceSegDataset(Dataset):
    """
    COCO-seg dataset for MaskFormer / Mask2Former training.

    Converts polygon (or RLE) annotations into an instance segmentation map and
    feeds ``segmentation_maps`` + ``instance_id_to_semantic_id`` to the HuggingFace
    image processor

    Parameters
    ----------
    img_dir : str
        Directory containing images (or an ``images/`` subdirectory).
    annotations_file : str
        Path to COCO JSON with a ``segmentation`` field per annotation.
    image_processor : Any
        HuggingFace MaskFormer / Mask2Former image processor.
    train : bool, optional
        Unused flag kept for API parity with ``CocoDetectionDataset``.
    max_samples : int, optional
        Cap on the number of images.
    seed : int, optional
        Sampling seed when ``max_samples`` is set.
    ignore_index : int, optional
        Background / void label passed to the processor (default 255).
    """

    def __init__(
        self,
        img_dir: str,
        annotations_file: str,
        image_processor: Any,
        train: bool = True,
        max_samples: Optional[int] = None,
        seed: int = 42,
        ignore_index: int = _IGNORE_INDEX,
    ):
        self.img_dir = Path(img_dir)
        self.image_processor = image_processor
        self.train = train
        self.seed = seed
        self.ignore_index = ignore_index

        with open(annotations_file, encoding="utf-8") as f:
            coco_data = json.load(f)

        self.images = coco_data["images"]
        self.annotations = coco_data["annotations"]
        self.categories = coco_data["categories"]

        self.id2label = {cat["id"]: cat["name"] for cat in self.categories}
        self.label2id = {cat["name"]: cat["id"] for cat in self.categories}

        cat_ids = sorted(self.id2label.keys())
        self.old_to_new_id = {old: new for new, old in enumerate(cat_ids)}
        self.id2label = {new: self.id2label[old] for old, new in self.old_to_new_id.items()}
        self.label2id = {v: k for k, v in self.id2label.items()}

        self.img_id_to_anns: Dict[int, list] = {}
        for ann in self.annotations:
            self.img_id_to_anns.setdefault(ann["image_id"], []).append(ann)

        self.images = [img for img in self.images if img["id"] in self.img_id_to_anns]

        if max_samples and max_samples < len(self.images):
            random.seed(seed)
            self.images = random.sample(self.images, max_samples)

        logger.info(
            "Loaded %d images with %d classes for instance segmentation",
            len(self.images),
            len(self.categories),
        )

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        img_info = self.images[idx]
        img_id = img_info["id"]
        img_path = self._find_image_path(img_info["file_name"])
        image = Image.open(img_path).convert("RGB")
        width = int(img_info.get("width") or image.width)
        height = int(img_info.get("height") or image.height)

        instance_map, instance_id_to_semantic_id = self._build_instance_map(
            self.img_id_to_anns.get(img_id, []), height, width
        )

        encoded = self.image_processor(
            images=image,
            segmentation_maps=instance_map,
            instance_id_to_semantic_id=instance_id_to_semantic_id,
            return_tensors="pt",
            ignore_index=self.ignore_index,
        )

        item: Dict[str, Any] = {
            "pixel_values": encoded["pixel_values"][0],
            "mask_labels": encoded["mask_labels"][0],
            "class_labels": encoded["class_labels"][0],
        }
        if "pixel_mask" in encoded:
            item["pixel_mask"] = encoded["pixel_mask"][0]
        return item

    def _build_instance_map(
        self, anns: List[dict], height: int, width: int
    ) -> tuple[np.ndarray, Dict[int, int]]:
        """Rasterize COCO polygons/RLE into an instance map (ignore_index = background)."""
        instance_map = np.full((height, width), self.ignore_index, dtype=np.int32)
        instance_id_to_semantic_id: Dict[int, int] = {}
        next_instance_id = 1

        for ann in anns:
            if ann.get("iscrowd", 0):
                continue
            mask = self._ann_to_mask(ann, height, width)
            if mask is None or not mask.any():
                continue

            class_id = self.old_to_new_id.get(ann["category_id"], 0)
            # Later instances win on overlaps (standard for dense instance maps).
            instance_map[mask] = next_instance_id
            instance_id_to_semantic_id[next_instance_id] = class_id
            next_instance_id += 1

        return instance_map, instance_id_to_semantic_id

    @staticmethod
    def _ann_to_mask(ann: dict, height: int, width: int) -> Optional[np.ndarray]:
        """Convert a COCO segmentation field to a boolean mask."""
        seg = ann.get("segmentation")
        if not seg:
            return None

        mask = np.zeros((height, width), dtype=np.uint8)

        if isinstance(seg, list):
            # Polygon(s): list of flat [x1,y1,...] rings
            for poly in seg:
                if not isinstance(poly, (list, tuple)) or len(poly) < 6:
                    continue
                pts = np.array(poly, dtype=np.float32).reshape(-1, 2)
                pts = np.round(pts).astype(np.int32)
                cv2.fillPoly(mask, [pts], 1)
            return mask.astype(bool)

        if isinstance(seg, dict) and "counts" in seg:
            try:
                from pycocotools import mask as mask_utils

                rle = seg
                if isinstance(rle.get("counts"), list):
                    rle = mask_utils.frPyObjects(rle, height, width)
                return mask_utils.decode(rle).astype(bool)
            except ImportError:
                logger.warning("pycocotools required to decode RLE segmentations; skipping ann")
                return None

        return None

    def _find_image_path(self, filename: str) -> Path:
        """Resolve an image path under ``img_dir``."""
        direct_path = self.img_dir / filename
        if direct_path.exists():
            return direct_path

        images_path = self.img_dir / "images" / filename
        if images_path.exists():
            return images_path

        name_only = Path(filename).name
        for path in self.img_dir.rglob(name_only):
            return path

        raise FileNotFoundError(f"Image not found: {filename}")
