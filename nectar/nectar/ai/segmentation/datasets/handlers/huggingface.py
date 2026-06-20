"""HuggingFace Hub handler for downloading instance-segmentation datasets."""

import logging
import os
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class HuggingFaceSegHandler(BaseDatasetHandler):
    """
    Download instance-segmentation datasets from the HuggingFace Hub and
    materialize them on disk as COCO-seg or YOLO-seg directories ready for
    training.

    Expects datasets with the native segmentation schema written by
    :meth:`HuggingFaceSegDatasetUploader.upload_native`: ``image`` +
    ``objects.{bbox, category, area, segmentation}``.

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
    >>> handler = HuggingFaceSegHandler("data/sae-2026-hook")
    >>> handler.download(
    ...     repo_id="blackbeedrones/sae-2026-hook",
    ...     format_type="yolo",
    ... )
    """

    def __init__(self, output_dir: str, token: Optional[str] = None, verbose: bool = True):
        self.token = token or os.environ.get("HF_TOKEN")
        super().__init__(output_dir, verbose=verbose)

    def download(
        self,
        repo_id: str,
        format_type: str = "yolo",
        split: Optional[str] = None,
        revision: Optional[str] = None,
        image_format: str = "jpg",
        **kwargs,
    ) -> Path:
        """
        Download a HuggingFace segmentation dataset and materialize it to disk.

        Parameters
        ----------
        repo_id : str
            HuggingFace dataset repository id (``user/name``).
        format_type : str, optional
            ``"yolo"`` (YOLO-seg) or ``"coco"`` (COCO-seg). Defaults to ``"yolo"``.
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

        from nectar.ai.segmentation.datasets.hf_converter import hf_to_coco_seg, hf_to_yolo_seg

        fmt = format_type.lower()
        if fmt not in ("coco", "yolo"):
            raise ValueError(f"Unsupported format: {format_type}. Use 'coco' or 'yolo'.")

        self._print(f"Loading {repo_id} from HuggingFace Hub")
        ds = load_dataset(repo_id, token=self.token, revision=revision, split=split)

        self._print(f"Materializing to {self.output_dir} as {fmt}-seg")
        if fmt == "coco":
            hf_to_coco_seg(ds, str(self.output_dir), image_format=image_format)
        else:
            hf_to_yolo_seg(ds, str(self.output_dir), image_format=image_format)

        self._print(f"Dataset written to: {self.output_dir}")
        return self.output_dir

    def convert(self, format: str, **kwargs) -> Optional[str]:
        """
        Datasets are already materialized in the requested format by ``download``.

        Returns the path to ``data.yaml`` if YOLO, else ``None``.
        """
        if format == "yolo":
            yaml_path = self.output_dir / "data.yaml"
            if yaml_path.exists():
                return str(yaml_path)
        return None


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download a HuggingFace segmentation dataset to COCO-seg/YOLO-seg"
    )
    parser.add_argument("--output-dir", required=True, help="Local output directory")
    parser.add_argument("--repo", required=True, help="HF dataset repo (user/name)")
    parser.add_argument("--format", choices=["coco", "yolo"], default="yolo")
    parser.add_argument("--split", help="Single split to download")
    parser.add_argument("--revision", help="Git revision (branch/tag/commit)")
    parser.add_argument("--token", help="HF API token (or set HF_TOKEN)")

    args = parser.parse_args()

    handler = HuggingFaceSegHandler(args.output_dir, token=args.token)
    handler.download(
        repo_id=args.repo,
        format_type=args.format,
        split=args.split,
        revision=args.revision,
    )


if __name__ == "__main__":
    main()
