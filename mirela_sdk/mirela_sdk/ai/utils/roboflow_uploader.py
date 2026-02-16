"""Roboflow image uploader for dataset management."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class RoboflowUploader:
    """
    Upload images to Roboflow for dataset annotation.

    Parameters
    ----------
    api_key : str
        Roboflow API key.
    workspace : str, optional
        Workspace name. Uses default if not provided.

    Attributes
    ----------
    SUPPORTED_FORMATS : Set[str]
        Supported image formats.

    Examples
    --------
    >>> uploader = RoboflowUploader(api_key="rf_xxx")
    >>> uploader.upload_directory(
    ...     directory_path="/path/to/images",
    ...     project_name="my-project",
    ...     batch_name="batch-1",
    ... )
    """

    SUPPORTED_FORMATS: Set[str] = {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tiff",
        ".webp",
        ".avif",
        ".heic",
    }

    def __init__(self, api_key: str, workspace: Optional[str] = None):
        try:
            from roboflow import Roboflow
        except ImportError as exc:
            raise ImportError("roboflow not installed. Install: pip install roboflow") from exc

        self.rf = Roboflow(api_key=api_key)
        self.workspace_name = workspace
        self._workspace = None
        self._project = None

    @property
    def workspace(self):
        """Get or initialize workspace."""
        if self._workspace is None:
            if self.workspace_name:
                self._workspace = self.rf.workspace(self.workspace_name)
            else:
                self._workspace = self.rf.workspace()
        return self._workspace

    def get_project(self, project_name: str):
        """
        Get Roboflow project.

        Parameters
        ----------
        project_name : str
            Project name.

        Returns
        -------
        Project
            Roboflow project instance.
        """
        self._project = self.workspace.project(project_name)
        return self._project

    def upload_directory(
        self,
        directory_path: str,
        project_name: str,
        batch_name: Optional[str] = None,
        recursive: bool = False,
        verbose: bool = True,
        max_workers: int = 10,
    ) -> Dict:
        """
        Upload images from directory to Roboflow.

        Parameters
        ----------
        directory_path : str
            Path to directory containing images.
        project_name : str
            Roboflow project name.
        batch_name : str, optional
            Batch name for uploaded images.
        recursive : bool, optional
            Upload from subdirectories. Defaults to False.
        verbose : bool, optional
            Print status. Defaults to True.
        max_workers : int, optional
            Parallel upload threads. Defaults to 10.

        Returns
        -------
        Dict
            Upload statistics with keys: total, success, failed, failed_files.
        """
        project = self.get_project(project_name)
        directory = Path(directory_path).expanduser().resolve()

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        failed_files: List[Tuple[str, str]] = []
        counter_lock = threading.Lock()
        upload_counter = {"value": 0}

        if recursive:
            image_files = self._find_images_recursive(directory)
        else:
            image_files = self._find_images(directory)

        stats["total"] = len(image_files)

        if verbose:
            print(f"\nUploading {stats['total']} images to '{project_name}'")
            if batch_name:
                print(f"Batch: {batch_name}")
            print(f"Source: {directory}")
            print(f"Workers: {max_workers}\n")

        def upload_image(image_path: Path) -> Tuple[bool, str, Optional[str]]:
            try:
                project.upload(image_path=str(image_path), batch_name=batch_name)

                with counter_lock:
                    stats["success"] += 1
                    upload_counter["value"] += 1
                    current = upload_counter["value"]

                    if verbose:
                        print(f"[{current}/{stats['total']}] ✓ {image_path.name}")

                return True, image_path.name, None

            except Exception as exc:
                with counter_lock:
                    stats["failed"] += 1
                    upload_counter["value"] += 1
                    current = upload_counter["value"]

                    if verbose:
                        print(f"[{current}/{stats['total']}] ✗ {image_path.name}: {exc}")

                return False, image_path.name, str(exc)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(upload_image, img): img for img in image_files}

            for future in as_completed(futures):
                success, filename, error = future.result()
                if not success and error:
                    failed_files.append((filename, error))

        if verbose:
            print(f"\n{'=' * 50}")
            print(
                f"Total: {stats['total']} | Success: {stats['success']} | Failed: {stats['failed']}"
            )
            print(f"{'=' * 50}\n")

            if failed_files:
                print("Failed:")
                for filename, error in failed_files:
                    print(f"  - {filename}: {error}")

        stats["failed_files"] = failed_files
        return stats

    def upload_multiple_directories(
        self,
        directories: List[Tuple[str, str]],
        project_name: str,
        verbose: bool = True,
        max_workers: int = 10,
    ) -> Dict:
        """
        Upload images from multiple directories with batch names.

        Parameters
        ----------
        directories : List[Tuple[str, str]]
            List of (directory_path, batch_name) tuples.
        project_name : str
            Roboflow project name.
        verbose : bool, optional
            Print status. Defaults to True.
        max_workers : int, optional
            Parallel upload threads. Defaults to 10.

        Returns
        -------
        Dict
            Overall statistics with keys: total_batches, total_images,
            total_success, total_failed, batches.

        Examples
        --------
        >>> uploader.upload_multiple_directories(
        ...     directories=[
        ...         ("/path/to/dir1", "batch-1"),
        ...         ("/path/to/dir2", "batch-2"),
        ...     ],
        ...     project_name="my-project",
        ... )
        """
        overall = {
            "total_batches": len(directories),
            "total_images": 0,
            "total_success": 0,
            "total_failed": 0,
            "batches": {},
        }

        for directory_path, batch_name in directories:
            if verbose:
                print(f"\n{'#' * 50}")
                print(f"Batch: {batch_name}")
                print(f"{'#' * 50}")

            stats = self.upload_directory(
                directory_path=directory_path,
                project_name=project_name,
                batch_name=batch_name,
                recursive=False,
                verbose=verbose,
                max_workers=max_workers,
            )

            overall["total_images"] += stats["total"]
            overall["total_success"] += stats["success"]
            overall["total_failed"] += stats["failed"]
            overall["batches"][batch_name] = stats

        if verbose:
            print(f"\n{'=' * 50}")
            print("OVERALL")
            print(f"Batches: {overall['total_batches']} | Images: {overall['total_images']}")
            print(f"Success: {overall['total_success']} | Failed: {overall['total_failed']}")
            print(f"{'=' * 50}\n")

        return overall

    def _find_images(self, directory: Path) -> List[Path]:
        """Find images in directory (non-recursive)."""
        images = []
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                images.append(file_path)
        return sorted(images)

    def _find_images_recursive(self, directory: Path) -> List[Path]:
        """Find images in directory and subdirectories."""
        images = []
        for root, _, files in os.walk(directory):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                    images.append(file_path)
        return sorted(images)


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Upload images to Roboflow")
    parser.add_argument("--api-key", required=True, help="Roboflow API key")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--directory", required=True, help="Image directory")
    parser.add_argument("--batch-name", help="Batch name")
    parser.add_argument("--recursive", action="store_true", help="Include subdirectories")
    parser.add_argument("--workspace", help="Workspace name")
    parser.add_argument("--max-workers", type=int, default=10, help="Parallel threads")

    args = parser.parse_args()

    uploader = RoboflowUploader(api_key=args.api_key, workspace=args.workspace)
    uploader.upload_directory(
        directory_path=args.directory,
        project_name=args.project,
        batch_name=args.batch_name,
        recursive=args.recursive,
        verbose=True,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
