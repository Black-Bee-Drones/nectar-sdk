"""CLI for uploading models to HuggingFace Hub."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

from nectar.ai.detection.utils.huggingface import HuggingFaceUploader


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Upload models to HuggingFace Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload single file
  python -m nectar.ai.detection.cli.upload \\
      --repo blackbeedrones/imav-2025-platform \\
      --files model.pt

  # Upload multiple files
  python -m nectar.ai.detection.cli.upload \\
      --repo blackbeedrones/imav-2025-platform \\
      --files model.pt model.onnx model.engine

  # Upload directory
  python -m nectar.ai.detection.cli.upload \\
      --repo blackbeedrones/imav-2025-platform \\
      --dir outputs/

  # With commit message
  python -m nectar.ai.detection.cli.upload \\
      --repo user/repo \\
      --files best.pt \\
      --message "Add trained model"
""",
    )

    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="HuggingFace repository ID (user/repo_name)",
    )
    parser.add_argument(
        "--files",
        type=str,
        nargs="+",
        help="Files to upload",
    )
    parser.add_argument(
        "--dir",
        type=str,
        help="Directory to upload (alternative to --files)",
    )
    parser.add_argument(
        "--message",
        type=str,
        default="Upload model",
        help="Commit message",
    )
    parser.add_argument(
        "--path-in-repo",
        type=str,
        default="",
        help="Target path in repository",
    )
    parser.add_argument(
        "--token",
        type=str,
        help="HuggingFace API token (uses HF_TOKEN env var if not provided)",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        default=True,
        help="Make repository private (default: True)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Make repository public",
    )
    parser.add_argument(
        "--ignore",
        type=str,
        nargs="*",
        help="Patterns to ignore when uploading directory",
    )

    return parser.parse_args()


def upload_files(
    repo_id: str,
    files: List[str],
    commit_message: str,
    path_in_repo: str = "",
    token: Optional[str] = None,
    private: bool = True,
) -> None:
    """
    Upload multiple files to HuggingFace Hub.

    Parameters
    ----------
    repo_id : str
        HuggingFace repository ID.
    files : List[str]
        List of file paths to upload.
    commit_message : str
        Commit message.
    path_in_repo : str
        Target path in repository.
    token : Optional[str]
        HuggingFace API token.
    private : bool
        Whether to make the repository private.
    """
    logger = logging.getLogger(__name__)

    uploader = HuggingFaceUploader(
        repo_id=repo_id,
        local_dir=".",
        token=token,
        private=private,
    )

    if not uploader.ensure_repo_exists():
        raise RuntimeError(f"Failed to create/access repository: {repo_id}")

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            continue

        target_path = f"{path_in_repo}/{path.name}" if path_in_repo else path.name
        logger.info(f"Uploading {path.name} -> {target_path}")

        uploader.upload_file(
            file_path=str(path),
            path_in_repo=target_path,
            commit_message=f"{commit_message}: {path.name}",
        )

    logger.info(f"Upload complete: https://huggingface.co/{repo_id}")


def upload_directory(
    repo_id: str,
    directory: str,
    commit_message: str,
    path_in_repo: Optional[str] = None,
    token: Optional[str] = None,
    private: bool = True,
    ignore_patterns: Optional[List[str]] = None,
) -> None:
    """
    Upload directory to HuggingFace Hub.

    Parameters
    ----------
    repo_id : str
        HuggingFace repository ID.
    directory : str
        Directory path to upload.
    commit_message : str
        Commit message.
    path_in_repo : Optional[str]
        Target path in repository.
    token : Optional[str]
        HuggingFace API token.
    private : bool
        Whether to make the repository private.
    ignore_patterns : Optional[List[str]]
        Patterns to ignore.
    """
    logger = logging.getLogger(__name__)

    uploader = HuggingFaceUploader(
        repo_id=repo_id,
        local_dir=directory,
        token=token,
        private=private,
    )

    logger.info(f"Uploading directory {directory} to {repo_id}")
    uploader.upload(
        commit_message=commit_message,
        ignore_patterns=ignore_patterns,
        path_in_repo=path_in_repo,
    )

    logger.info(f"Upload complete: https://huggingface.co/{repo_id}")


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    args = parse_args()

    if not args.files and not args.dir:
        logger.error("Either --files or --dir is required")
        sys.exit(1)

    if args.files and args.dir:
        logger.error("Cannot use both --files and --dir")
        sys.exit(1)

    private = not args.public

    try:
        if args.files:
            upload_files(
                repo_id=args.repo,
                files=args.files,
                commit_message=args.message,
                path_in_repo=args.path_in_repo,
                token=args.token,
                private=private,
            )
        else:
            upload_directory(
                repo_id=args.repo,
                directory=args.dir,
                commit_message=args.message,
                path_in_repo=args.path_in_repo,
                token=args.token,
                private=private,
                ignore_patterns=args.ignore,
            )

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
