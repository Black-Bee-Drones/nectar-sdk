"""
Shared training callbacks for HuggingFace Hub uploads.

Provides framework-specific callback factories that wrap HuggingFaceUploader
for automatic output directory sync during training.

All three frameworks share the same upload behavior: sync the full output
directory to HuggingFace Hub between epochs and at training end, using
HF_SYNC_IGNORE_PATTERNS to exclude datasets, temp files, etc.

Supported frameworks:
- Ultralytics (YOLO): via model.add_callback()
- RF-DETR (PyTorch Lightning): via pytorch_lightning.Callback
- Transformers (HuggingFace): via transformers.TrainerCallback
"""

import gc
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

HF_SYNC_IGNORE_PATTERNS: List[str] = [
    "datasets/**",
    "*.tmp",
    "*.bak",
    "__pycache__/**",
    "*.pyc",
    ".ipynb_checkpoints/**",
    "*.git*",
]


def _is_main_process() -> bool:
    """Check if current process is the main (rank 0) process."""
    try:
        import torch.distributed as dist

        if dist.is_available() and dist.is_initialized():
            return dist.get_rank() == 0
    except Exception:
        pass
    return int(os.environ.get("RANK", "0")) == 0


def setup_ultralytics_hf_callbacks(
    model,
    repo_id: str,
    output_dir: Path,
    log: Optional[logging.Logger] = None,
) -> None:
    """
    Register HuggingFace upload callbacks on an Ultralytics YOLO model.

    Syncs the full output directory after each epoch and at training end.

    Parameters
    ----------
    model : ultralytics.YOLO
        The YOLO model instance (must support add_callback).
    repo_id : str
        HuggingFace Hub repository ID (e.g. 'org/model-name').
    output_dir : Path
        Local training output directory.
    log : logging.Logger, optional
        Logger instance. Uses module logger if not provided.
    """
    from nectar.ai.core.utils.huggingface import HuggingFaceUploader

    log = log or logger

    uploader = HuggingFaceUploader(
        repo_id=repo_id,
        local_dir=str(output_dir),
        private=True,
    )

    def on_train_epoch_end(trainer):
        if not _is_main_process():
            return
        try:
            uploader.local_dir = Path(trainer.save_dir)
            uploader.upload(
                commit_message=f"Sync epoch {trainer.epoch}",
                ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
            )
        except Exception as e:
            log.error("HF epoch upload failed: %s", e)

    def on_train_end(trainer):
        if not _is_main_process():
            return
        try:
            uploader.local_dir = Path(trainer.save_dir)
            uploader.upload(
                commit_message="Training completed",
                ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
            )
        except Exception as e:
            log.error("HF final upload failed: %s", e)

    model.add_callback("on_train_epoch_end", on_train_epoch_end)
    model.add_callback("on_train_end", on_train_end)


def setup_ultralytics_gc_callback(model, accumulation_steps: int = 1) -> None:
    """
    Register a garbage-collection callback on an Ultralytics YOLO model.

    Clears Python GC and CUDA cache every `accumulation_steps` batches.
    """
    try:
        import torch
    except ImportError:
        torch = None

    def on_batch_end(trainer):
        ni = getattr(
            trainer,
            "ni",
            getattr(trainer, "epoch", 0) * getattr(trainer, "nb", 0),
        )
        if (ni + 1) % accumulation_steps == 0:
            gc.collect()
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()

    model.add_callback("on_train_batch_end", on_batch_end)


def get_hf_upload_ptl_callback(
    repo_id: str,
    output_dir: Path,
    log: Optional[logging.Logger] = None,
):
    """
    Create a PyTorch Lightning callback for HuggingFace Hub uploads.

    Syncs the output directory after each validation epoch and at
    training end. Used by RF-DETR models.

    Parameters
    ----------
    repo_id : str
        HuggingFace Hub repository ID.
    output_dir : Path
        Local training output directory.
    log : logging.Logger, optional
        Logger instance.

    Returns
    -------
    pytorch_lightning.Callback
        The configured callback instance.
    """
    from pytorch_lightning import Callback

    from nectar.ai.core.utils.huggingface import HuggingFaceUploader

    log = log or logger

    class _HFUploadCallback(Callback):
        """Syncs training outputs to HuggingFace Hub between epochs."""

        def __init__(self):
            super().__init__()
            self._uploader = HuggingFaceUploader(
                repo_id=repo_id,
                local_dir=str(output_dir),
                private=True,
            )

        def on_validation_epoch_end(self, trainer, pl_module):
            if trainer.global_rank != 0:
                return
            try:
                self._uploader.local_dir = output_dir
                self._uploader.upload(
                    commit_message=f"Sync epoch {trainer.current_epoch}",
                    ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                )
            except Exception as e:
                log.error("HF epoch upload failed: %s", e)

        def on_fit_end(self, trainer, pl_module):
            if trainer.global_rank != 0:
                return
            try:
                self._uploader.local_dir = output_dir
                self._uploader.upload(
                    commit_message="Training completed",
                    ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                )
            except Exception as e:
                log.error("HF final upload failed: %s", e)

    return _HFUploadCallback()


def get_hf_upload_transformers_callback(
    repo_id: str,
    output_dir: Path,
    log: Optional[logging.Logger] = None,
):
    """
    Create a HuggingFace Transformers TrainerCallback for Hub uploads.

    Syncs the output directory after each epoch and at training end.
    Used by Transformers detection and segmentation models.

    Parameters
    ----------
    repo_id : str
        HuggingFace Hub repository ID.
    output_dir : Path
        Local training output directory.
    log : logging.Logger, optional
        Logger instance.

    Returns
    -------
    transformers.TrainerCallback
        The configured callback instance.
    """
    from transformers import TrainerCallback

    from nectar.ai.core.utils.huggingface import HuggingFaceUploader

    log = log or logger

    class _HFUploadCallback(TrainerCallback):
        """Syncs training outputs to HuggingFace Hub between epochs."""

        def __init__(self):
            self._uploader = HuggingFaceUploader(
                repo_id=repo_id,
                local_dir=str(output_dir),
                private=True,
            )

        def on_epoch_end(self, args, state, control, **kwargs):
            if not state.is_world_process_zero:
                return
            try:
                self._uploader.upload(
                    commit_message=f"Sync epoch {int(state.epoch)}",
                    ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                )
            except Exception as e:
                log.error("HF epoch upload failed: %s", e)

        def on_train_end(self, args, state, control, **kwargs):
            if not state.is_world_process_zero:
                return
            try:
                self._uploader.upload(
                    commit_message="Training completed",
                    ignore_patterns=HF_SYNC_IGNORE_PATTERNS,
                )
            except Exception as e:
                log.error("HF final upload failed: %s", e)

    return _HFUploadCallback()
