"""Roboflow segmentation dataset handler."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class RoboflowSegHandler(BaseDatasetHandler):
    """
    Download Roboflow segmentation datasets in YOLO-seg or COCO format.

    Parameters
    ----------
    output_dir : str
        Output directory for downloaded dataset.
    api_key : str
        Roboflow API key.
    verbose : bool
        Print progress information.

    Examples
    --------
    >>> handler = RoboflowSegHandler("data/my_seg", api_key="key")
    >>> handler.download(workspace="ws", project="proj", version=1, format_type="yolov8")
    """

    def __init__(self, output_dir: str, api_key: str, verbose: bool = True):
        self.api_key = api_key
        super().__init__(output_dir, verbose=verbose)

    def download(
        self,
        workspace: str,
        project: str,
        version: int,
        format_type: str = "yolov8",
        **kwargs,
    ) -> Path:
        """
        Download a Roboflow segmentation project.

        Parameters
        ----------
        workspace : str
            Roboflow workspace name.
        project : str
            Project name.
        version : int
            Dataset version number.
        format_type : str
            Export format. ``"yolov8"`` for YOLO-seg, ``"coco"`` for COCO
            with segmentation polygons. Defaults to ``"yolov8"``.

        Returns
        -------
        Path
            Path to downloaded dataset directory.
        """
        try:
            from roboflow import Roboflow
        except ImportError as exc:
            raise ImportError("roboflow required. Install: pip install roboflow") from exc

        supported = ("yolov8", "coco", "coco-segmentation", "yolo11", "yolo26")
        if format_type not in supported:
            raise ValueError(f"Unsupported format: {format_type}. Use one of {supported}")

        self._print(f"Downloading {workspace}/{project} v{version} ({format_type})")

        rf = Roboflow(api_key=self.api_key)
        project_obj = rf.workspace(workspace).project(project)
        version_obj = project_obj.version(version)

        dataset = version_obj.download(
            format_type,
            location=str(self.output_dir),
            overwrite=True,
        )

        dataset_dir = Path(dataset.location)
        self._print(f"Dataset downloaded to: {dataset_dir}")

        if format_type == "coco":
            self._ensure_coco_structure(dataset_dir)

        return dataset_dir

    def convert(self, format: str, **kwargs) -> Optional[str]:
        """Return path to data.yaml if YOLO, else None."""
        if format == "yolo":
            yaml_path = self.output_dir / "data.yaml"
            return str(yaml_path) if yaml_path.exists() else None
        return None

    def _ensure_coco_structure(self, dataset_dir: Path) -> None:
        """Move annotation files into expected locations."""
        for split in ("train", "valid", "test"):
            split_dir = dataset_dir / split
            if not split_dir.exists():
                continue
            ann = split_dir / "_annotations.coco.json"
            if not ann.exists():
                nested = split_dir / "annotations" / "_annotations.coco.json"
                if nested.exists():
                    shutil.move(str(nested), str(ann))
