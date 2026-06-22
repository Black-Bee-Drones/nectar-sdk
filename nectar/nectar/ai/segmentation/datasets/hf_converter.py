"""Convert instance-segmentation datasets between COCO/YOLO-seg on disk and a
HuggingFace ``DatasetDict``.

The HF schema mirrors the object-detection schema produced by
:mod:`nectar.ai.detection.datasets.hf_converter` (so the Hub viewer renders
bounding-box overlays) and adds a per-instance ``segmentation`` polygon so the
masks survive the round trip and can be used for training.

Schema per row:

.. code-block:: python

    {
        "image": Image(),
        "image_id": int,
        "width": int,
        "height": int,
        "objects": {
            "id": [int, ...],
            "bbox": [[x, y, w, h], ...],        # COCO xywh, derived from the polygon
            "category": [int, ...],              # ClassLabel
            "area": [float, ...],
            "segmentation": [[x1, y1, ...], ...],  # absolute polygon vertices, one per instance
        },
    }
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from nectar.ai.detection.datasets.hf_converter import (
    SPLIT_MAP_HF_TO_LOCAL,
    SPLIT_MAP_LOCAL_TO_HF,
    _class_names_from_dataset,
    _require_datasets,
)
from nectar.ai.segmentation.datasets.format import _polygon_area, _polygon_bbox

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _build_seg_features(class_names: List[str]):
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
                "segmentation": Sequence(Sequence(Value("float32"))),
            },
        }
    )


def _empty_objects() -> Dict[str, List[Any]]:
    return {"id": [], "bbox": [], "category": [], "area": [], "segmentation": []}


def _seg_rows_to_dataset(rows: List[Dict[str, Any]], class_names: List[str]):
    from datasets import Dataset

    features = _build_seg_features(class_names)
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


def _first_polygon(segmentation: Any) -> Optional[List[float]]:
    """Return a single flat ``[x1, y1, ...]`` polygon from a COCO ``segmentation``.

    COCO instance segmentation stores a list of polygons per instance; we keep
    the first one (consistent with :class:`SegFormatConverter`). RLE masks
    (``dict``) are not supported and return ``None``.
    """
    if not segmentation or isinstance(segmentation, dict):
        return None
    if isinstance(segmentation[0], (list, tuple)):
        polygon = list(segmentation[0])
    else:
        polygon = list(segmentation)
    return polygon if len(polygon) >= 6 else None


def _parse_coco_seg_split(
    split_dir: Path, class_names: List[str]
) -> Optional[List[Dict[str, Any]]]:
    """Parse a COCO-seg split directory into row dicts. Mutates ``class_names``."""
    ann_file = split_dir / "_annotations.coco.json"
    if not ann_file.exists():
        return None

    with open(ann_file, encoding="utf-8") as f:
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

        objects = _empty_objects()
        for ann in img_anns.get(img_id, []):
            coco_cat_id = ann["category_id"]
            if coco_cat_id not in cat_id_map:
                continue
            polygon = _first_polygon(ann.get("segmentation"))
            if polygon is None:
                continue
            xs = polygon[0::2]
            ys = polygon[1::2]
            bbox = ann.get("bbox") or list(_polygon_bbox(xs, ys))
            area = ann.get("area") or _polygon_area(xs, ys)

            objects["id"].append(int(ann.get("id", len(objects["id"]))))
            objects["bbox"].append([float(v) for v in bbox])
            objects["category"].append(cat_id_map[coco_cat_id])
            objects["area"].append(float(area))
            objects["segmentation"].append([float(v) for v in polygon])

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


def seg_coco_to_hf(dataset_dir: str, class_names: Optional[List[str]] = None):
    """Convert a COCO-seg dataset directory to a HuggingFace ``DatasetDict``.

    Parameters
    ----------
    dataset_dir : str
        Root directory with ``train/``, ``valid/``, ``test/`` subdirs, each
        containing ``_annotations.coco.json`` plus the image files.
    class_names : list of str, optional
        Pre-seeded class names. Classes discovered in the COCO file are appended.

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
        rows = _parse_coco_seg_split(split_dir, discovered)
        if rows:
            splits[SPLIT_MAP_LOCAL_TO_HF[local_name]] = rows

    if not splits:
        raise RuntimeError(f"No valid COCO-seg splits found in {root}")

    return DatasetDict(
        {name: _seg_rows_to_dataset(rows, discovered) for name, rows in splits.items()}
    )


def seg_yolo_to_hf(dataset_dir: str):
    """Convert a YOLO-seg dataset directory (with ``data.yaml``) to a ``DatasetDict``.

    Expects the standard YOLO layout with polygon labels::

        dataset/
            data.yaml                      # names: [...]
            train/images/*.jpg
            train/labels/*.txt             # "class x1 y1 x2 y2 ... xN yN" (normalized)
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

    with open(yaml_path, encoding="utf-8") as f:
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
            if img_path.suffix.lower() not in _IMAGE_SUFFIXES:
                continue

            with PILImage.open(img_path) as im:
                w, h = im.size

            objects = _empty_objects()
            label_path = labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                for line in label_path.read_text(encoding="utf-8").strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) < 7:
                        continue
                    cls = int(parts[0])
                    coords = [float(v) for v in parts[1:]]
                    if len(coords) % 2 != 0:
                        coords = coords[:-1]

                    xs_abs = [coords[i] * w for i in range(0, len(coords), 2)]
                    ys_abs = [coords[i] * h for i in range(1, len(coords), 2)]
                    if len(xs_abs) < 3:
                        continue

                    polygon: List[float] = []
                    for x, y in zip(xs_abs, ys_abs):
                        polygon.extend([x, y])

                    bbox = _polygon_bbox(xs_abs, ys_abs)
                    objects["id"].append(ann_id)
                    objects["bbox"].append([float(v) for v in bbox])
                    objects["category"].append(cls)
                    objects["area"].append(float(_polygon_area(xs_abs, ys_abs)))
                    objects["segmentation"].append([float(v) for v in polygon])
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
        raise RuntimeError(f"No valid YOLO-seg splits found in {root}")

    return DatasetDict(
        {name: _seg_rows_to_dataset(rows, class_names) for name, rows in splits.items()}
    )


def hf_to_coco_seg(dataset, output_dir: str, image_format: str = "jpg") -> Path:
    """Materialize a HuggingFace seg ``DatasetDict`` to a COCO-seg directory.

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

    splits = dict(dataset) if hasattr(dataset, "keys") else {"train": dataset}

    class_names = _class_names_from_dataset(dataset)
    # COCO category ids are 1-indexed (matches SegFormatConverter convention).
    categories = [
        {"id": i + 1, "name": n, "supercategory": "object"} for i, n in enumerate(class_names)
    ]

    for split_name, split_ds in splits.items():
        split_dir = out / split_name
        split_dir.mkdir(parents=True, exist_ok=True)

        coco: Dict[str, Any] = {"images": [], "annotations": [], "categories": categories}
        ann_id = 0

        for idx, row in enumerate(split_ds):
            file_name = f"{idx:06d}.{image_format}"
            row["image"].convert("RGB").save(split_dir / file_name)

            coco["images"].append(
                {
                    "id": int(row["image_id"]),
                    "file_name": file_name,
                    "width": int(row["width"]),
                    "height": int(row["height"]),
                }
            )

            objects = row["objects"]
            for bbox, cat, area, seg in zip(
                objects["bbox"],
                objects["category"],
                objects["area"],
                objects["segmentation"],
            ):
                coco["annotations"].append(
                    {
                        "id": ann_id,
                        "image_id": int(row["image_id"]),
                        "category_id": int(cat) + 1,
                        "bbox": [float(v) for v in bbox],
                        "area": float(area),
                        "segmentation": [[float(v) for v in seg]],
                        "iscrowd": 0,
                    }
                )
                ann_id += 1

        with open(split_dir / "_annotations.coco.json", "w", encoding="utf-8") as f:
            json.dump(coco, f)

    return out


def hf_to_yolo_seg(dataset, output_dir: str, image_format: str = "jpg") -> Path:
    """Materialize a HuggingFace seg ``DatasetDict`` to a YOLO-seg directory.

    Writes normalized polygon labels (``class x1 y1 ... xN yN``) and a
    ``data.yaml`` ready for Ultralytics segmentation training.
    """
    _require_datasets()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    splits = dict(dataset) if hasattr(dataset, "keys") else {"train": dataset}
    class_names = _class_names_from_dataset(dataset)

    for hf_name, split_ds in splits.items():
        local_name = SPLIT_MAP_HF_TO_LOCAL.get(hf_name, hf_name)
        images_dir = out / local_name / "images"
        labels_dir = out / local_name / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        for idx, row in enumerate(split_ds):
            stem = f"{idx:06d}"
            row["image"].convert("RGB").save(images_dir / f"{stem}.{image_format}")

            w, h = row["width"], row["height"]
            lines: List[str] = []
            objects = row["objects"]
            for cat, seg in zip(objects["category"], objects["segmentation"]):
                if len(seg) < 6:
                    continue
                norm = []
                for i in range(0, len(seg), 2):
                    norm.append(f"{seg[i] / w:.6f}")
                    norm.append(f"{seg[i + 1] / h:.6f}")
                lines.append(f"{int(cat)} " + " ".join(norm))

            (labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    yaml_data: Dict[str, Any] = {
        "path": str(out.absolute()),
        "names": {i: n for i, n in enumerate(class_names)},
        "nc": len(class_names),
    }
    for hf_name in splits:
        local_name = SPLIT_MAP_HF_TO_LOCAL.get(hf_name, hf_name)
        yolo_split = "val" if local_name == "valid" else local_name
        yaml_data[yolo_split] = f"{local_name}/images"

    with open(out / "data.yaml", "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    return out


def generate_seg_dataset_card(
    dataset_dict,
    repo_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    license: str = "apache-2.0",  # noqa: A002  # pylint: disable=redefined-builtin
    tags: Optional[List[str]] = None,
    model_repo: Optional[str] = None,
    extra_sections: Optional[Dict[str, str]] = None,
) -> str:
    """Render a HuggingFace dataset card README.md for an instance-seg dataset.

    The frontmatter declares ``configs`` so the Hub viewer picks up the Parquet
    shards, and a ``dataset_info`` block describing the schema (including the
    ``segmentation`` polygon field). ``bbox`` + ``category`` make the viewer
    draw bounding-box overlays; the polygons are kept for training.

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
    base_tags = ["image-segmentation", "instance-segmentation"] + list(tags)

    configs_block = "\n".join(f"      - split: {s}\n        path: data/{s}-*" for s in splits)
    classlabel_block = "\n".join(f"                '{i}': {n}" for i, n in enumerate(class_names))

    split_table = "\n".join(f"| {s} | {len(dataset_dict[s])} |" for s in splits)
    classes_str = ", ".join(f"`{c}`" for c in class_names)

    title = title or repo_id.split("/")[-1].replace("-", " ").title()
    description = description or f"Instance segmentation dataset hosted at `{repo_id}`."

    card = f"""---
license: {license}
task_categories:
  - image-segmentation
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
        - name: segmentation
          sequence:
            sequence: float32
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

Each instance carries a COCO-style `bbox` (`[x_min, y_min, width, height]`, absolute
pixels), an `area`, a `category` (`ClassLabel`), and a `segmentation` polygon
(flat `[x1, y1, x2, y2, ...]` absolute pixel vertices). The Hub viewer draws the
bounding boxes; the polygons are kept for mask training.

## Usage

### Load with HuggingFace Datasets

```python
from datasets import load_dataset

dataset = load_dataset("{repo_id}")
example = dataset["{splits[0]}"][0]
print(example["objects"]["category"], example["objects"]["segmentation"][0][:8])
```

### Materialize as YOLO-seg (for training)

```python
from nectar.ai.segmentation.datasets import HuggingFaceSegHandler

handler = HuggingFaceSegHandler("data/local")
handler.download(repo_id="{repo_id}", format_type="yolo")
# data/local now contains data.yaml + train/images + train/labels (polygons)
```

### Train with Nectar SDK

```python
from nectar.ai.segmentation import Segmentor, SegTrainingConfig

segmentor = Segmentor("yolo26n-seg.pt")
segmentor.load()
segmentor.train(SegTrainingConfig(dataset_path="data/local/data.yaml", epochs=100))
```
"""

    if extra_sections:
        for header, body in extra_sections.items():
            card += f"\n## {header}\n\n{body}\n"

    return card
