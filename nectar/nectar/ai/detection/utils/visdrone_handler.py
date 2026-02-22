"""VisDrone dataset handler for download and format conversion."""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from PIL import Image


class VisDroneHandler:
    """
    Download and convert VisDrone dataset to YOLO/COCO formats.

    Parameters
    ----------
    output_dir : str
        Output directory for processed dataset.
    verbose : bool, optional
        Print progress. Defaults to True.

    Examples
    --------
    >>> handler = VisDroneHandler("datasets/visdrone")
    >>> handler.download_and_convert(
    ...     output_format="yolo",
    ...     splits=["train", "val", "test"]
    ... )
    """

    VISDRONE_CLASSES = {
        0: "pedestrian",
        1: "people",
        2: "bicycle",
        3: "car",
        4: "van",
        5: "truck",
        6: "tricycle",
        7: "awning-tricycle",
        8: "bus",
        9: "motor",
    }

    def __init__(self, output_dir: str, verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _print(self, message: str) -> None:
        if self.verbose:
            print(message)

    def download(
        self,
        splits: Optional[List[str]] = None,
        threads: int = 4,
    ) -> Path:
        """
        Download VisDrone dataset.

        Parameters
        ----------
        splits : List[str], optional
            Splits to download. Defaults to ["train", "val", "test"].
        threads : int, optional
            Download threads. Defaults to 4.

        Returns
        -------
        Path
            Path to downloaded dataset directory.
        """
        if splits is None:
            splits = ["train", "val", "test"]

        try:
            from ultralytics.utils.downloads import download
            from ultralytics.utils import ASSETS_URL
        except ImportError as exc:
            raise ImportError(
                "ultralytics required for download. Install: pip install ultralytics"
            ) from exc

        urls = [
            f"{ASSETS_URL}/VisDrone2019-DET-train.zip",
            f"{ASSETS_URL}/VisDrone2019-DET-val.zip",
            f"{ASSETS_URL}/VisDrone2019-DET-test-dev.zip",
        ]

        self._print(f"Downloading VisDrone dataset to {self.output_dir}")
        download(urls, dir=self.output_dir, threads=threads)

        return self.output_dir

    def convert_to_yolo(
        self,
        source_dir: Optional[Path] = None,
        splits: Optional[List[str]] = None,
    ) -> str:
        """
        Convert VisDrone annotations to YOLO format.

        Parameters
        ----------
        source_dir : Path, optional
            Source directory. Auto-detects if None.
        splits : List[str], optional
            Splits to convert. Defaults to ["train", "val", "test"].

        Returns
        -------
        str
            Path to generated data.yaml.
        """
        if splits is None:
            splits = ["train", "val", "test"]

        if source_dir is None:
            source_dir = self._find_source_dir()

        self._print(f"Converting VisDrone to YOLO format from {source_dir}")

        for split in splits:
            self._convert_split_to_yolo(source_dir, split)

        yaml_path = self._create_yolo_yaml()
        self._print(f"YOLO format saved: {yaml_path}")
        return str(yaml_path)

    def convert_to_coco(
        self,
        source_dir: Optional[Path] = None,
        splits: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Convert VisDrone annotations to COCO format.

        Parameters
        ----------
        source_dir : Path, optional
            Source directory. Auto-detects if None.
        splits : List[str], optional
            Splits to convert. Defaults to ["train", "val", "test"].

        Returns
        -------
        Dict[str, str]
            Mapping of split names to annotation file paths.
        """
        if splits is None:
            splits = ["train", "val", "test"]

        if source_dir is None:
            source_dir = self._find_source_dir()

        self._print(f"Converting VisDrone to COCO format from {source_dir}")

        result_paths = {}

        for split in splits:
            ann_path = self._convert_split_to_coco(source_dir, split)
            result_paths[split] = str(ann_path)

        self._print(f"COCO format saved to: {self.output_dir}")
        return result_paths

    def download_and_convert(
        self,
        output_format: str = "yolo",
        splits: Optional[List[str]] = None,
        download: bool = True,
        threads: int = 4,
    ) -> Tuple[str, Dict[str, str]]:
        """
        Download and convert VisDrone dataset.

        Parameters
        ----------
        output_format : str
            Output format ("yolo", "coco", or "both"). Defaults to "yolo".
        splits : List[str], optional
            Splits to process. Defaults to ["train", "val", "test"].
        download : bool, optional
            Download dataset. Defaults to True.
        threads : int, optional
            Download threads. Defaults to 4.

        Returns
        -------
        Tuple[str, Dict[str, str]]
            (yaml_path, coco_paths_dict)
        """
        if splits is None:
            splits = ["train", "val", "test"]

        source_dir = None
        if download:
            self.download(splits=splits, threads=threads)
            source_dir = self._find_source_dir()

        yaml_path = ""
        coco_paths = {}

        if output_format in ["yolo", "both"]:
            yaml_path = self.convert_to_yolo(source_dir=source_dir, splits=splits)

        if output_format in ["coco", "both"]:
            coco_paths = self.convert_to_coco(source_dir=source_dir, splits=splits)

        return yaml_path, coco_paths

    def _find_source_dir(self) -> Path:
        """Find source directory with VisDrone data."""
        candidates = [
            self.output_dir / "VisDrone2019-DET-train",
            self.output_dir / "VisDrone2019-DET-val",
            self.output_dir / "VisDrone2019-DET-test-dev",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate.parent

        raise FileNotFoundError(
            f"VisDrone source not found in {self.output_dir}. Run download() first."
        )

    def _convert_split_to_yolo(self, source_dir: Path, split: str) -> None:
        """Convert a single split to YOLO format."""
        split_map = {
            "train": "VisDrone2019-DET-train",
            "val": "VisDrone2019-DET-val",
            "test": "VisDrone2019-DET-test-dev",
        }

        source_split = source_dir / split_map.get(split, f"VisDrone2019-DET-{split}")
        if not source_split.exists():
            self._print(f"Warning: {source_split} not found, skipping")
            return

        images_dir = self.output_dir / split / "images"
        labels_dir = self.output_dir / split / "labels"
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)

        source_images = source_split / "images"
        source_annotations = source_split / "annotations"

        if not source_annotations.exists():
            self._print(f"Warning: {source_annotations} not found, skipping")
            return

        ann_files = list(source_annotations.glob("*.txt"))
        if tqdm:
            ann_files = tqdm(ann_files, desc=f"Converting {split}")

        for ann_file in ann_files:
            img_name = ann_file.with_suffix(".jpg").name
            img_path = source_images / img_name

            if not img_path.exists():
                continue

            try:
                img = Image.open(img_path)
                img_width, img_height = img.size
            except Exception as e:
                self._print(f"Warning: {img_path} - {e}")
                continue

            dw, dh = 1.0 / img_width, 1.0 / img_height
            lines = []

            with open(ann_file, encoding="utf-8") as f:
                for row in f.read().strip().splitlines():
                    parts = row.split(",")
                    if len(parts) < 6:
                        continue

                    if parts[4] == "0":
                        continue

                    x, y, w, h = map(int, parts[:4])
                    cls = int(parts[5]) - 1

                    if cls < 0 or cls >= len(self.VISDRONE_CLASSES):
                        continue

                    x_center = (x + w / 2) * dw
                    y_center = (y + h / 2) * dh
                    w_norm = w * dw
                    h_norm = h * dh

                    lines.append(
                        f"{cls} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}\n"
                    )

            if lines:
                label_path = labels_dir / ann_file.name
                label_path.write_text("".join(lines), encoding="utf-8")

                shutil.copy2(img_path, images_dir / img_name)

    def _convert_split_to_coco(self, source_dir: Path, split: str) -> Path:
        """Convert a single split to COCO format."""
        split_map = {
            "train": "VisDrone2019-DET-train",
            "val": "VisDrone2019-DET-val",
            "test": "VisDrone2019-DET-test-dev",
        }

        source_split = source_dir / split_map.get(split, f"VisDrone2019-DET-{split}")
        if not source_split.exists():
            raise FileNotFoundError(f"Source split not found: {source_split}")

        target_split = self.output_dir / split
        target_split.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": i, "name": name} for i, name in self.VISDRONE_CLASSES.items()
        ]

        coco_data = {"images": [], "annotations": [], "categories": categories}

        source_images = source_split / "images"
        source_annotations = source_split / "annotations"

        if not source_annotations.exists():
            raise FileNotFoundError(f"Annotations not found: {source_annotations}")

        ann_files = list(source_annotations.glob("*.txt"))
        if tqdm:
            ann_files = tqdm(ann_files, desc=f"Converting {split}")

        annotation_id = 1

        for img_idx, ann_file in enumerate(ann_files, 1):
            img_name = ann_file.with_suffix(".jpg").name
            img_path = source_images / img_name

            if not img_path.exists():
                continue

            try:
                img = Image.open(img_path)
                img_width, img_height = img.size
            except Exception as e:
                self._print(f"Warning: {img_path} - {e}")
                continue

            coco_data["images"].append(
                {
                    "id": img_idx,
                    "file_name": img_name,
                    "width": img_width,
                    "height": img_height,
                }
            )

            with open(ann_file, encoding="utf-8") as f:
                for row in f.read().strip().splitlines():
                    parts = row.split(",")
                    if len(parts) < 6:
                        continue

                    if parts[4] == "0":
                        continue

                    x, y, w, h = map(int, parts[:4])
                    cls = int(parts[5]) - 1

                    if cls < 0 or cls >= len(self.VISDRONE_CLASSES):
                        continue

                    coco_data["annotations"].append(
                        {
                            "id": annotation_id,
                            "image_id": img_idx,
                            "category_id": cls,
                            "bbox": [x, y, w, h],
                            "area": w * h,
                            "iscrowd": 0,
                        }
                    )
                    annotation_id += 1

            shutil.copy2(img_path, target_split / img_name)

        ann_path = target_split / "_annotations.coco.json"
        with open(ann_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, indent=2)

        return ann_path

    def _create_yolo_yaml(self) -> Path:
        """Create YOLO data.yaml file."""
        yaml_data = {
            "path": str(self.output_dir.absolute()),
            "names": self.VISDRONE_CLASSES,
            "nc": len(self.VISDRONE_CLASSES),
        }

        if (self.output_dir / "train").exists():
            yaml_data["train"] = "train/images"
        if (self.output_dir / "val").exists():
            yaml_data["val"] = "val/images"
        if (self.output_dir / "test").exists():
            yaml_data["test"] = "test/images"

        yaml_path = self.output_dir / "data.yaml"

        try:
            import yaml

            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_data, f, sort_keys=False)
        except ImportError as exc:
            json_path = yaml_path.with_suffix(".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(yaml_data, f, indent=2)
            raise ImportError("yaml required. Install: pip install pyyaml") from exc

        return yaml_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and convert VisDrone dataset"
    )
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument(
        "--format",
        choices=["yolo", "coco", "both"],
        default="yolo",
        help="Output format",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val", "test"],
        help="Dataset splits",
    )
    parser.add_argument("--no-download", action="store_true", help="Skip download")
    parser.add_argument("--threads", type=int, default=4, help="Download threads")

    args = parser.parse_args()

    handler = VisDroneHandler(args.output_dir)
    handler.download_and_convert(
        output_format=args.format,
        splits=args.splits,
        download=not args.no_download,
        threads=args.threads,
    )


if __name__ == "__main__":
    main()
