"""Ultralytics-hosted segmentation dataset handler.

Supports any dataset available through Ultralytics auto-download (e.g. crack-seg).
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from nectar.ai.core.utils.ultralytics_datasets import nectar_ultralytics_datasets_dir
from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler
from nectar.ai.paths import DEFAULT_DATA_DIR
from nectar.ai.segmentation.datasets.format import SegFormatConverter

logger = logging.getLogger(__name__)


class UltralyticsSegHandler(BaseDatasetHandler):
    """
    Download and manage Ultralytics-hosted segmentation datasets.

    Works with any dataset supported by the Ultralytics auto-download mechanism
    (e.g. ``crack-seg``).  The dataset is downloaded in YOLO-seg format and can
    optionally be converted to COCO with segmentation polygons.

    Parameters
    ----------
    output_dir : str
        Output directory for the processed dataset.
    dataset_name : str
        Ultralytics dataset identifier (e.g. ``"crack-seg"``).
    verbose : bool
        Print progress information.

    Examples
    --------
    >>> handler = UltralyticsSegHandler("data/crack-seg", "crack-seg")
    >>> handler.download_and_convert(output_format="coco")
    """

    CACHE_DIR = DEFAULT_DATA_DIR / "ultralytics"

    def __init__(self, output_dir: str, dataset_name: str, verbose: bool = True):
        super().__init__(output_dir, verbose=verbose)
        self.dataset_name = dataset_name

    def download(self, **kwargs) -> Path:
        """
        Download dataset via Ultralytics auto-download.

        Returns
        -------
        Path
            Path to the downloaded dataset directory.
        """
        try:
            from ultralytics.data.utils import check_det_dataset
        except ImportError as exc:
            raise ImportError(
                "ultralytics is required for download. Install: pip install ultralytics"
            ) from exc

        dataset_id = self.dataset_name
        if not dataset_id.endswith(".yaml"):
            dataset_id = f"{dataset_id}.yaml"

        self._print(f"Downloading '{dataset_id}' via Ultralytics...")

        with nectar_ultralytics_datasets_dir(self.CACHE_DIR):
            data_info = check_det_dataset(dataset_id)

        source_path = Path(data_info.get("path", "")).resolve()
        if not source_path.exists():
            yaml_file = data_info.get("yaml_file", "")
            source_path = Path(yaml_file).parent if yaml_file else source_path

        if source_path.resolve() != self.output_dir.resolve():
            self._reorganize(source_path, data_info)

        self._print(f"Dataset ready at: {self.output_dir}")
        return self.output_dir

    def convert(self, format: str, **kwargs) -> Optional[str]:
        """
        Convert the downloaded dataset to the requested format.

        Parameters
        ----------
        format : str
            Target format (``"yolo"`` or ``"coco"``).

        Returns
        -------
        str or None
            Path to ``data.yaml`` (YOLO) or target dir (COCO).
        """
        num_workers = kwargs.get("num_workers")

        if format == "yolo":
            yaml_path = self.output_dir / "data.yaml"
            return str(yaml_path) if yaml_path.exists() else None

        if format == "coco":
            coco_dir = self.output_dir.parent / f"{self.output_dir.name}_coco"
            converter = SegFormatConverter(
                str(self.output_dir),
                str(coco_dir),
                verbose=self.verbose,
                num_workers=num_workers,
            )
            converter.yolo_seg_to_coco(copy_images=False)

            for split_dir in coco_dir.iterdir():
                if not split_dir.is_dir():
                    continue
                target = self.output_dir / split_dir.name
                target.mkdir(parents=True, exist_ok=True)
                ann_file = split_dir / "_annotations.coco.json"
                if ann_file.exists():
                    with open(ann_file, encoding="utf-8") as f:
                        coco_data = json.load(f)
                    for img in coco_data["images"]:
                        if not img["file_name"].startswith("images/"):
                            img["file_name"] = f"images/{img['file_name']}"
                    dst = target / "_annotations.coco.json"
                    with open(dst, "w", encoding="utf-8") as f:
                        json.dump(coco_data, f, indent=2)

            shutil.rmtree(coco_dir, ignore_errors=True)
            return str(self.output_dir)

        raise ValueError(f"Unsupported format: {format}")

    def download_and_convert(
        self,
        output_format: str = "yolo",
        splits: Optional[List[str]] = None,
        num_workers: Optional[int] = None,
    ) -> Tuple[str, Dict[str, str]]:
        """
        Download dataset and optionally convert to COCO format.

        Parameters
        ----------
        output_format : str
            ``"yolo"``, ``"coco"``, or ``"both"``.
        splits : list of str, optional
            Unused, kept for API compatibility.
        num_workers : int, optional
            Parallel workers for conversion.

        Returns
        -------
        tuple of (str, dict)
            ``(yaml_path, coco_annotation_paths)``
        """
        self.download()

        yaml_path = str(self.output_dir / "data.yaml")
        coco_paths: Dict[str, str] = {}

        if output_format in ("coco", "both"):
            self.convert("coco", num_workers=num_workers)
            for split in ("train", "valid", "test"):
                ann = self.output_dir / split / "_annotations.coco.json"
                if ann.exists():
                    coco_paths[split] = str(ann)

        return yaml_path, coco_paths

    def _reorganize(self, source_path: Path, data_info: Optional[dict] = None) -> None:
        """Copy/symlink dataset files into output_dir with standard layout."""
        names = {}

        if data_info:
            names = data_info.get("names", {})
            for split_key in ("train", "val", "test"):
                img_path_raw = data_info.get(split_key, "")
                if not img_path_raw:
                    continue
                split_images = Path(str(img_path_raw)).resolve()
                if not split_images.exists():
                    continue

                target_name = "valid" if split_key == "val" else split_key
                target_split = self.output_dir / target_name

                (target_split / "images").mkdir(parents=True, exist_ok=True)
                for img in split_images.glob("*.*"):
                    dst = target_split / "images" / img.name
                    if not dst.exists():
                        shutil.copy2(img, dst)

                # Derive labels dir from images dir:
                # images/train -> labels/train
                labels_dir = split_images.parent.parent / "labels" / split_images.name
                if not labels_dir.exists():
                    labels_dir = split_images.parent / "labels"
                if labels_dir.exists():
                    (target_split / "labels").mkdir(parents=True, exist_ok=True)
                    for lbl in labels_dir.glob("*.txt"):
                        dst = target_split / "labels" / lbl.name
                        if not dst.exists():
                            shutil.copy2(lbl, dst)

            self._write_data_yaml(names)
            return

        yaml_path = source_path / "data.yaml"
        if not yaml_path.exists():
            for candidate in source_path.rglob("data.yaml"):
                yaml_path = candidate
                source_path = candidate.parent
                break

        if yaml_path.exists():
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            names = data.get("names", {})
            for split_key in ("train", "val", "test"):
                rel = data.get(split_key, "")
                if not rel:
                    continue
                split_images = (source_path / rel).resolve()
                if not split_images.exists():
                    continue

                target_name = "valid" if split_key == "val" else split_key
                target_split = self.output_dir / target_name

                if split_images.resolve() == (target_split / "images").resolve():
                    continue

                (target_split / "images").mkdir(parents=True, exist_ok=True)
                for img in split_images.glob("*.*"):
                    dst = target_split / "images" / img.name
                    if not dst.exists():
                        shutil.copy2(img, dst)

                split_name = Path(rel).name
                labels_dir = source_path / "labels" / split_name
                if not labels_dir.exists():
                    labels_dir = split_images.parent / "labels"
                if labels_dir.exists():
                    (target_split / "labels").mkdir(parents=True, exist_ok=True)
                    for lbl in labels_dir.glob("*.txt"):
                        dst = target_split / "labels" / lbl.name
                        if not dst.exists():
                            shutil.copy2(lbl, dst)

            self._write_data_yaml(names)

    def _write_data_yaml(self, names) -> Path:
        """Write a canonical data.yaml for the output directory."""
        if isinstance(names, list):
            names_dict = {i: n for i, n in enumerate(names)}
        elif isinstance(names, dict):
            names_dict = {int(k): v for k, v in names.items()}
        else:
            names_dict = {0: "object"}

        yaml_data = {
            "path": str(self.output_dir.absolute()),
            "names": names_dict,
            "nc": len(names_dict),
        }

        for split in ("train", "valid", "test"):
            split_dir = self.output_dir / split
            if (split_dir / "images").exists():
                key = "val" if split == "valid" else split
                yaml_data[key] = f"{split}/images"

        out = self.output_dir / "data.yaml"
        with open(out, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f, sort_keys=False)
        return out
