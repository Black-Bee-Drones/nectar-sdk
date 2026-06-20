"""HuggingFace uploader for instance-segmentation datasets."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from nectar.ai.detection.datasets.upload import HuggingFaceDatasetUploader

logger = logging.getLogger(__name__)


class HuggingFaceSegDatasetUploader(HuggingFaceDatasetUploader):
    """
    Upload instance-segmentation datasets to the HuggingFace Hub.

    Mirrors :class:`HuggingFaceDatasetUploader` (re-using its ``__init__``,
    ``ensure_repo_exists`` and raw ``upload_dataset``) but converts to the
    native segmentation schema (``objects.{bbox, category, area, segmentation}``)
    so the Hub viewer renders bounding-box overlays and the polygon masks are
    preserved for training.

    Examples
    --------
    >>> uploader = HuggingFaceSegDatasetUploader(repo_id="user/my-seg", private=False)
    >>> uploader.upload_native(dataset_path="data/my-seg")
    """

    def upload_native(
        self,
        dataset_path: str,
        source_format: Optional[str] = None,
        commit_message: str = "Upload dataset",
        card_metadata: Optional[Dict[str, Any]] = None,
        write_card: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert a local COCO-seg/YOLO-seg dataset to native Parquet and push.

        Parameters
        ----------
        dataset_path : str
            Local dataset directory in COCO-seg or YOLO-seg format.
        source_format : str, optional
            ``"coco"`` or ``"yolo"``. Auto-detected when ``None``.
        commit_message : str, optional
            Commit message for the README upload (the Parquet shards use the
            ``datasets`` library default message).
        card_metadata : dict, optional
            Forwarded to :func:`generate_seg_dataset_card`. Keys: ``title``,
            ``description``, ``license``, ``tags``, ``model_repo``,
            ``extra_sections``.
        write_card : bool, optional
            Upload the generated README.md. Defaults to True.

        Returns
        -------
        Dict
            ``{"repo_id", "splits": {name: count}, "class_names": [...]}``
        """
        from nectar.ai.detection.datasets.format import FormatDetector
        from nectar.ai.detection.datasets.hf_converter import _class_names_from_dataset
        from nectar.ai.segmentation.datasets.hf_converter import (
            generate_seg_dataset_card,
            seg_coco_to_hf,
            seg_yolo_to_hf,
        )

        try:
            from huggingface_hub import HfApi
        except ImportError as exc:
            raise ImportError(
                "huggingface_hub is required. Install: pip install huggingface-hub"
            ) from exc

        root = Path(dataset_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")

        fmt = (source_format or FormatDetector(str(root)).detect()).lower()
        if fmt == "coco":
            ds = seg_coco_to_hf(str(root))
        elif fmt == "yolo":
            ds = seg_yolo_to_hf(str(root))
        else:
            raise ValueError(f"Unsupported source format: {fmt}. Use 'coco' or 'yolo'.")

        logger.info(
            "Pushing %d splits to %s (%s)",
            len(ds),
            self.repo_id,
            ", ".join(f"{name}={len(d)}" for name, d in ds.items()),
        )
        ds.push_to_hub(self.repo_id, private=self.private, token=self.token)

        if write_card:
            card = generate_seg_dataset_card(ds, self.repo_id, **(card_metadata or {}))
            HfApi().upload_file(
                path_or_fileobj=card.encode(),
                path_in_repo="README.md",
                repo_id=self.repo_id,
                repo_type="dataset",
                commit_message=commit_message,
                token=self.token,
            )

        return {
            "repo_id": self.repo_id,
            "splits": {name: len(ds[name]) for name in ds},
            "class_names": _class_names_from_dataset(ds),
        }
