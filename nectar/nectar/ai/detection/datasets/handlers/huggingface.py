"""HuggingFace Hub dataset handler for download and format conversion."""

import logging
import os
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class HuggingFaceHandler(BaseDatasetHandler):
    """
    Download object detection datasets from the HuggingFace Hub and materialize
    them on disk as COCO or YOLO directories ready for training.

    Expects datasets with the standard HF object detection schema:
    ``image`` + ``objects.{bbox,category,...}``. Datasets uploaded via
    :meth:`HuggingFaceDatasetUploader.upload_native` follow this schema.

    Parameters
    ----------
    output_dir : str
        Local directory to write the converted dataset to.
    token : str, optional
        HuggingFace API token. Falls back to the ``HF_TOKEN`` environment
        variable.
    verbose : bool, optional
        Print progress. Defaults to True.

    Examples
    --------
    >>> handler = HuggingFaceHandler("data/imav-gate")
    >>> handler.download(
    ...     repo_id="blackbeedrones/imav-2025-gate-dataset",
    ...     format_type="yolo",
    ... )
    """

    def __init__(
        self,
        output_dir: str,
        token: Optional[str] = None,
        verbose: bool = True,
    ):
        self.token = token or os.environ.get("HF_TOKEN")
        super().__init__(output_dir, verbose=verbose)

    def download(  # pylint: disable=arguments-differ
        self,
        repo_id: str,
        format_type: str = "coco",
        split: Optional[str] = None,
        revision: Optional[str] = None,
        image_format: str = "jpg",
        **kwargs,
    ) -> Path:
        """
        Download a HuggingFace dataset and materialize it to disk.

        Parameters
        ----------
        repo_id : str
            HuggingFace dataset repository id (``user/name``).
        format_type : str, optional
            ``"coco"`` or ``"yolo"``. Defaults to ``"coco"``.
        split : str, optional
            Single split to download (``"train"``, ``"validation"``, ``"test"``).
            When omitted, all splits are written.
        revision : str, optional
            Git revision (branch/tag/commit) to load. Defaults to ``main``.
        image_format : str, optional
            Image extension for materialized files. Defaults to ``"jpg"``.

        Returns
        -------
        Path
            Path to the materialized dataset directory.
        """
        try:
            from datasets import load_dataset
        except ImportError as exc:
            raise ImportError("datasets is required. Install: pip install datasets") from exc

        from nectar.ai.detection.datasets.hf_converter import hf_to_coco, hf_to_yolo

        fmt = format_type.lower()
        if fmt not in ("coco", "yolo"):
            raise ValueError(f"Unsupported format: {format_type}. Use 'coco' or 'yolo'.")

        self._print(f"Loading {repo_id} from HuggingFace Hub")
        ds = load_dataset(repo_id, token=self.token, revision=revision, split=split)

        self._print(f"Materializing to {self.output_dir} as {fmt}")
        if fmt == "coco":
            hf_to_coco(ds, str(self.output_dir), image_format=image_format)
        else:
            hf_to_yolo(ds, str(self.output_dir), image_format=image_format)

        self._print(f"Dataset written to: {self.output_dir}")
        return self.output_dir

    def convert(self, format: str, **kwargs) -> Optional[str]:  # noqa: A002
        """
        Datasets are already materialized in the requested format by ``download``.

        Parameters
        ----------
        format : str
            Target format (``"yolo"`` or ``"coco"``).

        Returns
        -------
        str or None
            Path to ``data.yaml`` if YOLO, else ``None``.
        """
        if format == "yolo":
            yaml_path = self.output_dir / "data.yaml"
            if yaml_path.exists():
                return str(yaml_path)
        return None


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Download a HuggingFace dataset to COCO/YOLO")
    parser.add_argument("--output-dir", required=True, help="Local output directory")
    parser.add_argument("--repo", required=True, help="HF dataset repo (user/name)")
    parser.add_argument("--format", choices=["coco", "yolo"], default="coco")
    parser.add_argument("--split", help="Single split to download")
    parser.add_argument("--revision", help="Git revision (branch/tag/commit)")
    parser.add_argument("--token", help="HF API token (or set HF_TOKEN)")

    args = parser.parse_args()

    handler = HuggingFaceHandler(args.output_dir, token=args.token)
    handler.download(
        repo_id=args.repo,
        format_type=args.format,
        split=args.split,
        revision=args.revision,
    )


if __name__ == "__main__":
    main()
