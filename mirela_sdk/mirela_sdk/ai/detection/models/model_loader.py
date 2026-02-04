import os
from pathlib import Path
from typing import Optional


class ModelLoader:
    """Utility for loading models from local storage or Hugging Face."""

    @staticmethod
    def from_huggingface(
        repo_id: str,
        filename: Optional[str] = None,
        cache_dir: Optional[str] = None,
        token: Optional[str] = None,
    ) -> str:
        """
        Download and load model from Hugging Face.

        Supports two formats:
        1. Separate args: repo_id="blackbeedrones/cbr-25-base", filename="yolov11n.pt"
        2. Combined: repo_id="blackbeedrones/cbr-25-base:yolov11n.pt"

        Args:
            repo_id: Hugging Face repository ID (e.g., "user/repo" or "user/repo:file.pt")
            filename: Model filename (optional if included in repo_id)
            cache_dir: Custom cache directory (default: ~/.cache/huggingface/hub)
            token: HuggingFace API token for private repos (or set HF_TOKEN env var)

        Returns:
            Path to downloaded model file

        Example:
            # Public model
            path = ModelLoader.from_huggingface("blackbeedrones/cbr-25-base:yolov11n.pt")

            # Private model with token
            path = ModelLoader.from_huggingface("blackbeedrones/cbr-25-base:yolov11n.pt", token="hf_...")
        """
        try:
            from huggingface_hub import hf_hub_download
        except ImportError as exc:
            raise ImportError(
                "huggingface_hub not installed. Install with: pip install huggingface-hub"
            ) from exc

        # Parse repo_id if it contains filename
        if ":" in repo_id and filename is None:
            repo_id, filename = repo_id.split(":", 1)

        if filename is None:
            raise ValueError(
                "Filename must be provided either in repo_id (repo:file.pt) or as separate argument"
            )

        if token is None:
            token = os.environ.get("HF_TOKEN")

        print(f"Downloading {filename} from {repo_id}...")

        model_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=cache_dir,
            token=token,
        )

        print(f"Model cached at: {model_path}")
        return model_path

    @staticmethod
    def from_path(model_path: str) -> str:
        """
        Validate and return local model path.

        Args:
            model_path: Path to local model file

        Returns:
            Absolute path to model file

        Raises:
            FileNotFoundError: If model file doesn't exist
        """
        path = Path(model_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        return str(path)

    @staticmethod
    def load(
        model_source: str, cache_dir: Optional[str] = None, token: Optional[str] = None
    ) -> str:
        """
        Smart loader that handles both local paths and Hugging Face repos.

        Args:
            model_source: Either a local path or HuggingFace repo:file format
            cache_dir: Cache directory for HuggingFace downloads
            token: HuggingFace API token for private repos (or set HF_TOKEN env var)

        Returns:
            Path to model file

        Example:
            # Local file
            path = ModelLoader.load("/path/to/model.pt")

            # Public Hugging Face model
            path = ModelLoader.load("blackbeedrones/cbr-25-base:yolov11n.pt")

            # Private Hugging Face model
            path = ModelLoader.load("blackbeedrones/cbr-25-base:yolov11n.pt", token="hf_...")
        """
        if os.path.exists(model_source):
            return ModelLoader.from_path(model_source)

        if "/" in model_source:
            return ModelLoader.from_huggingface(
                model_source, cache_dir=cache_dir, token=token
            )

        raise ValueError(
            f"Invalid model source: {model_source}. "
            "Provide a local path or HuggingFace repo in format 'user/repo:file.pt'"
        )
