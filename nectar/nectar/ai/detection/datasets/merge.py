"""Dataset merger utility for combining YOLO and COCO datasets."""

import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from tqdm import tqdm

from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector


class DatasetMerger:
    """
    Merge YOLO or COCO format datasets with balanced sampling.

    Supports merging datasets in the same format or mixed formats.
    Auto-detects input formats and can output in either format.

    Parameters
    ----------
    d1_path : str
        Path to first dataset.
    d2_path : str
        Path to second dataset.
    output_path : str
        Path to output merged dataset.
    output_format : str, optional
        Output format ("yolo", "coco", or "auto"). Defaults to "auto".
        If "auto", uses the format of the first dataset.
    seed : int, optional
        Random seed. Defaults to 42.

    Examples
    --------
    >>> merger = DatasetMerger("data/dataset1", "data/dataset2", "data/merged")
    >>> merger.merge({
    ...     "train": {"d1": 1000, "d2": 5000},
    ...     "valid": {"d1": "all", "d2": 500}
    ... })
    """

    def __init__(
        self,
        d1_path: str,
        d2_path: str,
        output_path: str,
        output_format: str = "auto",
        seed: int = 42,
    ):
        self.d1_path = Path(d1_path)
        self.d2_path = Path(d2_path)
        self.output_path = Path(output_path)
        self.seed = seed
        self.random_gen = random.Random(seed)

        self.output_path.mkdir(parents=True, exist_ok=True)

        detector1 = FormatDetector(str(self.d1_path))
        detector2 = FormatDetector(str(self.d2_path))

        self.d1_format = detector1.detect()
        self.d2_format = detector2.detect()

        if self.d1_format == "unknown" or self.d2_format == "unknown":
            raise ValueError(f"Could not detect format. d1: {self.d1_format}, d2: {self.d2_format}")

        if output_format == "auto":
            self.output_format = self.d1_format
        else:
            self.output_format = output_format

        if self.output_format not in ["yolo", "coco"]:
            raise ValueError(f"Unsupported output format: {self.output_format}")

        self.class_names: Dict[int, str] = {}
        self.d1_map: Optional[Dict[int, int]] = None
        self.d2_map: Optional[Dict[int, int]] = None

        self.d1_categories: Optional[List[Dict]] = None
        self.d2_categories: Optional[List[Dict]] = None
        self.merged_categories: Optional[List[Dict]] = None

    def merge(
        self,
        split_config: Dict[str, Dict[str, int]],
        rename_files: bool = True,
    ) -> None:
        """
        Merge datasets based on split configuration.

        Parameters
        ----------
        split_config : Dict
            Configuration for each split.
            Example: {"train": {"d1": 1000, "d2": 5000}}
        rename_files : bool, optional
            Prepend dataset name to filenames. Defaults to True.
        """
        print("Starting dataset merge...")
        print(f"Dataset 1 format: {self.d1_format}")
        print(f"Dataset 2 format: {self.d2_format}")
        print(f"Output format: {self.output_format}")

        if self.output_format == "yolo":
            self._merge_yolo(split_config, rename_files)
        else:
            self._merge_coco(split_config, rename_files)

        print("\nMerge completed!")

    def _merge_yolo(
        self,
        split_config: Dict[str, Dict[str, int]],
        rename_files: bool,
    ) -> None:
        """Merge datasets in YOLO format."""
        d1_yaml = self.d1_path / "data.yaml"
        d2_yaml = self.d2_path / "data.yaml"

        if self.d1_format != "yolo":
            d1_yaml = self._convert_to_yolo(self.d1_path, "d1_temp")
        if self.d2_format != "yolo":
            d2_yaml = self._convert_to_yolo(self.d2_path, "d2_temp")

        if not d1_yaml.exists() or not d2_yaml.exists():
            raise FileNotFoundError("Both datasets must have data.yaml")

        with open(d1_yaml, encoding="utf-8") as f:
            d1_config = yaml.safe_load(f)
        with open(d2_yaml, encoding="utf-8") as f:
            d2_config = yaml.safe_load(f)

        self.class_names, self.d1_map, self.d2_map = self._merge_class_names(
            d1_config["names"], d2_config["names"]
        )

        for split, config in split_config.items():
            print(f"Processing split: {split}")

            dest_images = self.output_path / split / "images"
            dest_labels = self.output_path / split / "labels"
            dest_images.mkdir(parents=True, exist_ok=True)
            dest_labels.mkdir(parents=True, exist_ok=True)

            for d_id, num_samples in config.items():
                dataset_path = self.d1_path if d_id == "d1" else self.d2_path
                dataset_name = dataset_path.name
                class_map = self.d1_map if d_id == "d1" else self.d2_map

                if self.d1_format != "yolo" and d_id == "d1":
                    dataset_path = Path("d1_temp")
                elif self.d2_format != "yolo" and d_id == "d2":
                    dataset_path = Path("d2_temp")

                print(f"  Sampling from {dataset_name} ({num_samples})")

                split_images = dataset_path / split / "images"
                split_labels = dataset_path / split / "labels"

                if not split_images.exists() or not split_labels.exists():
                    print(f"  Warning: {split} not found in {dataset_path}")
                    continue

                image_files = [
                    p
                    for p in split_images.glob("*.*")
                    if p.suffix.lower() in [".jpg", ".jpeg", ".png"]
                ]

                sampled = self._get_sampled_files_yolo(split_labels, image_files, num_samples)

                self._copy_files_yolo(
                    sampled,
                    split_labels,
                    dest_images,
                    dest_labels,
                    dataset_name if rename_files else "",
                    class_map,
                )

        self._create_final_yaml(split_config.keys())

        if self.d1_format != "yolo":
            shutil.rmtree("d1_temp", ignore_errors=True)
        if self.d2_format != "yolo":
            shutil.rmtree("d2_temp", ignore_errors=True)

    def _merge_coco(
        self,
        split_config: Dict[str, Dict[str, int]],
        rename_files: bool,
    ) -> None:
        """Merge datasets in COCO format."""
        d1_anns = self._load_coco_categories(self.d1_path)
        d2_anns = self._load_coco_categories(self.d2_path)

        if self.d1_format != "coco":
            d1_path = self._convert_to_coco(self.d1_path, "d1_temp")
        else:
            d1_path = self.d1_path

        if self.d2_format != "coco":
            d2_path = self._convert_to_coco(self.d2_path, "d2_temp")
        else:
            d2_path = self.d2_path

        self.merged_categories, self.d1_map, self.d2_map = self._merge_coco_categories(
            d1_anns["categories"], d2_anns["categories"]
        )

        for split, config in split_config.items():
            print(f"Processing split: {split}")

            split_dir = self.output_path / split
            split_dir.mkdir(parents=True, exist_ok=True)

            merged_data = {
                "images": [],
                "annotations": [],
                "categories": self.merged_categories,
            }

            image_id_counter = 1
            annotation_id_counter = 1

            for d_id, num_samples in config.items():
                dataset_path = d1_path if d_id == "d1" else d2_path
                dataset_name = dataset_path.name
                category_map = self.d1_map if d_id == "d1" else self.d2_map

                print(f"  Sampling from {dataset_name} ({num_samples})")

                split_ann_file = dataset_path / split / "_annotations.coco.json"
                if not split_ann_file.exists():
                    print(f"  Warning: {split} not found in {dataset_path}")
                    continue

                with open(split_ann_file, encoding="utf-8") as f:
                    coco_data = json.load(f)

                image_files = []
                for img in coco_data["images"]:
                    img_path = dataset_path / split / img["file_name"]
                    if not img_path.exists():
                        img_path = dataset_path / split / "images" / img["file_name"]
                    if img_path.exists():
                        image_files.append((img, img_path))

                sampled = self._get_sampled_files_coco(coco_data, image_files, num_samples)

                for img_info, img_path in sampled:
                    new_filename = (
                        f"{dataset_name}--{img_info['file_name']}"
                        if rename_files
                        else img_info["file_name"]
                    )

                    dest_img = split_dir / new_filename
                    shutil.copy2(img_path, dest_img)

                    new_image_id = image_id_counter
                    image_id_counter += 1

                    merged_data["images"].append(
                        {
                            "id": new_image_id,
                            "file_name": new_filename,
                            "width": img_info["width"],
                            "height": img_info["height"],
                        }
                    )

                    for ann in coco_data["annotations"]:
                        if ann["image_id"] == img_info["id"]:
                            old_cat_id = ann["category_id"]
                            new_cat_id = category_map.get(old_cat_id, old_cat_id)

                            merged_data["annotations"].append(
                                {
                                    "id": annotation_id_counter,
                                    "image_id": new_image_id,
                                    "category_id": new_cat_id,
                                    "bbox": ann["bbox"],
                                    "area": ann["area"],
                                    "iscrowd": ann.get("iscrowd", 0),
                                }
                            )
                            annotation_id_counter += 1

            ann_file = split_dir / "_annotations.coco.json"
            with open(ann_file, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, indent=2)

            print(f"  Created: {ann_file}")

        if self.d1_format != "coco":
            shutil.rmtree("d1_temp", ignore_errors=True)
        if self.d2_format != "coco":
            shutil.rmtree("d2_temp", ignore_errors=True)

    def _convert_to_yolo(self, dataset_path: Path, temp_name: str) -> Path:
        """Convert dataset to YOLO format temporarily."""
        converter = FormatConverter(str(dataset_path), temp_name, verbose=False)
        yaml_path = converter.coco_to_yolo()
        return Path(yaml_path)

    def _convert_to_coco(self, dataset_path: Path, temp_name: str) -> Path:
        """Convert dataset to COCO format temporarily."""
        converter = FormatConverter(str(dataset_path), temp_name, verbose=False)
        converter.yolo_to_coco()
        return Path(temp_name)

    def _load_coco_categories(self, dataset_path: Path) -> Dict:
        """Load COCO categories from dataset."""
        for split_dir in dataset_path.iterdir():
            if split_dir.is_dir():
                ann_file = split_dir / "_annotations.coco.json"
                if ann_file.exists():
                    with open(ann_file, encoding="utf-8") as f:
                        return json.load(f)
        return {"categories": []}

    def _merge_coco_categories(
        self, cats1: List[Dict], cats2: List[Dict]
    ) -> Tuple[List[Dict], Dict[int, int], Dict[int, int]]:
        """Merge COCO categories and create mapping."""
        name_to_id1 = {cat["name"]: cat["id"] for cat in cats1}
        name_to_id2 = {cat["name"]: cat["id"] for cat in cats2}

        all_names = list(name_to_id1.keys())
        for name in name_to_id2.keys():
            if name not in all_names:
                all_names.append(name)

        merged_cats = []
        name_to_new_id = {}
        for idx, name in enumerate(all_names):
            new_id = idx
            name_to_new_id[name] = new_id
            merged_cats.append({"id": new_id, "name": name})

        map1 = {old_id: name_to_new_id[name] for name, old_id in name_to_id1.items()}
        map2 = {old_id: name_to_new_id[name] for name, old_id in name_to_id2.items()}

        return merged_cats, map1, map2

    def _get_sampled_files_yolo(
        self,
        labels_path: Path,
        image_files: List[Path],
        num_samples,
    ) -> List[Path]:
        """Get sampled files for YOLO merge."""
        if num_samples == "all":
            return image_files

        if num_samples == 0:
            return []

        image_to_classes, class_to_images, _ = self._analyze_distribution_yolo(
            labels_path, image_files
        )

        if not class_to_images:
            print("  Warning: No labeled images found")
            return []

        if num_samples >= len(image_files):
            return image_files

        return self._balanced_sample(image_to_classes, class_to_images, num_samples)

    def _get_sampled_files_coco(
        self,
        coco_data: Dict,
        image_files: List[Tuple[Dict, Path]],
        num_samples,
    ) -> List[Tuple[Dict, Path]]:
        """Get sampled files for COCO merge."""
        if num_samples == "all":
            return image_files

        if num_samples == 0:
            return []

        if num_samples >= len(image_files):
            return image_files

        image_to_classes = {}
        class_to_images = defaultdict(list)

        img_id_to_anns = defaultdict(list)
        for ann in coco_data["annotations"]:
            img_id_to_anns[ann["image_id"]].append(ann)

        for img_info, img_path in image_files:
            anns = img_id_to_anns.get(img_info["id"], [])
            classes = [ann["category_id"] for ann in anns]
            if classes:
                image_to_classes[img_info["id"]] = list(set(classes))
                for cls_id in set(classes):
                    class_to_images[cls_id].append((img_info, img_path))

        if not class_to_images:
            print("  Warning: No labeled images found")
            return []

        selected = set()
        for class_id in sorted(class_to_images.keys()):
            if len(selected) >= num_samples:
                break
            options = class_to_images[class_id]
            if options:
                selected.add(options[0][0]["id"])

        remaining = [
            (img_info, img_path)
            for img_info, img_path in image_files
            if img_info["id"] not in selected
        ]
        self.random_gen.shuffle(remaining)

        needed = num_samples - len(selected)
        if needed > 0:
            selected_ids = {img_info["id"] for img_info, _ in remaining[:needed]}
            selected.update(selected_ids)

        return [
            (img_info, img_path) for img_info, img_path in image_files if img_info["id"] in selected
        ]

    def _analyze_distribution_yolo(self, labels_path: Path, image_files: List[Path]):
        """Analyze class distribution from YOLO labels."""
        image_to_classes = defaultdict(list)
        class_to_images = defaultdict(list)
        total_counts = Counter()

        for img_path in tqdm(image_files, desc="  Analyzing"):
            label_path = labels_path / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue

            with open(label_path, encoding="utf-8") as f:
                lines = f.readlines()

            classes = []
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                class_id = int(parts[0])
                classes.append(class_id)
                class_to_images[class_id].append(img_path)

            if classes:
                image_to_classes[img_path] = list(set(classes))
                total_counts.update(classes)

        return image_to_classes, class_to_images, total_counts

    def _balanced_sample(
        self,
        image_to_classes: Dict,
        class_to_images: Dict,
        num_samples: int,
    ) -> List[Path]:
        """Balanced sampling of images."""
        selected = set()

        for class_id in sorted(class_to_images.keys()):
            if len(selected) >= num_samples:
                break
            options = class_to_images[class_id]
            if options:
                selected.add(self.random_gen.choice(options))

        remaining = list(set(image_to_classes.keys()) - selected)
        self.random_gen.shuffle(remaining)

        needed = num_samples - len(selected)
        if needed > 0:
            selected.update(remaining[:needed])

        return list(selected)

    def _copy_files_yolo(
        self,
        files: List[Path],
        src_labels: Path,
        dest_images: Path,
        dest_labels: Path,
        prefix: str,
        class_map: Optional[Dict[int, int]],
    ) -> None:
        """Copy image and label files for YOLO."""
        for src_img in tqdm(files, desc=f"  Copying {prefix}"):
            new_name = f"{prefix}--{src_img.name}" if prefix else src_img.name
            dest_img = dest_images / new_name

            shutil.copy2(src_img, dest_img)

            src_label = src_labels / f"{src_img.stem}.txt"
            if src_label.exists():
                dest_label = dest_labels / f"{Path(new_name).stem}.txt"
                if class_map:
                    self._remap_label(src_label, dest_label, class_map)
                else:
                    shutil.copy2(src_label, dest_label)

    def _remap_label(
        self,
        src: Path,
        dest: Path,
        class_map: Dict[int, int],
    ) -> None:
        """Copy label with remapped class IDs."""
        with open(src, encoding="utf-8") as f_in, open(dest, "w", encoding="utf-8") as f_out:
            for line in f_in:
                parts = line.strip().split()
                if not parts:
                    continue
                old_id = int(parts[0])
                new_id = class_map.get(old_id, old_id)
                f_out.write(f"{new_id} {' '.join(parts[1:])}\n")

    def _normalize_names(self, names) -> Dict[int, str]:
        """Normalize class names to dict format."""
        if isinstance(names, list):
            return {i: name for i, name in enumerate(names)}
        return names

    def _merge_class_names(self, names1, names2):
        """Merge class names from two datasets."""
        names1 = self._normalize_names(names1)
        names2 = self._normalize_names(names2)

        if names1 == names2:
            print("Class names identical")
            return names1, None, None

        print("Warning: Class names differ, merging")

        all_names = list(names1.values())
        for name in names2.values():
            if name not in all_names:
                all_names.append(name)

        merged = {i: name for i, name in enumerate(all_names)}
        name_to_id = {name: i for i, name in merged.items()}

        map1 = {old: name_to_id[name] for old, name in names1.items()}
        map2 = {old: name_to_id[name] for old, name in names2.items()}

        return merged, map1, map2

    def _create_final_yaml(self, splits) -> None:
        """Create data.yaml for merged YOLO dataset."""
        yaml_data = {
            "path": str(self.output_path.absolute()),
            "names": self.class_names,
            "nc": len(self.class_names),
        }

        for split in splits:
            if (self.output_path / split).exists():
                key = "val" if split == "valid" else split
                yaml_data[key] = f"{split}/images"

        yaml_path = self.output_path / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        print(f"\nCreated: {yaml_path}")
