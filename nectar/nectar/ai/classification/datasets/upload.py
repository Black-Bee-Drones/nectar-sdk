"""Upload classification datasets to HuggingFace Hub or Roboflow."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HuggingFaceClsDatasetUploader:
    """Upload an ImageFolder classification dataset to the Hub as Parquet."""

    def __init__(self, repo_id: str, private: bool = False, token: Optional[str] = None):
        self.repo_id = repo_id
        self.private = private
        self.token = token

    def upload_native(
        self,
        dataset_path: str,
        commit_message: str = "Upload classification dataset",
        card_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert ImageFolder → DatasetDict and push to Hub."""
        from huggingface_hub import HfApi

        from nectar.ai.classification.datasets.hf_converter import (
            generate_cls_dataset_card,
            imagefolder_to_hf,
        )

        ds = imagefolder_to_hf(dataset_path)
        ds.push_to_hub(self.repo_id, private=self.private, token=self.token)

        card = generate_cls_dataset_card(
            ds,
            self.repo_id,
            title=(card_metadata or {}).get("title"),
            description=(card_metadata or {}).get("description"),
            license=(card_metadata or {}).get("license", "apache-2.0"),
            tags=(card_metadata or {}).get("tags"),
        )
        api = HfApi(token=self.token)
        api.upload_file(
            path_or_fileobj=card.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=self.repo_id,
            repo_type="dataset",
            commit_message=commit_message,
        )

        class_names = []
        first = next(iter(ds.values()))
        feat = first.features.get("label")
        if feat is not None and hasattr(feat, "names"):
            class_names = list(feat.names)

        return {
            "repo_id": self.repo_id,
            "splits": {k: len(v) for k, v in ds.items()},
            "class_names": class_names,
        }


class RoboflowClsUploader:
    """Upload images to a Roboflow classification project."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def upload_dataset(
        self,
        dataset_path: str,
        project_name: str,
        workspace: Optional[str] = None,
        splits: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Upload ImageFolder images to Roboflow (classification projects)."""
        try:
            from roboflow import Roboflow
        except ImportError as e:
            raise ImportError("roboflow is required. Install: pip install roboflow") from e

        rf = Roboflow(api_key=self.api_key)
        if workspace:
            ws = rf.workspace(workspace)
        else:
            ws = rf.workspace()

        project = ws.project(project_name)
        root = Path(dataset_path)
        splits = splits or ["train", "val", "valid", "test"]
        stats = {"uploaded": 0, "failed": 0, "per_split": {}}

        for split in splits:
            split_dir = root / split
            if not split_dir.is_dir():
                continue
            count = 0
            for img_path in split_dir.rglob("*"):
                if not img_path.is_file():
                    continue
                if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                    continue
                try:
                    project.upload(str(img_path), split=split if split != "valid" else "valid")
                    count += 1
                    stats["uploaded"] += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to upload %s: %s", img_path, exc)
                    stats["failed"] += 1
            stats["per_split"][split] = count

        return stats
