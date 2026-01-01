import os
from pathlib import Path
from typing import Optional, List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class RoboflowUploader:

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
        """
        Initialize Roboflow uploader.

        Args:
            api_key: Your Roboflow API key
            workspace: Workspace name (optional, will use default if not provided)
        """
        try:
            from roboflow import Roboflow
        except ImportError as exc:
            raise ImportError(
                "roboflow not installed. Install with: pip install roboflow"
            ) from exc

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

        Args:
            project_name: Name of the project

        Returns:
            Roboflow project instance
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
    ) -> dict:
        """
        Upload all images from a directory to Roboflow project.

        Args:
            directory_path: Path to directory containing images
            project_name: Name of the Roboflow project
            batch_name: Optional batch name for uploaded images
            recursive: If True, recursively upload from subdirectories
            verbose: Print upload status
            max_workers: Number of parallel upload threads (default 10)

        Returns:
            Dictionary with upload statistics
        """
        project = self.get_project(project_name)
        directory = Path(directory_path).expanduser().resolve()

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        failed_files = []
        counter_lock = threading.Lock()
        upload_counter = {"value": 0}

        # Get all image files
        if recursive:
            image_files = self._find_images_recursive(directory)
        else:
            image_files = self._find_images(directory)

        stats["total"] = len(image_files)

        if verbose:
            print(f"\nUploading {stats['total']} images to project '{project_name}'")
            if batch_name:
                print(f"Batch name: {batch_name}")
            print(f"Source: {directory}")
            print(f"Parallel workers: {max_workers}\n")

        def upload_image(image_path):

            try:
                project.upload(image_path=str(image_path), batch_name=batch_name)

                with counter_lock:
                    stats["success"] += 1
                    upload_counter["value"] += 1
                    current_count = upload_counter["value"]

                    if verbose:
                        print(
                            f"[{current_count}/{stats['total']}] ✓ Uploaded: {image_path.name}"
                        )

                return True, image_path.name, None

            except Exception as exc:
                with counter_lock:
                    stats["failed"] += 1
                    upload_counter["value"] += 1
                    current_count = upload_counter["value"]

                    if verbose:
                        print(
                            f"[{current_count}/{stats['total']}] ✗ Failed: {image_path.name} - {exc}"
                        )

                return False, image_path.name, str(exc)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(upload_image, img_path): img_path
                for img_path in image_files
            }

            for future in as_completed(futures):
                success, filename, error = future.result()
                if not success and error:
                    failed_files.append((filename, error))

        # Print summary
        if verbose:
            print(f"\n{'='*60}")
            print("Upload Summary:")
            print(f"  Total files: {stats['total']}")
            print(f"  Successful: {stats['success']}")
            print(f"  Failed: {stats['failed']}")
            print(f"{'='*60}\n")

            if failed_files:
                print("Failed uploads:")
                for filename, error in failed_files:
                    print(f"  - {filename}: {error}")

        stats["failed_files"] = failed_files
        return stats

    def upload_multiple_directories(
        self,
        directories: List[tuple],
        project_name: str,
        verbose: bool = True,
        max_workers: int = 10,
    ) -> dict:
        """
        Upload images from multiple directories with different batch names.

        Args:
            directories: List of tuples (directory_path, batch_name)
            project_name: Name of the Roboflow project
            verbose: Print upload status
            max_workers: Number of parallel upload threads (default 10)

        Returns:
            Dictionary with overall upload statistics

        Example:
            uploader.upload_multiple_directories(
                directories=[
                    ("/path/to/dir1", "batch-1"),
                    ("/path/to/dir2", "batch-2"),
                ],
                project_name="my-project"
            )
        """
        overall_stats = {
            "total_batches": len(directories),
            "total_images": 0,
            "total_success": 0,
            "total_failed": 0,
            "batches": {},
        }

        for directory_path, batch_name in directories:
            if verbose:
                print(f"\n{'#'*60}")
                print(f"Processing batch: {batch_name}")
                print(f"{'#'*60}")

            stats = self.upload_directory(
                directory_path=directory_path,
                project_name=project_name,
                batch_name=batch_name,
                recursive=False,
                verbose=verbose,
                max_workers=max_workers,
            )

            overall_stats["total_images"] += stats["total"]
            overall_stats["total_success"] += stats["success"]
            overall_stats["total_failed"] += stats["failed"]
            overall_stats["batches"][batch_name] = stats

        if verbose:
            print(f"\n{'='*60}")
            print("OVERALL SUMMARY")
            print(f"{'='*60}")
            print(f"Total batches: {overall_stats['total_batches']}")
            print(f"Total images: {overall_stats['total_images']}")
            print(f"Total successful: {overall_stats['total_success']}")
            print(f"Total failed: {overall_stats['total_failed']}")
            print(f"{'='*60}\n")

        return overall_stats

    def _find_images(self, directory: Path) -> List[Path]:
        """Find all images in directory (non-recursive)."""
        images = []
        for file_path in directory.iterdir():
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_FORMATS
            ):
                images.append(file_path)
        return sorted(images)

    def _find_images_recursive(self, directory: Path) -> List[Path]:
        """Find all images in directory and subdirectories."""
        images = []
        for root, _, files in os.walk(directory):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                    images.append(file_path)
        return sorted(images)


def main():
    """Example usage script."""
    import argparse

    parser = argparse.ArgumentParser(description="Upload images to Roboflow project")
    parser.add_argument(
        "--api-key",
        required=True,
        help="Roboflow API key",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Roboflow project name",
    )
    parser.add_argument(
        "--directory",
        required=True,
        help="Directory containing images",
    )
    parser.add_argument(
        "--batch-name",
        help="Optional batch name for uploads",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively upload from subdirectories",
    )
    parser.add_argument(
        "--workspace",
        help="Workspace name (optional)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Number of parallel upload threads (default: 10)",
    )

    args = parser.parse_args()

    uploader = RoboflowUploader(
        api_key=args.api_key,
        workspace=args.workspace,
    )

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
