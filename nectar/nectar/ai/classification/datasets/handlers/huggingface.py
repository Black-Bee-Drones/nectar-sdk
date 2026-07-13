"""HuggingFace classification dataset download handler."""

import logging
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class HuggingFaceClsHandler(BaseDatasetHandler):
    """Download a HuggingFace image-classification dataset as ImageFolder."""

    def __init__(self, output_dir: str, token: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.token = token
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        repo_id: str,
        format_type: str = "imagefolder",
        split: Optional[str] = None,
        max_samples: Optional[int] = None,
        **kwargs,
    ) -> str:
        from datasets import DatasetDict, load_dataset

        from nectar.ai.classification.datasets.hf_converter import hf_to_imagefolder

        ds = load_dataset(
            repo_id,
            token=self.token,
            **{k: v for k, v in kwargs.items() if k != "format_type"},
        )

        if split is not None and isinstance(ds, DatasetDict) and split in ds:
            ds = DatasetDict({split: ds[split]})

        if max_samples is not None:
            if isinstance(ds, DatasetDict):
                ds = DatasetDict(
                    {
                        name: split_ds.select(range(min(max_samples, len(split_ds))))
                        for name, split_ds in ds.items()
                    }
                )
            else:
                ds = ds.select(range(min(max_samples, len(ds))))

        out = hf_to_imagefolder(ds, str(self.output_dir))
        logger.info("Downloaded %s → %s", repo_id, out)
        return out

    def convert(self, format: str = "imagefolder", **kwargs) -> str:
        return str(self.output_dir)
