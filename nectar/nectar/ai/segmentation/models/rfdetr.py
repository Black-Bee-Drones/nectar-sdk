"""RF-DETR segmentation model implementation."""

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
    from rfdetr import (
        RFDETRSeg2XLarge,
        RFDETRSegLarge,
        RFDETRSegMedium,
        RFDETRSegNano,
        RFDETRSegSmall,
        RFDETRSegXLarge,
    )
    from rfdetr.util.coco_classes import COCO_CLASSES

    RFDETR_SEG_AVAILABLE = True
    RFDETR_SEG_MODELS = {
        "rfdetr-seg-nano": RFDETRSegNano,
        "rfdetr-seg-small": RFDETRSegSmall,
        "rfdetr-seg-medium": RFDETRSegMedium,
        "rfdetr-seg-large": RFDETRSegLarge,
        "rfdetr-seg-xlarge": RFDETRSegXLarge,
        "rfdetr-seg-2xlarge": RFDETRSeg2XLarge,
    }
except ImportError as _rfdetr_err:
    RFDETR_SEG_AVAILABLE = False
    COCO_CLASSES = []
    RFDETR_SEG_MODELS = {}
    logging.getLogger(__name__).debug("rfdetr seg import failed: %s", _rfdetr_err)

from PIL import Image

from nectar.ai.detection.datasets.format import FormatDetector
from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import SegTrainingConfig
from nectar.ai.segmentation.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.segmentation.core.types import SegmentationInput, SegPrediction
from nectar.ai.segmentation.datasets.format import SegFormatConverter

logger = logging.getLogger(__name__)


class RFDETRSegModel(BaseSegmentationModel):
    """
    RF-DETR instance segmentation model wrapper.

    Parameters
    ----------
    model_name : str
        Model name ('rfdetr-seg-medium') or checkpoint path.
    rfdetr_size : str, optional
        Explicit model size (nano, small, medium, large, xlarge, 2xlarge).
    resolution : int, optional
        Image resolution.
    from_scratch : bool
        Train from scratch.
    """

    def __init__(
        self,
        model_name: str = "rfdetr-seg-medium",
        rfdetr_size: Optional[str] = None,
        resolution: Optional[int] = None,
        from_scratch: bool = False,
    ):
        super().__init__(model_name, "rfdetr")

        if not RFDETR_SEG_AVAILABLE:
            raise ImportError("rfdetr is required. Install: pip install rfdetr")

        self.model_path = model_name if Path(model_name).exists() else None

        if rfdetr_size:
            self.base_model_name = f"rfdetr-seg-{rfdetr_size.lower()}"
        elif self.model_path:
            self.base_model_name = self._infer_model_size(self.model_path)
        else:
            self.base_model_name = model_name

        self.model_class = RFDETR_SEG_MODELS.get(self.base_model_name)
        if self.model_class is None:
            raise ValueError(
                f"Unsupported RF-DETR seg model: '{self.base_model_name}'. "
                f"Available: {list(RFDETR_SEG_MODELS.keys())}"
            )

        self.model = None
        self.rfdetr_wrapper = None
        self.from_scratch = from_scratch
        self.resolution = resolution
        self.class_names = {i: name for i, name in enumerate(COCO_CLASSES)}

    def _infer_model_size(self, path: str) -> str:
        """Infer model size from checkpoint path."""
        path_obj = Path(path)
        candidates = [str(path_obj.name).lower()] + [str(p.name).lower() for p in path_obj.parents]
        for candidate in candidates:
            for size in RFDETR_SEG_MODELS.keys():
                size_short = size.replace("rfdetr-seg-", "")
                if size_short in candidate:
                    return size
        return "rfdetr-seg-medium"

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load RF-DETR segmentation model."""
        checkpoint_path = model_path or self.model_path
        model_kwargs = {}

        if len(self.class_names) != len(COCO_CLASSES):
            model_kwargs["num_classes"] = len(self.class_names)

        if self.resolution:
            model_kwargs["resolution"] = self.resolution

        if torch and torch.backends.mps.is_available():
            model_kwargs["device"] = "mps"

        if checkpoint_path and Path(checkpoint_path).exists():
            self.logger.info("Loading RF-DETR seg model from checkpoint: %s", checkpoint_path)
            self.rfdetr_wrapper = self.model_class(pretrain_weights=checkpoint_path, **model_kwargs)
        else:
            self.logger.info("Loading pre-trained RF-DETR seg model: %s", self.base_model_name)
            self.rfdetr_wrapper = self.model_class(**model_kwargs)

        self.model = self.rfdetr_wrapper.model.model

    def update_class_names_from_dataset(self, dataset_path: str) -> None:
        """Update class names from COCO dataset annotations."""
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
                    self.logger.info("Loaded %d classes from dataset", len(self.class_names))
                    return
        self.logger.warning("Could not load class names from dataset")

    def _predict_single(self, seg_input: SegmentationInput) -> SegPrediction:
        """Run segmentation inference on a single image."""
        if self.rfdetr_wrapper is None:
            raise ModelNotLoadedError()

        image = seg_input.image

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
        detections = self.rfdetr_wrapper.predict(pil_image, threshold=seg_input.conf_threshold)
        inference_time = time.time() - start_time

        return SegPrediction.from_detections(
            detections=detections,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def train(self, config: SegTrainingConfig) -> Dict[str, Any]:
        """Train RF-DETR segmentation model."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        detector = FormatDetector(config.dataset_path)
        detected_format = detector.detect()

        if detected_format == "unknown":
            detected_format = "coco"

        if detected_format != "coco":
            converted_dir = output_dir / "datasets" / "converted"
            if not (converted_dir / "train" / "_annotations.coco.json").exists():
                self.logger.info("Converting dataset from %s to coco", detected_format)
                converter = SegFormatConverter(
                    config.dataset_path, str(converted_dir), verbose=True
                )
                converter.convert(target_format="coco", copy_images=False)
            config.dataset_path = str(converted_dir)

        self.update_class_names_from_dataset(config.dataset_path)

        if self.rfdetr_wrapper is None:
            self.load_model()

        dataset_path = config.dataset_path
        if config.max_train_samples is not None or config.max_eval_samples is not None:
            subset_output_dir = output_dir / "datasets" / "subset"
            subset_creator = SubsetCreator(
                config.dataset_path,
                str(subset_output_dir),
                seed=config.seed,
                verbose=True,
            )
            dataset_path = subset_creator.create(
                max_train_samples=config.max_train_samples,
                max_eval_samples=config.max_eval_samples,
                max_test_samples=config.max_test_samples,
            )

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
            "device": config.device,
            "use_ema": getattr(config, "use_ema", True),
            "gradient_checkpointing": getattr(config, "gradient_checkpointing", False),
            "checkpoint_interval": config.save_period,
            "tensorboard": config.tensorboard,
            "early_stopping": config.early_stopping_patience is not None,
            "early_stopping_patience": config.early_stopping_patience,
            "early_stopping_min_delta": config.early_stopping_delta,
        }

        # GC callback
        self.rfdetr_wrapper._gc_batch_counter = 0

        def on_epoch_end_gc(info_dict):
            gc.collect()
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
            self.rfdetr_wrapper._gc_batch_counter = 0

        self.rfdetr_wrapper.callbacks["on_fit_epoch_end"].append(on_epoch_end_gc)

        try:
            self.rfdetr_wrapper.train(**{k: v for k, v in train_args.items() if v is not None})
        except RuntimeError as e:
            raise TrainingError(str(e)) from e

        model_path = self._find_best_checkpoint(output_dir)
        return {
            "model_path": str(model_path)
            if model_path and model_path.exists()
            else str(output_dir),
            "metrics": {},
        }

    def _find_best_checkpoint(self, output_dir: Path) -> Optional[Path]:
        """Find best model checkpoint from output directory."""
        candidates = [
            "checkpoint_best_total.pth",
            "checkpoint_best_ema.pth",
            "checkpoint_best_regular.pth",
            "checkpoint.pth",
        ]
        for name in candidates:
            path = output_dir / name
            if path.exists():
                return path
        return None

    def save(self, save_path: str) -> str:
        """Save model to path."""
        if self.model is None:
            raise ModelNotLoadedError()

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        model_path = save_dir / f"{Path(self.model_name).stem}_saved.pth"

        if torch:
            torch.save(self.model.state_dict(), str(model_path))

        return str(model_path)
