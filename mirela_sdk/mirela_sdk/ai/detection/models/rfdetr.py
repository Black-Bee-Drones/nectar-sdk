"""RF-DETR model implementation."""

import gc
import json
import logging
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
    from rfdetr.util.coco_classes import COCO_CLASSES

    RFDETR_AVAILABLE = True
    RFDETR_MODELS = {
        "rfdetr-nano": RFDETRNano,
        "rfdetr-small": RFDETRSmall,
        "rfdetr-base": RFDETRBase,
        "rfdetr-medium": RFDETRMedium,
        "rfdetr-large": RFDETRLarge,
    }
except ImportError:
    RFDETR_AVAILABLE = False
    COCO_CLASSES = []
    RFDETR_MODELS = {}

from PIL import Image

from mirela_sdk.ai.detection.core.base import BaseDetectionModel
from mirela_sdk.ai.detection.core.configs import TrainingConfig
from mirela_sdk.ai.detection.core.exceptions import ModelNotLoadedError, TrainingError
from mirela_sdk.ai.detection.core.types import DetectionInput, Prediction

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
            self.logger.info(f"Loading from checkpoint: {checkpoint_path}")
            self.rfdetr_wrapper = self.model_class(pretrain_weights=checkpoint_path, **model_kwargs)
        else:
            self.logger.info(f"Loading pretrained: {self.base_model_name}")
            self.rfdetr_wrapper = self.model_class(**model_kwargs)

        self.model = self.rfdetr_wrapper.model.model

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

    def train(self, config: TrainingConfig) -> Dict[str, Any]:
        """Train RF-DETR model."""
        self.update_class_names_from_dataset(config.dataset_path)

        if self.rfdetr_wrapper is None:
            self.load_model()

        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare dataset subset if needed
        dataset_path = self._prepare_dataset_subset(config, output_dir)

        # Setup callbacks
        self._setup_callbacks(config, output_dir)

        # Build training arguments - use framework-specific config if available
        if hasattr(config, "to_rfdetr_args"):
            train_args = config.to_rfdetr_args()
            train_args["dataset_dir"] = dataset_path
            train_args["output_dir"] = str(output_dir)
        else:
            # Fallback for base TrainingConfig
            imgsz = getattr(config, "imgsz", 728)
            if imgsz % 56 != 0:
                self.logger.warning("Image size %d not divisible by 56", imgsz)

            train_args = {
                "dataset_dir": dataset_path,
                "output_dir": str(output_dir),
                "epochs": config.epochs,
                "batch_size": config.batch_size,
                "grad_accum_steps": config.gradient_accumulation_steps,
                "lr": config.learning_rate,
                "resolution": imgsz,
                "weight_decay": getattr(config, "weight_decay", 0.0001),
                "device": config.device,
                "use_ema": getattr(config, "use_ema", True),
                "checkpoint_interval": config.save_period,
                "tensorboard": config.tensorboard,
                "early_stopping": config.early_stopping_patience is not None,
                "early_stopping_patience": config.early_stopping_patience,
                "warmup_epochs": getattr(config, "warmup_epochs", 1),
                "amp": config.mixed_precision == "fp16",
            }

        self.logger.info("Starting RF-DETR training")

        try:
            self.rfdetr_wrapper.train(**{k: v for k, v in train_args.items() if v is not None})
        except RuntimeError as e:
            if "DistributedDataParallel" in str(e):
                self.logger.warning("DDP error at end of training, ignoring")
            else:
                raise TrainingError(str(e)) from e

        model_path = self._find_best_checkpoint(output_dir)

        return {
            "model_path": str(model_path) if model_path else str(output_dir),
            "metrics": {},
        }

    def _setup_callbacks(self, config: TrainingConfig, output_dir: Path) -> None:
        """Setup RF-DETR callbacks."""
        from ..utils.huggingface import HuggingFaceUploader

        # Initialize GC callback
        self.rfdetr_wrapper._gc_batch_counter = 0

        def on_batch_gc(info_dict):
            self.rfdetr_wrapper._gc_batch_counter += 1
            if self.rfdetr_wrapper._gc_batch_counter % 20 == 0:
                gc.collect()

        def on_epoch_gc(info_dict):
            gc.collect()
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.rfdetr_wrapper._gc_batch_counter = 0

        self.rfdetr_wrapper.callbacks["on_train_batch_start"].append(on_batch_gc)
        self.rfdetr_wrapper.callbacks["on_fit_epoch_end"].append(on_epoch_gc)

        # HuggingFace upload callback
        if config.push_to_hub and config.hub_model_id:
            uploader = HuggingFaceUploader(
                repo_id=config.hub_model_id,
                local_dir=str(output_dir),
                private=True,
            )
            uploader.ensure_repo_exists()

            def on_epoch_upload(stats):
                epoch = stats.get("epoch", 0)
                if (epoch + 1) % config.save_period == 0:
                    try:
                        uploader.upload(
                            commit_message=f"Epoch {epoch + 1}",
                            ignore_patterns=["*.log", "dataset_subset/**"],
                        )
                    except Exception as e:
                        self.logger.error(f"Upload failed: {e}")

            def on_train_end_upload():
                try:
                    uploader.upload(commit_message="Training completed")
                except Exception as e:
                    self.logger.error(f"Final upload failed: {e}")

            self.rfdetr_wrapper.callbacks["on_fit_epoch_end"].append(on_epoch_upload)
            self.rfdetr_wrapper.callbacks["on_train_end"].append(on_train_end_upload)

    def _prepare_dataset_subset(self, config: TrainingConfig, output_dir: Path) -> str:
        """Create dataset subset if max samples specified."""
        if not config.max_train_samples and not config.max_eval_samples:
            return config.dataset_path

        import random
        import shutil

        source_dir = Path(config.dataset_path)
        subset_dir = output_dir / "dataset_subset"
        subset_dir.mkdir(parents=True, exist_ok=True)

        for split in ["train", "valid", "test"]:
            source_split = source_dir / split
            if not source_split.is_dir():
                continue

            max_samples = config.max_train_samples if split == "train" else config.max_eval_samples
            if not max_samples:
                continue

            ann_file = source_split / "_annotations.coco.json"
            if not ann_file.exists():
                continue

            with open(ann_file) as f:
                data = json.load(f)

            images = data["images"]
            if max_samples and len(images) > max_samples:
                random.seed(config.seed)
                random.shuffle(images)
                images = images[:max_samples]

            image_ids = {img["id"] for img in images}
            annotations = [a for a in data["annotations"] if a["image_id"] in image_ids]

            new_data = {
                "images": images,
                "annotations": annotations,
                "categories": data["categories"],
            }

            target_split = subset_dir / split
            target_split.mkdir(parents=True, exist_ok=True)

            with open(target_split / "_annotations.coco.json", "w") as f:
                json.dump(new_data, f)

            for img in images:
                src = source_split / img["file_name"]
                dst = target_split / img["file_name"]
                if src.exists() and not dst.exists():
                    shutil.copy(src, dst)

            self.logger.info(f"Created {split} subset: {len(images)} images")

        return str(subset_dir)

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
