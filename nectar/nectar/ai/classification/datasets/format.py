"""ImageFolder format detection and helpers for classification datasets."""

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
SPLIT_NAMES = ("train", "val", "valid", "validation", "test")

_SPLIT_ALIASES = {
    "val": ["val", "valid", "validation"],
    "valid": ["valid", "val", "validation"],
    "test": ["test", "val", "valid", "validation"],
    "train": ["train"],
}


def resolve_split_dir(root: Path, split: str) -> Path:
    """Resolve train/val/test (with aliases) under an ImageFolder root."""
    root = Path(root)
    for name in _SPLIT_ALIASES.get(split, [split]):
        candidate = root / name
        if candidate.is_dir():
            return candidate
    if _has_class_dirs(root):
        return root
    raise FileNotFoundError(f"Split '{split}' not found in {root}")


def _has_class_dirs(path: Path) -> bool:
    class_dirs = [p for p in path.iterdir() if p.is_dir() and p.name not in SPLIT_NAMES]
    if not class_dirs:
        return False
    for class_dir in class_dirs:
        if any(f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS for f in class_dir.rglob("*")):
            return True
    return False


class ImageFolderDetector:
    """Detect and validate ImageFolder classification layout."""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)

    def is_imagefolder(self) -> bool:
        """Return True if path looks like ImageFolder (with or without splits)."""
        if not self.dataset_path.exists() or not self.dataset_path.is_dir():
            return False

        for split in SPLIT_NAMES:
            split_dir = self.dataset_path / split
            if split_dir.is_dir() and _has_class_dirs(split_dir):
                return True

        return _has_class_dirs(self.dataset_path)

    def detect(self) -> str:
        return "imagefolder" if self.is_imagefolder() else "unknown"

    def class_names(self, split: str = "train") -> List[str]:
        split_dir = resolve_split_dir(self.dataset_path, split)
        return sorted([p.name for p in split_dir.iterdir() if p.is_dir()])

    def count_samples(self) -> Dict[str, Dict[str, int]]:
        """Return {split: {class_name: count}}."""
        counts: Dict[str, Dict[str, int]] = {}
        for split in SPLIT_NAMES:
            split_dir = self.dataset_path / split
            if not split_dir.is_dir():
                continue
            counts[split] = {}
            for class_dir in sorted(p for p in split_dir.iterdir() if p.is_dir()):
                n = sum(
                    1
                    for f in class_dir.rglob("*")
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                )
                counts[split][class_dir.name] = n
        if not counts and _has_class_dirs(self.dataset_path):
            counts["all"] = {}
            for class_dir in sorted(p for p in self.dataset_path.iterdir() if p.is_dir()):
                if class_dir.name in SPLIT_NAMES:
                    continue
                n = sum(
                    1
                    for f in class_dir.rglob("*")
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                )
                counts["all"][class_dir.name] = n
        return counts

    def _resolve_split(self, split: str) -> Path:
        return resolve_split_dir(self.dataset_path, split)

    @staticmethod
    def _has_class_dirs(path: Path) -> bool:
        return _has_class_dirs(path)


class ClsFormatConverter:
    """Helpers to normalize classification dataset layouts."""

    def __init__(self, input_path: str, output_path: str, verbose: bool = True):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.verbose = verbose

    def normalize_split_names(self) -> str:
        """
        Copy dataset ensuring splits are named train/val/test.

        Maps valid/validation → val.
        """
        detector = ImageFolderDetector(str(self.input_path))
        if not detector.is_imagefolder():
            raise ValueError(f"Not an ImageFolder dataset: {self.input_path}")

        self.output_path.mkdir(parents=True, exist_ok=True)
        mapping = {"valid": "val", "validation": "val"}

        for split_dir in self.input_path.iterdir():
            if not split_dir.is_dir():
                continue
            if split_dir.name in SPLIT_NAMES:
                dest_name = mapping.get(split_dir.name, split_dir.name)
                dest = self.output_path / dest_name
                if dest.exists():
                    continue
                shutil.copytree(split_dir, dest)
            elif ImageFolderDetector._has_class_dirs(split_dir):
                # unexpected nested layout
                continue

        # Unsplit ImageFolder → put everything under train
        if not any((self.output_path / s).exists() for s in ("train", "val", "test")):
            train_dest = self.output_path / "train"
            train_dest.mkdir(parents=True, exist_ok=True)
            for class_dir in self.input_path.iterdir():
                if class_dir.is_dir() and class_dir.name not in SPLIT_NAMES:
                    shutil.copytree(class_dir, train_dest / class_dir.name)

        if self.verbose:
            logger.info("Normalized ImageFolder written to %s", self.output_path)
        return str(self.output_path)


def stratify_imagefolder(
    input_path: str,
    output_path: str,
    train_ratio: float = 0.8,
    val_ratio: float = 0.2,
    test_ratio: float = 0.0,
    seed: int = 42,
) -> str:
    """Split an unsplit ImageFolder into train/val/test preserving class ratios."""
    import random

    random.seed(seed)
    src = Path(input_path)
    dst = Path(output_path)

    if (src / "train").is_dir():
        raise ValueError("Dataset already has splits; use subset instead of stratify")

    class_dirs = sorted([p for p in src.iterdir() if p.is_dir() and p.name not in SPLIT_NAMES])
    if not class_dirs:
        raise ValueError(f"No class directories in {src}")

    for split_name in ("train", "val", "test"):
        (dst / split_name).mkdir(parents=True, exist_ok=True)

    for class_dir in class_dirs:
        images = [
            f
            for f in sorted(class_dir.rglob("*"))
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
        random.shuffle(images)
        n = len(images)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        splits = {
            "train": images[:n_train],
            "val": images[n_train : n_train + n_val],
            "test": images[n_train + n_val :],
        }
        if test_ratio <= 0:
            splits["test"] = []

        for split_name, files in splits.items():
            class_out = dst / split_name / class_dir.name
            class_out.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.copy2(f, class_out / f.name)

    return str(dst)


def subset_imagefolder(
    input_path: str,
    output_path: str,
    max_train_samples: Optional[int] = None,
    max_eval_samples: Optional[int] = None,
    max_test_samples: Optional[int] = None,
    seed: int = 42,
) -> str:
    """Create a balanced subset of an ImageFolder dataset."""
    import random

    random.seed(seed)
    src = Path(input_path)
    dst = Path(output_path)
    limits = {
        "train": max_train_samples,
        "val": max_eval_samples,
        "valid": max_eval_samples,
        "test": max_test_samples,
    }

    for split_dir in src.iterdir():
        if not split_dir.is_dir() or split_dir.name not in SPLIT_NAMES:
            continue
        limit = limits.get(split_dir.name)
        dest_split = "val" if split_dir.name in ("valid", "validation") else split_dir.name
        class_dirs = sorted([p for p in split_dir.iterdir() if p.is_dir()])
        if not class_dirs:
            continue

        if limit is None:
            shutil.copytree(split_dir, dst / dest_split, dirs_exist_ok=True)
            continue

        per_class = max(1, limit // len(class_dirs))
        for class_dir in class_dirs:
            images = [
                f
                for f in sorted(class_dir.rglob("*"))
                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
            ]
            random.shuffle(images)
            selected = images[:per_class]
            out_dir = dst / dest_split / class_dir.name
            out_dir.mkdir(parents=True, exist_ok=True)
            for f in selected:
                shutil.copy2(f, out_dir / f.name)

    return str(dst)
