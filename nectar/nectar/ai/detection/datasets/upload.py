"""Dataset uploaders for Roboflow and HuggingFace."""

import json
import logging
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from nectar.ai.detection.utils.huggingface import HuggingFaceUploader

logger = logging.getLogger(__name__)


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

    def upload_dataset(
        self,
        dataset_path: str,
        project_name: str,
        annotation_format: Optional[str] = None,
        splits: Optional[List[str]] = None,
        batch_name: Optional[str] = None,
        tag_names: Optional[List[str]] = None,
        max_workers: int = 10,
        verbose: bool = True,
    ) -> Dict:
        """
        Upload an entire object detection dataset (images + annotations) to Roboflow.

        Auto-detects whether the dataset is in COCO or YOLO format using
        :class:`FormatDetector`, pairs each image with its annotation, and uploads
        them in parallel preserving the train/valid/test split assignment.

        Parameters
        ----------
        dataset_path : str
            Root directory of a COCO- or YOLO-format dataset.
        project_name : str
            Roboflow project name.
        annotation_format : str, optional
            ``"coco"`` or ``"yolo"``. Auto-detected when ``None``.
        splits : list of str, optional
            Subset of ``["train", "valid", "test"]`` to upload. Defaults to all available.
        batch_name : str, optional
            Batch name for uploaded images.
        tag_names : list of str, optional
            Tags applied to every uploaded image.
        max_workers : int, optional
            Parallel upload threads. Defaults to 10.
        verbose : bool, optional
            Print per-file progress. Defaults to True.

        Returns
        -------
        Dict
            Statistics: ``total``, ``success``, ``failed``, ``per_split``,
            ``failed_files``.
        """
        from nectar.ai.detection.datasets.format import FormatDetector

        root = Path(dataset_path).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")

        fmt = (annotation_format or FormatDetector(str(root)).detect()).lower()
        if fmt not in ("coco", "yolo"):
            raise ValueError(f"Unsupported annotation format: {fmt}. Use 'coco' or 'yolo'.")

        project = self.get_project(project_name)

        if fmt == "coco":
            tasks = self._collect_coco_tasks(root, splits)
            cleanup_dirs: List[Path] = [t["_tmp_dir"] for t in tasks if t.get("_tmp_dir")]
        else:
            tasks = self._collect_yolo_tasks(root, splits)
            cleanup_dirs = []

        try:
            return self._run_upload_tasks(
                project=project,
                tasks=tasks,
                batch_name=batch_name,
                tag_names=tag_names,
                max_workers=max_workers,
                verbose=verbose,
                project_name=project_name,
            )
        finally:
            for d in cleanup_dirs:
                try:
                    import shutil

                    shutil.rmtree(d, ignore_errors=True)
                except Exception:
                    pass

    def _collect_coco_tasks(self, root: Path, splits: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Build per-image upload tasks from a COCO-format dataset.

        Each image gets its own minimal COCO json (single-image, with shared
        categories) so that the Roboflow SDK's ``annotation_path`` per-image API
        can attach annotations correctly.
        """
        tasks: List[Dict[str, Any]] = []
        tmp_dir = Path(tempfile.mkdtemp(prefix="rf_coco_anns_"))

        for local_split in self._iter_splits(root, splits):
            split_dir = root / local_split
            ann_file = split_dir / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            with open(ann_file) as f:
                coco = json.load(f)

            categories = coco.get("categories", [])
            anns_by_image: Dict[int, List[Dict[str, Any]]] = {}
            for ann in coco.get("annotations", []):
                anns_by_image.setdefault(ann["image_id"], []).append(ann)

            split_tmp = tmp_dir / local_split
            split_tmp.mkdir(parents=True, exist_ok=True)

            for img_info in coco.get("images", []):
                img_path = split_dir / img_info["file_name"]
                if not img_path.exists():
                    continue

                per_image_coco = {
                    "info": coco.get("info", {}),
                    "licenses": coco.get("licenses", []),
                    "categories": categories,
                    "images": [img_info],
                    "annotations": anns_by_image.get(img_info["id"], []),
                }
                ann_out = split_tmp / f"{Path(img_info['file_name']).stem}.json"
                with open(ann_out, "w") as f:
                    json.dump(per_image_coco, f)

                tasks.append(
                    {
                        "image_path": str(img_path),
                        "annotation_path": str(ann_out),
                        "split": self._normalize_split(local_split),
                        "_tmp_dir": tmp_dir,
                    }
                )

        return tasks

    def _collect_yolo_tasks(self, root: Path, splits: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Build per-image upload tasks from a YOLO-format dataset."""
        tasks: List[Dict[str, Any]] = []

        for local_split in self._iter_splits(root, splits):
            images_dir = root / local_split / "images"
            labels_dir = root / local_split / "labels"
            if not images_dir.exists():
                continue

            for img_path in sorted(images_dir.iterdir()):
                if img_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                    continue

                label_path = labels_dir / f"{img_path.stem}.txt"
                tasks.append(
                    {
                        "image_path": str(img_path),
                        "annotation_path": str(label_path) if label_path.exists() else None,
                        "split": self._normalize_split(local_split),
                    }
                )

        return tasks

    def _iter_splits(self, root: Path, splits: Optional[List[str]]) -> List[str]:
        """Return the local split names to process, filtered by ``splits`` if given."""
        candidates = ["train", "valid", "val", "test"]
        present = [s for s in candidates if (root / s).exists()]
        if splits:
            wanted = {s.lower() for s in splits}
            present = [s for s in present if s in wanted or self._normalize_split(s) in wanted]
        return present

    @staticmethod
    def _normalize_split(name: str) -> str:
        """Normalize split name to Roboflow's expected values (train/valid/test)."""
        return "valid" if name in ("val", "validation") else name

    def _run_upload_tasks(
        self,
        project,
        tasks: List[Dict[str, Any]],
        batch_name: Optional[str],
        tag_names: Optional[List[str]],
        max_workers: int,
        verbose: bool,
        project_name: str,
    ) -> Dict:
        """Execute ``project.upload(image_path, annotation_path, split, ...)`` tasks in parallel."""
        stats = {
            "total": len(tasks),
            "success": 0,
            "failed": 0,
            "per_split": {"train": 0, "valid": 0, "test": 0},
        }
        failed_files: List[Tuple[str, str]] = []
        counter_lock = threading.Lock()
        counter = {"value": 0}

        if verbose:
            print(f"\nUploading {stats['total']} image+annotation pairs to '{project_name}'")
            if batch_name:
                print(f"Batch: {batch_name}")
            print(f"Workers: {max_workers}\n")

        def upload_one(task: Dict[str, Any]) -> Tuple[bool, str, Optional[str], str]:
            img_name = Path(task["image_path"]).name
            split = task["split"]
            try:
                kwargs: Dict[str, Any] = {
                    "image_path": task["image_path"],
                    "split": split,
                }
                if task.get("annotation_path"):
                    kwargs["annotation_path"] = task["annotation_path"]
                if batch_name:
                    kwargs["batch_name"] = batch_name
                if tag_names:
                    kwargs["tag_names"] = tag_names

                project.upload(**kwargs)

                with counter_lock:
                    stats["success"] += 1
                    stats["per_split"][split] = stats["per_split"].get(split, 0) + 1
                    counter["value"] += 1
                    if verbose:
                        print(f"[{counter['value']}/{stats['total']}] OK   {split}/{img_name}")
                return True, img_name, None, split

            except Exception as exc:
                with counter_lock:
                    stats["failed"] += 1
                    counter["value"] += 1
                    if verbose:
                        print(
                            f"[{counter['value']}/{stats['total']}] FAIL {split}/{img_name}: {exc}"
                        )
                return False, img_name, str(exc), split

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(upload_one, t) for t in tasks]
            for fut in as_completed(futures):
                ok, name, err, _ = fut.result()
                if not ok and err:
                    failed_files.append((name, err))

        if verbose:
            print(f"\n{'=' * 50}")
            print(
                f"Total: {stats['total']} | Success: {stats['success']} | Failed: {stats['failed']}"
            )
            print(f"Per split: {stats['per_split']}")
            print(f"{'=' * 50}\n")

        stats["failed_files"] = failed_files
        return stats

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


class HuggingFaceDatasetUploader:
    """
    Upload datasets to HuggingFace Hub.

    Wraps HuggingFaceUploader with dataset-specific defaults and convenience methods.

    Parameters
    ----------
    repo_id : str
        HuggingFace Hub repository ID (username/repo_name).
    token : Optional[str], optional
        HuggingFace API token. Uses HF_TOKEN env var if not provided.
    private : bool, optional
        Make repository private. Defaults to True.

    Examples
    --------
    >>> uploader = HuggingFaceDatasetUploader(
    ...     repo_id="user/my-dataset",
    ...     private=True,
    ... )
    >>> uploader.upload_dataset(
    ...     dataset_path="datasets/my_dataset",
    ...     commit_message="Upload dataset"
    ... )
    """

    def __init__(
        self,
        repo_id: str,
        token: Optional[str] = None,
        private: bool = True,
    ):
        """Initialize uploader."""
        self.repo_id = repo_id
        self.token = token
        self.private = private
        self._uploader = None

    def _get_uploader(self, dataset_path: str) -> HuggingFaceUploader:
        """Get or create HuggingFaceUploader instance."""
        if self._uploader is None:
            self._uploader = HuggingFaceUploader(
                repo_id=self.repo_id,
                local_dir=dataset_path,
                token=self.token,
                repo_type="dataset",
                private=self.private,
            )
        else:
            self._uploader.local_dir = Path(dataset_path)
        return self._uploader

    def ensure_repo_exists(self) -> bool:
        """
        Ensure repository exists, creating if needed.

        Returns
        -------
        bool
            True if repository exists or was created.
        """
        uploader = HuggingFaceUploader(
            repo_id=self.repo_id,
            local_dir=".",
            token=self.token,
            repo_type="dataset",
            private=self.private,
        )
        return uploader.ensure_repo_exists()

    def upload_dataset(
        self,
        dataset_path: str,
        commit_message: str = "Upload dataset",
        ignore_patterns: Optional[List[str]] = None,
    ) -> Dict:
        """
        Upload dataset directory to HuggingFace Hub as raw files.

        Note
        ----
        This uploads files as-is. The Hub dataset viewer will not render
        bounding boxes for raw COCO/YOLO files. Use :meth:`upload_native`
        instead to enable visualization.

        Parameters
        ----------
        dataset_path : str
            Path to dataset directory.
        commit_message : str, optional
            Commit message. Defaults to "Upload dataset".
        ignore_patterns : Optional[List[str]], optional
            Patterns to ignore (e.g., ["*.log", "__pycache__"]).

        Returns
        -------
        Dict
            Upload response.
        """
        dataset_dir = Path(dataset_path).expanduser().resolve()

        if not dataset_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {dataset_path}")

        default_ignore = [
            "*.pyc",
            "__pycache__",
            "*.log",
            ".git",
            ".gitignore",
            ".DS_Store",
            "*.tmp",
            "*.swp",
            ".vscode",
            ".idea",
        ]

        ignore = (ignore_patterns or []) + default_ignore

        uploader = self._get_uploader(str(dataset_dir))
        logger.info(f"Uploading dataset to HuggingFace Hub: {self.repo_id}")

        try:
            response = uploader.upload(
                commit_message=commit_message,
                ignore_patterns=ignore,
            )
            logger.info(f"Successfully uploaded dataset to {self.repo_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to upload dataset: {e}")
            raise

    def upload_native(
        self,
        dataset_path: str,
        source_format: Optional[str] = None,
        commit_message: str = "Upload dataset",
        card_metadata: Optional[Dict[str, Any]] = None,
        write_card: bool = True,
    ) -> Dict[str, Any]:
        """
        Convert a local COCO/YOLO dataset to HuggingFace-native Parquet and push.

        This produces a dataset compatible with the Hub viewer's bounding box
        visualization (``image`` column + ``objects.{bbox,category}`` schema).

        Parameters
        ----------
        dataset_path : str
            Local dataset directory in COCO or YOLO format.
        source_format : str, optional
            ``"coco"`` or ``"yolo"``. Auto-detected when ``None``.
        commit_message : str, optional
            Commit message for the README upload (Parquet shards use the
            ``datasets`` library's default commit message).
        card_metadata : dict, optional
            Forwarded to :func:`generate_dataset_card`. Keys: ``title``,
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
        from nectar.ai.detection.datasets.hf_converter import (
            coco_to_hf,
            generate_dataset_card,
            yolo_to_hf,
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
            ds = coco_to_hf(str(root))
        elif fmt == "yolo":
            ds = yolo_to_hf(str(root))
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
            card = generate_dataset_card(ds, self.repo_id, **(card_metadata or {}))
            HfApi().upload_file(
                path_or_fileobj=card.encode(),
                path_in_repo="README.md",
                repo_id=self.repo_id,
                repo_type="dataset",
                commit_message=commit_message,
                token=self.token,
            )

        from nectar.ai.detection.datasets.hf_converter import _class_names_from_dataset

        return {
            "repo_id": self.repo_id,
            "splits": {name: len(ds[name]) for name in ds},
            "class_names": _class_names_from_dataset(ds),
        }


if __name__ == "__main__":
    main()
