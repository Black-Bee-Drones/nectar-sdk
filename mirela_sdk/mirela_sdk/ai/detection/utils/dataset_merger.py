"""Dataset merger utility for combining YOLO datasets."""

import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from tqdm import tqdm


class DatasetMerger:
    """
    Merge YOLO format datasets with balanced sampling.

    Parameters
    ----------
    d1_path : str
        Path to first dataset.
    d2_path : str
        Path to second dataset.
    output_path : str
        Path to output merged dataset.
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
        self, d1_path: str, d2_path: str, output_path: str, seed: int = 42
    ):
        self.d1_path = Path(d1_path)
        self.d2_path = Path(d2_path)
        self.output_path = Path(output_path)
        self.seed = seed
        self.random_gen = random.Random(seed)

        self.output_path.mkdir(parents=True, exist_ok=True)

        self.class_names: Dict[int, str] = {}
        self.d1_map: Optional[Dict[int, int]] = None
        self.d2_map: Optional[Dict[int, int]] = None

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

        d1_yaml = self.d1_path / "data.yaml"
        d2_yaml = self.d2_path / "data.yaml"

        if not d1_yaml.exists() or not d2_yaml.exists():
            raise FileNotFoundError("Both datasets must have data.yaml")

        with open(d1_yaml) as f:
            d1_config = yaml.safe_load(f)
        with open(d2_yaml) as f:
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

                sampled = self._get_sampled_files(
                    split_labels, image_files, num_samples
                )

                self._copy_files(
                    sampled,
                    split_labels,
                    dest_images,
                    dest_labels,
                    dataset_name if rename_files else "",
                    class_map,
                )

        self._create_final_yaml(split_config.keys())
        print("\nMerge completed!")

    def _get_sampled_files(
        self,
        labels_path: Path,
        image_files: List[Path],
        num_samples,
    ) -> List[Path]:
        """Get sampled files for merge."""
        if num_samples == "all":
            return image_files

        if num_samples == 0:
            return []

        image_to_classes, class_to_images, _ = self._analyze_distribution(
            labels_path, image_files
        )

        if not class_to_images:
            print("  Warning: No labeled images found")
            return []

        if num_samples >= len(image_files):
            return image_files

        return self._balanced_sample(
            image_to_classes, class_to_images, num_samples
        )

    def _analyze_distribution(
        self, labels_path: Path, image_files: List[Path]
    ):
        """Analyze class distribution from labels."""
        image_to_classes = defaultdict(list)
        class_to_images = defaultdict(list)
        total_counts = Counter()

        for img_path in tqdm(image_files, desc="  Analyzing"):
            label_path = labels_path / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue

            with open(label_path) as f:
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

    def _copy_files(
        self,
        files: List[Path],
        src_labels: Path,
        dest_images: Path,
        dest_labels: Path,
        prefix: str,
        class_map: Optional[Dict[int, int]],
    ) -> None:
        """Copy image and label files."""
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
        with open(src) as f_in, open(dest, "w") as f_out:
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
        """Create data.yaml for merged dataset."""
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
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_data, f, sort_keys=False)

        print(f"\nCreated: {yaml_path}")
