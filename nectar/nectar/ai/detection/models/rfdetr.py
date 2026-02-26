"""RF-DETR model implementation."""

import gc
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

try:
    import torch
except ImportError:
    torch = None

try:
    import supervision as sv
except ImportError:
    sv = None

try:
    from rfdetr import RFDETRBase, RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
    from rfdetr.main import download_pretrain_weights
    from rfdetr.util.coco_classes import COCO_CLASSES

    RFDETR_AVAILABLE = True
    RFDETR_MODELS = {
        "rfdetr-nano": RFDETRNano,
        "rfdetr-small": RFDETRSmall,
        "rfdetr-base": RFDETRBase,
        "rfdetr-medium": RFDETRMedium,
        "rfdetr-large": RFDETRLarge,
    }
    _DEFAULT_PRETRAIN_WEIGHTS = {
        "rfdetr-nano": "rf-detr-nano.pth",
        "rfdetr-small": "rf-detr-small.pth",
        "rfdetr-base": "rf-detr-base.pth",
        "rfdetr-medium": "rf-detr-medium.pth",
        "rfdetr-large": "rf-detr-large-2026.pth",
    }
except ImportError as _rfdetr_err:
    RFDETR_AVAILABLE = False
    COCO_CLASSES = []
    RFDETR_MODELS = {}
    _DEFAULT_PRETRAIN_WEIGHTS = {}
    logging.getLogger(__name__).debug("rfdetr import failed: %s", _rfdetr_err)

from PIL import Image

from nectar.ai.detection.core.base import BaseDetectionModel
from nectar.ai.detection.core.configs import TrainingConfig
from nectar.ai.detection.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.detection.core.types import DetectionInput, Prediction
from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector
from nectar.ai.detection.datasets.subset import SubsetCreator

logger = logging.getLogger(__name__)


class RFDETRModel(BaseDetectionModel):
    """
    RF-DETR model wrapper.

    Parameters
    ----------
    model_name : str
        Model name ('rfdetr-base') or checkpoint path.
    rfdetr_size : str, optional
        Explicit model size (nano, small, base, medium, large).
    resolution : int, optional
        Image resolution. Defaults to model's default.
    from_scratch : bool, optional
        Train from scratch. Defaults to False.

    Examples
    --------
    >>> model = RFDETRModel("rfdetr-base", resolution=560)
    >>> model.load_model()
    >>> result = model.detect(image)
    """

    def __init__(
        self,
        model_name: str = "rfdetr-base",
        rfdetr_size: Optional[str] = None,
        resolution: Optional[int] = None,
        from_scratch: bool = False,
    ):
        super().__init__(model_name, "rfdetr")

        if not RFDETR_AVAILABLE:
            raise ImportError("rfdetr is required. Install: pip install rfdetr")

        self.model_path = model_name if Path(model_name).exists() else None

        # Determine model class
        if rfdetr_size:
            self.base_model_name = f"rfdetr-{rfdetr_size.lower()}"
        elif self.model_path:
            self.base_model_name = self._infer_model_size(self.model_path)
        else:
            self.base_model_name = model_name

        self.model_class = RFDETR_MODELS.get(self.base_model_name)
        if self.model_class is None:
            raise ValueError(
                f"Unsupported RF-DETR model: '{self.base_model_name}'. "
                f"Available: {list(RFDETR_MODELS.keys())}"
            )

        self.model = None
        self.rfdetr_wrapper = None
        self.from_scratch = from_scratch
        self.resolution = resolution
        self.class_names = {i: name for i, name in enumerate(COCO_CLASSES)}

    def _infer_model_size(self, path: str) -> str:
        """Infer model size from checkpoint path."""
        path = Path(path)
        candidates = [str(path.name).lower()] + [str(p.name).lower() for p in path.parents]
        for candidate in candidates:
            for size in RFDETR_MODELS.keys():
                size_short = size.replace("rfdetr-", "")
                if size_short in candidate:
                    return size
        return "rfdetr-base"

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load RF-DETR model."""
        checkpoint_path = model_path or self.model_path

        model_kwargs = {}

        if len(self.class_names) != len(COCO_CLASSES):
            model_kwargs["num_classes"] = len(self.class_names)
            self.logger.info(f"Initializing with {len(self.class_names)} classes")

        if self.resolution:
            model_kwargs["resolution"] = self.resolution
            self.logger.info(f"Using resolution: {self.resolution}")

        if torch and torch.backends.mps.is_available():
            model_kwargs["device"] = "mps"

        if checkpoint_path and Path(checkpoint_path).exists():
            self.logger.info(f"Loading RF-DETR model from checkpoint: {checkpoint_path}")
            self.rfdetr_wrapper = self.model_class(pretrain_weights=checkpoint_path, **model_kwargs)
        else:
            pretrain_filename = (
                _DEFAULT_PRETRAIN_WEIGHTS.get(self.base_model_name)
                if not self.from_scratch
                else None
            )
            if pretrain_filename:
                # In multi-GPU, only rank 0 downloads to avoid races; others wait for file.
                rank = int(os.environ.get("RANK", "0"))
                world_size = int(os.environ.get("WORLD_SIZE", "1"))
                if rank == 0:
                    download_pretrain_weights(pretrain_filename)
                else:
                    abs_path = os.path.abspath(pretrain_filename)
                    if world_size > 1:
                        for _ in range(120):
                            if os.path.isfile(abs_path):
                                break
                            time.sleep(1)
                        else:
                            download_pretrain_weights(pretrain_filename)
                    else:
                        download_pretrain_weights(pretrain_filename)
                model_kwargs["pretrain_weights"] = os.path.abspath(pretrain_filename)
            self.logger.info(f"Loading pre-trained RF-DETR model: {self.base_model_name}")
            self.rfdetr_wrapper = self.model_class(**model_kwargs)

        self.model = self.rfdetr_wrapper.model.model

        if hasattr(self.rfdetr_wrapper, "model") and hasattr(
            self.rfdetr_wrapper.model, "resolution"
        ):
            actual_resolution = self.rfdetr_wrapper.model.resolution
            self.logger.info(f"- RF-DETR model loaded with resolution: {actual_resolution}")
        else:
            self.logger.info("- RF-DETR model loaded (resolution not accessible)")

    def update_class_names_from_dataset(self, dataset_path: str) -> None:
        """Update class names from COCO dataset."""
        for split in ["train", "valid", "test"]:
            ann_path = Path(dataset_path) / split / "_annotations.coco.json"
            if ann_path.exists():
                with open(ann_path) as f:
                    data = json.load(f)
                categories = data.get("categories", [])
                if categories:
                    self.class_names = {
                        cat["id"]: cat["name"] for cat in sorted(categories, key=lambda x: x["id"])
                    }
                    self.logger.info(f"Loaded {len(self.class_names)} classes from dataset")
                    return
        self.logger.warning("Could not load class names from dataset")

    def _predict_single(self, detection_input: DetectionInput) -> Prediction:
        """Run inference on a single image."""
        if self.rfdetr_wrapper is None:
            raise ModelNotLoadedError()

        image = detection_input.image

        # Convert to PIL Image
        if isinstance(image, (str, Path)):
            image_path = str(image)
            pil_image = Image.open(image_path).convert("RGB")
        elif isinstance(image, np.ndarray):
            image_path = "array"
            pil_image = Image.fromarray(image).convert("RGB")
        elif isinstance(image, Image.Image):
            image_path = "pil"
            pil_image = image.convert("RGB")
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        start_time = time.time()
        detections = self.rfdetr_wrapper.predict(
            pil_image, threshold=detection_input.conf_threshold
        )
        inference_time = time.time() - start_time

        return Prediction.from_detections(
            detections=detections,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def train(self, config: TrainingConfig, is_main_process: bool = True) -> Dict[str, Any]:
        """Train RF-DETR model."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect and convert format if needed (RF-DETR needs COCO)
        if is_main_process:
            detector = FormatDetector(config.dataset_path)
            detected_format = detector.detect()

            if detected_format == "unknown":
                self.logger.warning("Could not auto-detect format, assuming COCO")
                detected_format = "coco"

            target_format = "coco"

            if detected_format != target_format:
                converted_dir = output_dir / "datasets" / "converted"
                # Skip if already converted
                if (converted_dir / "train" / "_annotations.coco.json").exists():
                    self.logger.info("Using existing COCO conversion: %s", converted_dir)
                else:
                    self.logger.info(
                        f"Converting dataset from {detected_format} to {target_format}"
                    )
                    converter = FormatConverter(
                        config.dataset_path, str(converted_dir), verbose=True
                    )
                    converter.convert(target_format=target_format, copy_images=False)
                config.dataset_path = str(converted_dir)

        self.update_class_names_from_dataset(config.dataset_path)

        if self.rfdetr_wrapper is None:
            self.load_model()

        # Prepare dataset subset only on the main process to avoid race conditions
        if is_main_process:
            dataset_path = self._prepare_dataset_subset(config)
        else:
            # Other processes will use the path prepared by the main process
            dataset_path = self._get_subset_path_if_any(config)

        # Synchronize all processes after dataset preparation
        if torch and torch.distributed.is_initialized():
            torch.distributed.barrier()

        uploader = None
        if is_main_process and config.push_to_hub:
            if not config.hub_model_id:
                raise ValueError("hub_model_id must be specified when push_to_hub is True.")
            from ..utils.huggingface import HuggingFaceUploader

            uploader = HuggingFaceUploader(
                repo_id=config.hub_model_id,
                local_dir=str(output_dir),
                repo_type="model",
                private=True,
            )
            uploader.ensure_repo_exists()

        # Setup callbacks
        self._setup_callbacks(config, output_dir, is_main_process)

        # Resolve resolution: prefer config.resolution, fallback to config.imgsz
        resolution = getattr(config, "resolution", None)
        if resolution is None:
            imgsz_raw = getattr(config, "imgsz", None)
            if isinstance(imgsz_raw, list):
                resolution = imgsz_raw[0]
            elif isinstance(imgsz_raw, int):
                resolution = imgsz_raw
            else:
                resolution = 560
        imgsz = int(resolution)

        if imgsz:
            if imgsz % 56 != 0:
                self.logger.warning(
                    f"Image size {imgsz} is not divisible by 56. "
                    f"This might lead to suboptimal performance or errors with RF-DETR's internal resizing."
                )

        # Ensure the correct device is passed to the underlying trainer
        device = config.device
        if torch and torch.distributed.is_initialized():
            # In DDP, the device should be the local rank
            local_rank = torch.distributed.get_rank()
            if not str(device).endswith(str(local_rank)):
                self.logger.warning(
                    f"Mismatch between config device ({device}) and DDP rank ({local_rank}). "
                    f"Forcing device to cuda:{local_rank}"
                )
                device = f"cuda:{local_rank}"

        # Build training arguments
        lr_encoder = getattr(config, "lr_encoder", None)
        train_args = {
            "dataset_dir": dataset_path,
            "output_dir": str(output_dir),
            "epochs": config.epochs,
            "warmup_epochs": getattr(config, "warmup_epochs", 1),
            "batch_size": config.batch_size,
            "grad_accum_steps": config.gradient_accumulation_steps,
            "lr": float(config.learning_rate),
            "lr_scheduler": getattr(config, "lr_scheduler_type", "step"),
            "lr_encoder": float(lr_encoder) if lr_encoder is not None else None,
            "resolution": imgsz,
            "weight_decay": config.weight_decay,
            "device": device,
            "use_ema": getattr(config, "use_ema", True),
            "gradient_checkpointing": getattr(config, "gradient_checkpointing", False),
            "checkpoint_interval": config.save_period,
            "tensorboard": config.tensorboard,
            "early_stopping": config.early_stopping_patience is not None,
            "early_stopping_patience": config.early_stopping_patience,
            "early_stopping_min_delta": config.early_stopping_delta,
            "early_stopping_use_ema": getattr(config, "early_stopping_use_ema", False),
            "clip_max_norm": getattr(config, "max_grad_norm", 1.0),
            "dropout": getattr(config, "dropout", 0.0),
            "drop_path": getattr(config, "drop_path", 0.0),
            "drop_mode": getattr(config, "drop_mode", "standard"),
            "drop_schedule": getattr(config, "drop_schedule", "constant"),
            "cutoff_epoch": getattr(config, "cutoff_epoch", 0),
            "freeze_encoder": getattr(config, "freeze_encoder", False),
            "layer_norm": getattr(config, "layer_norm", False),
            "rms_norm": getattr(config, "rms_norm", False),
            "backbone_lora": getattr(config, "backbone_lora", False),
            "multi_scale": getattr(config, "multi_scale", False),
            "force_no_pretrain": getattr(config, "force_no_pretrain", False),
            "ema_decay": getattr(config, "ema_decay", 0.9997),
            "ema_tau": getattr(config, "ema_tau", 0.0),
            "lr_vit_layer_decay": getattr(config, "lr_vit_layer_decay", 0.8),
            "lr_component_decay": getattr(config, "lr_component_decay", 1.0),
            "sync_bn": getattr(config, "sync_bn", True),
            "num_workers": getattr(config, "num_workers", 2),
            "amp": getattr(config, "mixed_precision", "no") == "fp16",
            "set_cost_class": getattr(config, "set_cost_class", 2.0),
            "set_cost_bbox": getattr(config, "set_cost_bbox", 5.0),
            "set_cost_giou": getattr(config, "set_cost_giou", 2.0),
            "start_epoch": getattr(config, "start_epoch", 0),
        }

        # Handle resuming from a checkpoint
        if not self.from_scratch and config.model and Path(config.model).exists():
            if getattr(config, "resume", False):
                train_args["resume"] = config.model
                self.logger.info(
                    f"Resuming training from checkpoint: {config.model} (including optimizer state)"
                )
            else:
                self.logger.info(
                    f"Fine-tuning from pre-trained weights: {config.model} (fresh optimizer/scheduler)"
                )

        self.logger.info(f"Starting RF-DETR training with args: {train_args}")

        try:
            self.rfdetr_wrapper.train(**{k: v for k, v in train_args.items() if v is not None})
        except FileNotFoundError as e:
            self.logger.warning(f"Caught expected FileNotFoundError in multi-GPU training: {e}")
            self.logger.warning(
                "This is likely a race condition and can be ignored if the main process succeeds."
            )
        except RuntimeError as e:
            if (
                "Error(s) in loading state_dict for DistributedDataParallel" in str(e)
                and torch
                and torch.distributed.is_initialized()
            ):
                self.logger.warning(
                    "Caught a known DDP state_dict loading error at the end of training. "
                    "This is likely a bug in the rfdetr library when loading the best checkpoint. "
                    "Since training is finished, we can proceed."
                )
            else:
                raise TrainingError(str(e)) from e

        # RF-DETR does not return metrics directly, logged to files.
        model_path = None
        if is_main_process:
            model_path = self._find_best_checkpoint(output_dir)
            self.logger.info(f"Using model checkpoint: {model_path}")

        return {
            "model_path": (
                str(model_path) if model_path and model_path.exists() else str(output_dir)
            ),
            "metrics": {},  # Metrics should be read from files by evaluation script
        }

    def _setup_callbacks(
        self, config: TrainingConfig, output_dir: Path, is_main_process: bool = True
    ) -> None:
        """Setup RF-DETR callbacks."""
        from ..utils.huggingface import HuggingFaceUploader

        self.rfdetr_wrapper._gc_batch_counter = 0

        def on_train_batch_gc(info_dict):
            """Lightweight garbage collection callback - runs gc.collect() periodically."""
            grad_accum_steps = config.gradient_accumulation_steps

            self.rfdetr_wrapper._gc_batch_counter += 1
            batch_count = self.rfdetr_wrapper._gc_batch_counter

            # Run Python GC every N gradient accumulation cycles
            gc_frequency = grad_accum_steps * 5 if grad_accum_steps > 1 else 20

            if batch_count % gc_frequency == 0:
                gc.collect()

                # Log memory usage occasionally (every 100 batches)
                if is_main_process and batch_count % 100 == 0:
                    if torch and torch.cuda.is_available():
                        for i in range(torch.cuda.device_count()):
                            try:
                                mem_reserved = torch.cuda.memory_reserved(i) / 1024**3
                                mem_allocated = torch.cuda.memory_allocated(i) / 1024**3
                                self.logger.debug(
                                    f"Batch {batch_count} - GPU {i}: "
                                    f"Reserved={mem_reserved:.2f}GB, Allocated={mem_allocated:.2f}GB"
                                )
                            except Exception:
                                pass  # Ignore errors in memory logging

        def on_epoch_end_gc(info_dict):
            """Heavy memory cleanup at end of each epoch - this is where we clear GPU cache."""
            gc.collect()

            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()

            self.rfdetr_wrapper._gc_batch_counter = 0

            if is_main_process:
                epoch = info_dict.get("epoch", "?")

                if torch and torch.cuda.is_available():
                    for i in range(torch.cuda.device_count()):
                        try:
                            mem_reserved = torch.cuda.memory_reserved(i) / 1024**3
                            mem_allocated = torch.cuda.memory_allocated(i) / 1024**3
                            self.logger.info(
                                f"Epoch {epoch} complete - GPU {i} memory: "
                                f"{mem_allocated:.2f}GB allocated / {mem_reserved:.2f}GB reserved (after cleanup)"
                            )
                        except Exception:
                            pass

        # Register GC callbacks
        self.rfdetr_wrapper.callbacks["on_train_batch_start"].append(on_train_batch_gc)
        self.rfdetr_wrapper.callbacks["on_fit_epoch_end"].append(on_epoch_end_gc)
        if is_main_process:
            grad_accum_steps = config.gradient_accumulation_steps
            gc_frequency = grad_accum_steps * 5 if grad_accum_steps > 1 else 20
            self.logger.info(
                f"Memory management configured: Python GC every {gc_frequency} batches, "
                "GPU cache cleared each epoch"
            )

        # HuggingFace upload callback
        if config.push_to_hub and config.hub_model_id:
            uploader = HuggingFaceUploader(
                repo_id=config.hub_model_id,
                local_dir=str(output_dir),
                repo_type="model",
                private=True,
            )
            uploader.ensure_repo_exists()

            def on_epoch_end_upload(stats):
                if is_main_process and uploader:
                    epoch = stats.get("epoch")
                    if epoch is None:
                        self.logger.warning(
                            "Epoch not found in stats, cannot determine when to upload."
                        )
                        return

                    if (epoch + 1) % config.save_period == 0:
                        self.logger.info(
                            f"Uploading checkpoint from epoch {epoch + 1} to Hugging Face Hub..."
                        )
                        try:
                            uploader.upload(
                                commit_message=f"Upload from epoch {epoch + 1}",
                                ignore_patterns=[
                                    "*.log",
                                    "dataset_subset/**",
                                    "tensorboard_server.log",
                                ],
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to upload to Hugging Face Hub: {e}")

            def on_train_end_upload():
                if is_main_process and uploader:
                    self.logger.info("Uploading final model and artifacts to Hugging Face Hub...")
                    try:
                        uploader.upload(
                            commit_message="Final model upload",
                            ignore_patterns=[
                                "*.log",
                                "dataset_subset/**",
                                "tensorboard_server.log",
                            ],
                        )
                    except Exception as e:
                        self.logger.error(f"Failed to upload final model to Hugging Face Hub: {e}")

            self.rfdetr_wrapper.callbacks["on_fit_epoch_end"].append(on_epoch_end_upload)
            self.rfdetr_wrapper.callbacks["on_train_end"].append(on_train_end_upload)
            if is_main_process:
                self.logger.info("Hugging Face Hub callback configured.")

    def _get_subset_path_if_any(self, config: TrainingConfig) -> str:
        """
        Get the path to the dataset subset if it was created, otherwise return the original path.
        """
        use_subset = config.max_train_samples or config.max_eval_samples or config.max_test_samples
        if use_subset:
            return str(Path(config.output_dir) / "datasets" / "subset")
        return config.dataset_path

    def _prepare_dataset_subset(self, config: TrainingConfig) -> str:
        """
        Creates a subset of the dataset if max_train_samples, max_eval_samples, or
        max_test_samples are specified in the config.
        Uses centralized SubsetCreator for balanced sampling.
        Returns the path to the dataset to be used for training.
        """
        source_dir = Path(config.dataset_path)

        if (
            not config.max_train_samples
            and not config.max_eval_samples
            and not config.max_test_samples
        ):
            self.logger.info("No max samples specified, using original dataset: %s", source_dir)
            return str(source_dir)

        self.logger.info("Creating a balanced subset of the dataset as max samples are specified.")
        subset_dir = Path(config.output_dir) / "datasets" / "subset"
        subset_dir.mkdir(parents=True, exist_ok=True)

        subset_creator = SubsetCreator(
            str(source_dir), str(subset_dir), seed=config.seed, verbose=True
        )
        subset_path = subset_creator.create(
            max_train_samples=config.max_train_samples,
            max_eval_samples=config.max_eval_samples,
            max_test_samples=config.max_test_samples,
        )

        # Symlink any source splits missing from the subset.
        for split in ["train", "valid", "test"]:
            subset_split = subset_dir / split
            source_split = source_dir / split
            if not subset_split.exists() and source_split.exists():
                os.symlink(source_split.resolve(), subset_split)
                self.logger.info("Linked missing split: %s -> %s", split, source_split)

        return subset_path

    def _find_best_checkpoint(self, output_dir: Path) -> Optional[Path]:
        """Find best checkpoint."""
        for name in [
            "checkpoint_best_total.pth",
            "checkpoint_best_regular.pth",
            "checkpoint_best_ema.pth",
            "checkpoint.pth",
        ]:
            path = output_dir / name
            if path.exists():
                return path
        return None

    def save(self, save_path: str) -> str:
        """Save model state dict."""
        if self.model is None:
            raise ModelNotLoadedError()

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        model_file = save_dir / f"{self.base_model_name}_saved.pth"

        torch.save(self.model.state_dict(), str(model_file))
        return str(model_file)
