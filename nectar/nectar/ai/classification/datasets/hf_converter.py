"""ImageFolder ↔ HuggingFace DatasetDict converters for classification."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from nectar.ai.classification.datasets.format import IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)

SPLIT_MAP = {
    "train": "train",
    "val": "validation",
    "valid": "validation",
    "validation": "validation",
    "test": "test",
}


def imagefolder_to_hf(dataset_path: str):
    """
    Convert an ImageFolder dataset to a HuggingFace DatasetDict.

    Schema: ``image`` (Image) + ``label`` (ClassLabel).
    """
    from datasets import ClassLabel, Dataset, DatasetDict, Image

    root = Path(dataset_path)
    splits: Dict[str, List[Dict[str, Any]]] = {}
    all_classes: List[str] = []

    for split_dir in sorted(root.iterdir()):
        if not split_dir.is_dir():
            continue
        hf_split = SPLIT_MAP.get(split_dir.name)
        if hf_split is None:
            # unsplit ImageFolder: treat class dirs at root as train
            if any(p.is_dir() for p in split_dir.iterdir()):
                continue
            continue

        rows = []
        class_dirs = sorted([p for p in split_dir.iterdir() if p.is_dir()])
        for class_dir in class_dirs:
            if class_dir.name not in all_classes:
                all_classes.append(class_dir.name)
            for img_path in sorted(class_dir.rglob("*")):
                if img_path.is_file() and img_path.suffix.lower() in IMAGE_EXTENSIONS:
                    rows.append({"image": str(img_path), "label": class_dir.name})
        if rows:
            splits[hf_split] = rows

    # Unsplit root-level class folders
    if not splits:
        class_dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name not in SPLIT_MAP])
        rows = []
        for class_dir in class_dirs:
            all_classes.append(class_dir.name)
            for img_path in sorted(class_dir.rglob("*")):
                if img_path.is_file() and img_path.suffix.lower() in IMAGE_EXTENSIONS:
                    rows.append({"image": str(img_path), "label": class_dir.name})
        if rows:
            splits["train"] = rows

    if not splits:
        raise ValueError(f"No images found in ImageFolder at {dataset_path}")

    all_classes = sorted(set(all_classes))

    ds_dict = {}
    for split_name, rows in splits.items():
        # Map string labels to ClassLabel indices via from_list then cast
        ds = Dataset.from_list(rows)
        ds = ds.cast_column("image", Image())
        ds = ds.cast_column("label", ClassLabel(names=all_classes))
        ds_dict[split_name] = ds

    return DatasetDict(ds_dict)


def hf_to_imagefolder(
    dataset, output_path: str, image_key: str = "image", label_key: str = "label"
) -> str:
    """
    Materialize a HF DatasetDict (or Dataset) as ImageFolder on disk.

    Returns the output path.
    """
    from datasets import DatasetDict

    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)

    if isinstance(dataset, DatasetDict):
        items = dataset.items()
    elif isinstance(dataset, dict):
        items = dataset.items()
    else:
        items = [("train", dataset)]

    reverse_split = {"train": "train", "validation": "val", "test": "test"}

    for split_name, split_ds in items:
        dest_split = reverse_split.get(split_name, split_name)
        label_feature = split_ds.features.get(label_key)
        names = getattr(label_feature, "names", None)

        for i, example in enumerate(split_ds):
            label = example[label_key]
            if names is not None:
                class_name = names[int(label)]
            else:
                class_name = str(label)

            class_dir = out / dest_split / class_name
            class_dir.mkdir(parents=True, exist_ok=True)

            image = example[image_key]
            if hasattr(image, "save"):
                image_path = class_dir / f"{split_name}_{i:06d}.jpg"
                image.convert("RGB").save(image_path, quality=95)
            else:
                raise ValueError(f"Unsupported image type in HF dataset: {type(image)}")

    logger.info("Wrote ImageFolder dataset to %s", out)
    return str(out)


def generate_cls_dataset_card(
    dataset,
    repo_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    license: str = "apache-2.0",
    tags: Optional[List[str]] = None,
) -> str:
    """Generate a minimal dataset card for a classification DatasetDict."""
    title = title or repo_id.split("/")[-1]
    description = description or "Image classification dataset."
    tags = tags or ["image-classification", "nectar-sdk"]

    n_splits = {}
    class_names = []
    if hasattr(dataset, "items"):
        for name, split in dataset.items():
            n_splits[name] = len(split)
            feat = split.features.get("label")
            if feat is not None and hasattr(feat, "names"):
                class_names = list(feat.names)

    lines = [
        "---",
        f"license: {license}",
        "task_categories:",
        "  - image-classification",
        "tags:",
    ]
    for tag in tags:
        lines.append(f"  - {tag}")
    lines.extend(
        [
            "---",
            "",
            f"# {title}",
            "",
            description,
            "",
            "## Splits",
            "",
        ]
    )
    for name, count in n_splits.items():
        lines.append(f"- **{name}**: {count} images")
    if class_names:
        lines.extend(["", "## Classes", "", ", ".join(f"`{c}`" for c in class_names)])
    return "\n".join(lines) + "\n"
