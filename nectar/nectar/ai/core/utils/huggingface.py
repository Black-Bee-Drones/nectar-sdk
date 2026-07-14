"""
HuggingFace Hub utilities.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from huggingface_hub import HfApi, create_repo
except ImportError:
    HfApi = None
    create_repo = None


logger = logging.getLogger(__name__)


class HuggingFaceUploader:
    """
    Handles uploading models and artifacts to HuggingFace Hub.

    Parameters
    ----------
    repo_id : str
        HuggingFace Hub repository ID (username/repo_name).
    local_dir : str
        Local directory containing files to upload.
    token : Optional[str], optional
        HuggingFace API token. Uses HF_TOKEN env var if not provided.
    repo_type : str, optional
        Repository type ('model', 'dataset', 'space'). Defaults to 'model'.
    private : bool, optional
        Make repository private. Defaults to True.

    Examples
    --------
    >>> uploader = HuggingFaceUploader(
    ...     repo_id="user/my-model",
    ...     local_dir="outputs/",
    ...     private=True,
    ... )
    >>> uploader.ensure_repo_exists()
    >>> uploader.upload(commit_message="Training checkpoint")
    """

    def __init__(
        self,
        repo_id: str,
        local_dir: str,
        token: Optional[str] = None,
        repo_type: str = "model",
        private: bool = True,
    ):
        """Initialize uploader."""
        if HfApi is None:
            raise ImportError(
                "huggingface_hub is required. Install with: pip install huggingface-hub"
            )

        self.repo_id = repo_id
        self.local_dir = Path(local_dir)
        self.repo_type = repo_type
        self.private = private
        self.token = token or os.environ.get("HF_TOKEN")
        self.api = HfApi()
        self._repo_exists = False

        if not self.token:
            logger.warning("No HuggingFace token provided.")

    def ensure_repo_exists(self) -> bool:
        """
        Ensure repository exists, creating if needed.

        Returns
        -------
        bool
            True if repository exists or was created.
        """
        if self._repo_exists:
            return True

        try:
            self.api.repo_info(
                repo_id=self.repo_id,
                repo_type=self.repo_type,
                token=self.token,
            )
            self._repo_exists = True
            return True
        except Exception:
            try:
                logger.info(f"Creating repository {self.repo_id}")
                create_repo(
                    repo_id=self.repo_id,
                    repo_type=self.repo_type,
                    token=self.token,
                    private=self.private,
                    exist_ok=True,
                )
                self._repo_exists = True
                return True
            except Exception as e:
                logger.error(f"Failed to create repository: {e}")
                return False

    def upload(
        self,
        commit_message: str,
        ignore_patterns: Optional[List[str]] = None,
        path_in_repo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload directory contents to HuggingFace Hub.

        Parameters
        ----------
        commit_message : str
            Commit message.
        ignore_patterns : Optional[List[str]], optional
            Patterns to ignore (e.g., ["*.log"]).
        path_in_repo : Optional[str], optional
            Target path in repository.

        Returns
        -------
        Dict[str, Any]
            Upload response.
        """
        logger.info(f"Uploading to HuggingFace Hub: {self.repo_id}")

        if not self.local_dir.exists():
            raise FileNotFoundError(f"Directory not found: {self.local_dir}")

        if not self.ensure_repo_exists():
            raise RuntimeError(f"Failed to ensure repository: {self.repo_id}")

        try:
            response = self.api.upload_folder(
                folder_path=str(self.local_dir),
                repo_id=self.repo_id,
                repo_type=self.repo_type,
                commit_message=commit_message,
                ignore_patterns=ignore_patterns or [],
                token=self.token,
                path_in_repo=path_in_repo,
            )
            logger.info(f"Successfully uploaded to {self.repo_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to upload: {e}")
            raise

    def upload_file(
        self,
        file_path: str,
        path_in_repo: str,
        commit_message: str,
    ) -> Dict[str, Any]:
        """
        Upload a single file.

        Parameters
        ----------
        file_path : str
            Local file path.
        path_in_repo : str
            Target path in repository.
        commit_message : str
            Commit message.

        Returns
        -------
        Dict[str, Any]
            Upload response.
        """
        logger.info(f"Uploading file to {self.repo_id}/{path_in_repo}")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.ensure_repo_exists():
            raise RuntimeError(f"Failed to ensure repository: {self.repo_id}")

        try:
            response = self.api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=path_in_repo,
                repo_id=self.repo_id,
                repo_type=self.repo_type,
                commit_message=commit_message,
                token=self.token,
            )
            logger.info("Successfully uploaded file")
            return response
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise
