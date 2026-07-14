"""Roboflow classification dataset download handler."""

import logging
from pathlib import Path
from typing import Optional

from nectar.ai.detection.datasets.handlers.base import BaseDatasetHandler

logger = logging.getLogger(__name__)


class RoboflowClsHandler(BaseDatasetHandler):
    """Download a Roboflow classification project as ImageFolder / folder structure."""

    def __init__(self, output_dir: str, api_key: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.api_key = api_key
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        workspace: str,
        project: str,
        version: int = 1,
        format_type: str = "folder",
        **kwargs,
    ) -> str:
        try:
            from roboflow import Roboflow
        except ImportError as e:
            raise ImportError("roboflow is required. Install: pip install roboflow") from e

        if not self.api_key:
            raise ValueError("Roboflow API key required")

        rf = Roboflow(api_key=self.api_key)
        project_obj = rf.workspace(workspace).project(project)
        version_obj = project_obj.version(version)
        # folder format is ImageFolder-compatible for classification
        dataset = version_obj.download(format_type, location=str(self.output_dir))
        location = getattr(dataset, "location", str(self.output_dir))
        logger.info("Downloaded Roboflow %s/%s v%s → %s", workspace, project, version, location)
        return str(location)

    def convert(self, format: str = "imagefolder", **kwargs) -> str:
        return str(self.output_dir)
