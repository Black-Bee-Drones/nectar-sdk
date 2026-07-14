"""Classification dataset loaders for evaluation."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from nectar.ai.classification.datasets.format import IMAGE_EXTENSIONS, resolve_split_dir

logger = logging.getLogger(__name__)


def discover_class_names(dataset_path: str, split: str = "test") -> Dict[int, str]:
    """Discover class names from ImageFolder split directories."""
    root = Path(dataset_path)
    split_dir = resolve_split_dir(root, split)
    class_dirs = sorted([p for p in split_dir.iterdir() if p.is_dir()])
    return {i: d.name for i, d in enumerate(class_dirs)}


def load_classification_dataset(
    dataset_path: str,
    split: str = "test",
    num_samples: Optional[int] = None,
) -> Tuple[List[str], List[int], Dict[int, str]]:
    """
    Load an ImageFolder classification dataset.

    Returns
    -------
    image_paths : List[str]
    labels : List[int]
    class_names : Dict[int, str]
    """
    root = Path(dataset_path)
    split_dir = resolve_split_dir(root, split)
    class_dirs = sorted([p for p in split_dir.iterdir() if p.is_dir()])
    if not class_dirs:
        raise ValueError(f"No class directories found in {split_dir}")

    class_names = {i: d.name for i, d in enumerate(class_dirs)}
    name_to_id = {name: i for i, name in class_names.items()}

    image_paths: List[str] = []
    labels: List[int] = []

    for class_dir in class_dirs:
        class_id = name_to_id[class_dir.name]
        for img_path in sorted(class_dir.rglob("*")):
            if img_path.suffix.lower() in IMAGE_EXTENSIONS and img_path.is_file():
                image_paths.append(str(img_path))
                labels.append(class_id)

    if num_samples is not None and num_samples < len(image_paths):
        image_paths = image_paths[:num_samples]
        labels = labels[:num_samples]

    logger.info(
        "Loaded %d images from %s (%d classes)",
        len(image_paths),
        split_dir,
        len(class_names),
    )
    return image_paths, labels, class_names


def open_image_rgb(path: str) -> Image.Image:
    """Open an image path as RGB PIL Image."""
    return Image.open(path).convert("RGB")
