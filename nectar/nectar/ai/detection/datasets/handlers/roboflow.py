"""Roboflow dataset handler for download and format conversion."""

import logging
import shutil
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class RoboflowHandler(BaseDatasetHandler):
    """
    Download Roboflow datasets in YOLO or COCO format.

    Parameters
    ----------
    output_dir : str
        Output directory for downloaded dataset.
    api_key : str
        Roboflow API key.
    verbose : bool, optional
        Print progress. Defaults to True.

    Examples
    --------
    >>> handler = RoboflowHandler("datasets/roboflow", api_key="your_key")
    >>> handler.download(
    ...     workspace="black-bee-drones",
    ...     project="imav-25-gate-sfbbq",
    ...     version=1,
    ...     format_type="yolo"
    ... )
    """

    def __init__(self, output_dir: str, api_key: str, verbose: bool = True):
        self.api_key = api_key
        super().__init__(output_dir, verbose=verbose)

    def download(
        self,
        workspace: str,
        project: str,
        version: int,
        format_type: str = "yolo",
        **kwargs,
    ) -> Path:
        """
        Download Roboflow dataset.

        Parameters
        ----------
        workspace : str
            Roboflow workspace name.
        project : str
            Project name.
        version : int
            Dataset version number.
        format_type : str, optional
            Format ("yolo", "yolov8", "yolov9", "yolov11", "yolov12", "yolo26", or "coco").
            "yolo" maps to "yolo26". Defaults to "yolo".

        Returns
        -------
        Path
            Path to downloaded dataset directory.
        """
        try:
            from roboflow import Roboflow
        except ImportError as exc:
            raise ImportError("roboflow required. Install: pip install roboflow") from exc

        # Known short aliases. Anything else is passed through to Roboflow as-is,
        # so callers can request formats like ``coco-mmdetection``, ``coco-segmentation``,
        # ``yolov8-obb``, etc. Roboflow validates the final string against the project type.
        download_format = "yolo26" if format_type == "yolo" else format_type

        self._print(f"Downloading {workspace}/{project} v{version} ({download_format} format)")

        rf = Roboflow(api_key=self.api_key)
        project_obj = rf.workspace(workspace).project(project)
        version_obj = project_obj.version(version)

        dataset = version_obj.download(
            download_format, location=str(self.output_dir), overwrite=True
        )

        dataset_dir = Path(dataset.location)
        self._print(f"Dataset downloaded to: {dataset_dir}")

        if format_type == "coco":
            self._ensure_coco_structure(dataset_dir)

        return dataset_dir

    def convert(self, format: str, **kwargs) -> Optional[str]:
        """
        Convert dataset format (Roboflow downloads are already in the requested format).

        Parameters
        ----------
        format : str
            Target format (not used, dataset is already in correct format).

        Returns
        -------
        str or None
            Path to data.yaml if YOLO format, None otherwise.
        """
        dataset_dir = kwargs.get("dataset_dir", self.output_dir)
        dataset_dir = Path(dataset_dir)

        if format == "yolo":
            yaml_path = dataset_dir / "data.yaml"
            if yaml_path.exists():
                return str(yaml_path)
        elif format == "coco":
            return None
        else:
            raise ValueError(f"Unsupported format: {format}")

        return None

    def _ensure_coco_structure(self, dataset_dir: Path) -> None:
        """Ensure COCO format has correct structure with _annotations.coco.json files."""
        for split in ["train", "valid", "test"]:
            split_dir = dataset_dir / split
            if not split_dir.exists():
                continue

            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                ann_file = split_dir / "annotations" / "_annotations.coco.json"
                if ann_file.exists():
                    shutil.move(str(ann_file), str(split_dir / "_annotations.coco.json"))


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download Roboflow dataset")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--api-key", required=True, help="Roboflow API key")
    parser.add_argument("--workspace", required=True, help="Workspace name")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--version", type=int, required=True, help="Version number")
    parser.add_argument(
        "--format",
        choices=["yolo", "yolov8", "yolov9", "yolov11", "yolov12", "yolo26", "coco"],
        default="yolo",
        help="Dataset format (yolo maps to yolo26)",
        dest="format_type",
    )

    args = parser.parse_args()

    handler = RoboflowHandler(args.output_dir, args.api_key)
    handler.download(
        workspace=args.workspace,
        project=args.project,
        version=args.version,
        format_type=args.format_type,
    )


if __name__ == "__main__":
    main()
