"""Roboflow dataset handler for download and format conversion."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RoboflowHandler:
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
    ...     format="yolo"
    ... )
    """

    def __init__(self, output_dir: str, api_key: str, verbose: bool = True):
        self.api_key = api_key
        self.verbose = verbose

        output_path = Path(output_dir).expanduser().resolve()

        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied creating directory: {output_path}\n"
                f"Use a relative path (e.g., '../datasets/my-project') or a path in your home directory."
            ) from e
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Parent directory does not exist: {output_path.parent}\n"
                f"Ensure the parent directory exists or use a relative path."
            ) from e

        self.output_dir = output_path

    def _print(self, message: str) -> None:
        if self.verbose:
            print(message)

    def download(
        self,
        workspace: str,
        project: str,
        version: int,
        format_type: str = "yolo",
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
            raise ImportError(
                "roboflow required. Install: pip install roboflow"
            ) from exc

        yolo_formats = ["yolo", "yolov8", "yolov9", "yolov11", "yolov12", "yolo26"]
        if format_type not in yolo_formats + ["coco"]:
            raise ValueError(
                f"Unsupported format: {format_type}. "
                f"Use 'yolo', 'yolov8', 'yolov9', 'yolov11', 'yolov12', 'yolo26', or 'coco'"
            )

        self._print(
            f"Downloading {workspace}/{project} v{version} ({format_type} format)"
        )

        rf = Roboflow(api_key=self.api_key)
        project_obj = rf.workspace(workspace).project(project)
        version_obj = project_obj.version(version)

        download_format = "yolo26" if format_type == "yolo" else format_type
        dataset = version_obj.download(
            download_format, location=str(self.output_dir), overwrite=True
        )

        dataset_dir = Path(dataset.location)
        self._print(f"Dataset downloaded to: {dataset_dir}")

        if format_type == "coco":
            self._ensure_coco_structure(dataset_dir)

        return dataset_dir

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
                    import shutil

                    shutil.move(
                        str(ann_file), str(split_dir / "_annotations.coco.json")
                    )


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
