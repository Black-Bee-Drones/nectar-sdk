"""Convert object detection datasets between COCO/YOLO on disk and HuggingFace ``DatasetDict``.

The HF schema produced here matches the convention used by ``detection-datasets/coco``
and ``rishitdagli/cppe-5`` so that the Hub dataset viewer renders bounding box overlays.

Schema per row:

.. code-block:: python

    {
        "image": Image(),
        "image_id": int,
        "width": int,
        "height": int,
        "objects": {
            "id": [int, ...],
            "bbox": [[x, y, w, h], ...],   # COCO xywh
            "category": [int, ...],         # ClassLabel
            "area": [float, ...],
        },
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

SPLIT_MAP_LOCAL_TO_HF = {
    "train": "train",
    "valid": "validation",
    "val": "validation",
    "test": "test",
}
SPLIT_MAP_HF_TO_LOCAL = {"train": "train", "validation": "valid", "test": "test"}


def _require_datasets() -> None:
    """Raise ImportError with a helpful message if the ``datasets`` package is missing."""
    from importlib.util import find_spec

    if find_spec("datasets") is None:
        raise ImportError(
            "datasets is required for HuggingFace conversions. Install: pip install datasets"
        )


def _build_features(class_names: List[str]):
    from datasets import ClassLabel, Features, Image, Sequence, Value

    return Features(
        {
            "image": Image(),
            "image_id": Value("int64"),
            "width": Value("int32"),
            "height": Value("int32"),
            "objects": {
                "id": Sequence(Value("int64")),
                "bbox": Sequence(Sequence(Value("float32"), length=4)),
                "category": Sequence(ClassLabel(names=class_names)),
                "area": Sequence(Value("float64")),
            },
        }
    )


def _parse_coco_split(split_dir: Path, class_names: List[str]) -> Optional[List[Dict[str, Any]]]:
    """Parse a COCO split directory into row dicts. Mutates ``class_names`` in place."""
    ann_file = split_dir / "_annotations.coco.json"
    if not ann_file.exists():
        return None

    with open(ann_file) as f:
        coco = json.load(f)

    cat_id_map: Dict[int, int] = {}
    for cat in coco.get("categories", []):
        name = str(cat["name"]).lower().strip()
        if name in class_names:
            cat_id_map[cat["id"]] = class_names.index(name)
        else:
            cat_id_map[cat["id"]] = len(class_names)
            class_names.append(name)

    img_anns: Dict[int, List[Dict[str, Any]]] = {}
    for ann in coco.get("annotations", []):
        img_anns.setdefault(ann["image_id"], []).append(ann)

    rows: List[Dict[str, Any]] = []
    for img_info in coco.get("images", []):
        img_id = img_info["id"]
        img_path = split_dir / img_info["file_name"]
        if not img_path.exists():
            continue

        objects = {"id": [], "bbox": [], "category": [], "area": []}
        for ann in img_anns.get(img_id, []):
            coco_cat_id = ann["category_id"]
            if coco_cat_id not in cat_id_map:
                continue
            bbox = [float(v) for v in ann["bbox"]]
            objects["id"].append(int(ann["id"]))
            objects["bbox"].append(bbox)
            objects["category"].append(cat_id_map[coco_cat_id])
            objects["area"].append(float(ann.get("area", bbox[2] * bbox[3])))

        rows.append(
            {
                "image": str(img_path),
                "image_id": int(img_id),
                "width": int(img_info["width"]),
                "height": int(img_info["height"]),
                "objects": objects,
            }
        )

    return rows


def _rows_to_dataset(rows: List[Dict[str, Any]], class_names: List[str]):
    from datasets import Dataset

    features = _build_features(class_names)
    return Dataset.from_dict(
        {
            "image": [r["image"] for r in rows],
            "image_id": [r["image_id"] for r in rows],
            "width": [r["width"] for r in rows],
            "height": [r["height"] for r in rows],
            "objects": [r["objects"] for r in rows],
        },
        features=features,
    )


def coco_to_hf(dataset_dir: str, class_names: Optional[List[str]] = None):
    """Convert a COCO-format dataset directory to a HuggingFace ``DatasetDict``.

    Parameters
    ----------
    dataset_dir : str
        Root directory containing ``train/``, ``valid/``, ``test/`` subdirs each
        with a ``_annotations.coco.json`` plus the image files.
    class_names : list of str, optional
        Pre-seeded class names. New classes discovered in the COCO file are appended.

    Returns
    -------
    DatasetDict
        With keys ``train``/``validation``/``test`` (only those that exist).
    """
    _require_datasets()
    from datasets import DatasetDict

    root = Path(dataset_dir).expanduser().resolve()
    discovered: List[str] = list(class_names or [])

    splits: Dict[str, List[Dict[str, Any]]] = {}
    for local_name in ("train", "valid", "val", "test"):
        split_dir = root / local_name
        if not split_dir.exists():
            continue
        rows = _parse_coco_split(split_dir, discovered)
        if rows:
            hf_name = SPLIT_MAP_LOCAL_TO_HF[local_name]
            splits[hf_name] = rows

    if not splits:
        raise RuntimeError(f"No valid COCO splits found in {root}")

    return DatasetDict({name: _rows_to_dataset(rows, discovered) for name, rows in splits.items()})


def yolo_to_hf(dataset_dir: str):
    """Convert a YOLO-format dataset directory (with ``data.yaml``) to a ``DatasetDict``.

    Expects the standard YOLO layout::

        dataset/
            data.yaml          # names: [...]
            train/images/*.jpg
            train/labels/*.txt
            valid/images/*.jpg
            valid/labels/*.txt
            test/images/*.jpg
            test/labels/*.txt
    """
    _require_datasets()
    from datasets import DatasetDict
    from PIL import Image as PILImage

    root = Path(dataset_dir).expanduser().resolve()
    yaml_path = root / "data.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"data.yaml not found in {root}")

    with open(yaml_path) as f:
        data_yaml = yaml.safe_load(f)

    raw_names = data_yaml.get("names", {})
    if isinstance(raw_names, dict):
        class_names = [raw_names[k] for k in sorted(raw_names, key=int)]
    else:
        class_names = list(raw_names)

    splits: Dict[str, List[Dict[str, Any]]] = {}
    for local_name in ("train", "valid", "val", "test"):
        split_dir = root / local_name
        images_dir = split_dir / "images"
        labels_dir = split_dir / "labels"
        if not images_dir.exists():
            continue

        rows: List[Dict[str, Any]] = []
        ann_id = 0
        for idx, img_path in enumerate(sorted(images_dir.iterdir())):
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue

            with PILImage.open(img_path) as im:
                w, h = im.size

            objects = {"id": [], "bbox": [], "category": [], "area": []}
            label_path = labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                for line in label_path.read_text().strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    cls = int(parts[0])
                    xc, yc, bw, bh = (float(v) for v in parts[1:5])
                    x = (xc - bw / 2) * w
                    y = (yc - bh / 2) * h
                    bw_px, bh_px = bw * w, bh * h
                    objects["id"].append(ann_id)
                    objects["bbox"].append([x, y, bw_px, bh_px])
                    objects["category"].append(cls)
                    objects["area"].append(float(bw_px * bh_px))
                    ann_id += 1

            rows.append(
                {
                    "image": str(img_path),
                    "image_id": idx,
                    "width": w,
                    "height": h,
                    "objects": objects,
                }
            )

        if rows:
            splits[SPLIT_MAP_LOCAL_TO_HF[local_name]] = rows

    if not splits:
        raise RuntimeError(f"No valid YOLO splits found in {root}")

    return DatasetDict({name: _rows_to_dataset(rows, class_names) for name, rows in splits.items()})


def _class_names_from_dataset(dataset) -> List[str]:
    """Extract class names from a DatasetDict or Dataset's ClassLabel feature.

    Handles both common HF object detection schemas:

    - struct-of-sequences: ``features["objects"]["category"].feature.names``
    - sequence-of-structs: ``features["objects"].feature["category"].names``
    """
    first = dataset[next(iter(dataset))] if hasattr(dataset, "keys") else dataset
    objects_feature = first.features["objects"]

    if isinstance(objects_feature, dict):
        cat_feature = objects_feature["category"]
    else:
        cat_feature = objects_feature.feature["category"]

    inner = cat_feature.feature if hasattr(cat_feature, "feature") else cat_feature
    return list(inner.names)


def hf_to_coco(dataset, output_dir: str, image_format: str = "jpg") -> Path:
    """Materialize a HuggingFace ``DatasetDict`` (or ``Dataset``) to a COCO directory.

    Output layout::

        output_dir/
            train/_annotations.coco.json
            train/<files>.<image_format>
            validation/_annotations.coco.json
            ...
    """
    _require_datasets()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    if hasattr(dataset, "keys"):
        splits = dict(dataset)
    else:
        splits = {"train": dataset}

    class_names = _class_names_from_dataset(dataset)
    categories = [{"id": i, "name": n, "supercategory": "none"} for i, n in enumerate(class_names)]

    for split_name, split_ds in splits.items():
        split_dir = out / split_name
        split_dir.mkdir(parents=True, exist_ok=True)

        coco = {"images": [], "annotations": [], "categories": categories}
        ann_id = 0

        for idx, row in enumerate(split_ds):
            file_name = f"{idx:06d}.{image_format}"
            img_path = split_dir / file_name
            row["image"].convert("RGB").save(img_path)

            coco["images"].append(
                {
                    "id": int(row["image_id"]),
                    "file_name": file_name,
                    "width": int(row["width"]),
                    "height": int(row["height"]),
                }
            )

            for bbox, cat, area in zip(
                row["objects"]["bbox"],
                row["objects"]["category"],
                row["objects"]["area"],
            ):
                coco["annotations"].append(
                    {
                        "id": ann_id,
                        "image_id": int(row["image_id"]),
                        "category_id": int(cat),
                        "bbox": [float(v) for v in bbox],
                        "area": float(area),
                        "iscrowd": 0,
                        "segmentation": [],
                    }
                )
                ann_id += 1

        with open(split_dir / "_annotations.coco.json", "w") as f:
            json.dump(coco, f)

    return out


def hf_to_yolo(dataset, output_dir: str, image_format: str = "jpg") -> Path:
    """Materialize a HuggingFace ``DatasetDict`` to a YOLO directory with ``data.yaml``."""
    _require_datasets()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    if hasattr(dataset, "keys"):
        splits = dict(dataset)
    else:
        splits = {"train": dataset}

    class_names = _class_names_from_dataset(dataset)

    for hf_name, split_ds in splits.items():
        local_name = SPLIT_MAP_HF_TO_LOCAL.get(hf_name, hf_name)
        images_dir = out / local_name / "images"
        labels_dir = out / local_name / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        for idx, row in enumerate(split_ds):
            stem = f"{idx:06d}"
            img_path = images_dir / f"{stem}.{image_format}"
            row["image"].convert("RGB").save(img_path)

            w, h = row["width"], row["height"]
            lines: List[str] = []
            for bbox, cat in zip(row["objects"]["bbox"], row["objects"]["category"]):
                x, y, bw, bh = bbox
                xc = (x + bw / 2) / w
                yc = (y + bh / 2) / h
                lines.append(f"{int(cat)} {xc} {yc} {bw / w} {bh / h}")

            (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    yaml_data = {
        "path": str(out.absolute()),
        "names": {i: n for i, n in enumerate(class_names)},
        "nc": len(class_names),
    }
    for hf_name in splits:
        local_name = SPLIT_MAP_HF_TO_LOCAL.get(hf_name, hf_name)
        yolo_split = "val" if local_name == "valid" else local_name
        yaml_data[yolo_split] = f"{local_name}/images"

    with open(out / "data.yaml", "w") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    return out


def generate_dataset_card(
    dataset_dict,
    repo_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    license: str = "apache-2.0",
    tags: Optional[List[str]] = None,
    model_repo: Optional[str] = None,
    extra_sections: Optional[Dict[str, str]] = None,
) -> str:
    """Render a HuggingFace dataset card README.md with proper YAML frontmatter.

    The frontmatter declares ``configs`` so the Hub viewer picks up the Parquet
    shards uploaded via ``Dataset.push_to_hub``.

    Parameters
    ----------
    dataset_dict : DatasetDict
        The dataset to describe (used for split sizes and class names).
    repo_id : str
        Target repo (``user/name``).
    title, description, license, tags, model_repo : optional
        Card metadata.
    extra_sections : dict, optional
        Mapping of section header to markdown body to append.
    """
    _require_datasets()

    class_names = _class_names_from_dataset(dataset_dict)
    splits = list(dataset_dict.keys())
    total = sum(len(dataset_dict[s]) for s in splits)

    if total < 1000:
        size_cat = "n<1K"
    elif total < 10000:
        size_cat = "1K<n<10K"
    elif total < 100000:
        size_cat = "10K<n<100K"
    else:
        size_cat = "100K<n<1M"

    tags = tags or []
    base_tags = ["object-detection"] + list(tags)

    configs_block = "\n".join(f"      - split: {s}\n        path: data/{s}-*" for s in splits)
    classlabel_block = "\n".join(f"                '{i}': {n}" for i, n in enumerate(class_names))

    split_table = "\n".join(f"| {s} | {len(dataset_dict[s])} |" for s in splits)
    classes_str = ", ".join(f"`{c}`" for c in class_names)

    title = title or repo_id.split("/")[-1].replace("-", " ").title()
    description = description or f"Object detection dataset hosted at `{repo_id}`."

    card = f"""---
license: {license}
task_categories:
  - object-detection
tags:
{chr(10).join(f"  - {t}" for t in base_tags)}
size_categories:
  - {size_cat}
pretty_name: {title}
configs:
  - config_name: default
    data_files:
{configs_block}
dataset_info:
  features:
    - name: image
      dtype: image
    - name: image_id
      dtype: int64
    - name: width
      dtype: int32
    - name: height
      dtype: int32
    - name: objects
      struct:
        - name: id
          sequence: int64
        - name: bbox
          sequence:
            sequence: float32
            length: 4
        - name: category
          sequence:
            class_label:
              names:
{classlabel_block}
        - name: area
          sequence: float64
---

# {title}

{description}
"""

    if model_repo:
        card += f"\n**Trained model:** [{model_repo}](https://huggingface.co/{model_repo})\n"

    card += f"""
## Dataset Structure

| Split | Images |
|-------|--------|
{split_table}

**Total images:** {total}

**Classes:** {classes_str}

**Annotation format:** COCO bbox `[x_min, y_min, width, height]`.

## Usage

### Load with HuggingFace Datasets

```python
from datasets import load_dataset

dataset = load_dataset("{repo_id}")
example = dataset["{splits[0]}"][0]
print(example["objects"])
```

### Use with Nectar SDK

```python
from nectar.ai.detection.datasets import HuggingFaceHandler

handler = HuggingFaceHandler("data/local")
handler.download(repo_id="{repo_id}", format_type="coco")
# data/local now contains train/_annotations.coco.json and image files
```
"""

    if extra_sections:
        for header, body in extra_sections.items():
            card += f"\n## {header}\n\n{body}\n"

    return card
