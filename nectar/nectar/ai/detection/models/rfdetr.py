"""RF-DETR model implementation."""

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
    from rfdetr import RFDETRLarge, RFDETRMedium, RFDETRNano, RFDETRSmall
    from rfdetr.assets.coco_classes import COCO_CLASS_NAMES

    RFDETR_AVAILABLE = True
    RFDETR_MODELS = {
        "rfdetr-nano": RFDETRNano,
        "rfdetr-small": RFDETRSmall,
        "rfdetr-medium": RFDETRMedium,
        "rfdetr-large": RFDETRLarge,
    }
except ImportError as _rfdetr_err:
    RFDETR_AVAILABLE = False
    COCO_CLASS_NAMES = []
    RFDETR_MODELS = {}
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
        Model name ('rfdetr-medium') or checkpoint path.
    rfdetr_size : str, optional
        Explicit model size (nano, small, medium, large).
    resolution : int, optional
        Image resolution. Defaults to model's default.
    from_scratch : bool, optional
        Train from scratch. Defaults to False.

    Examples
    --------
    >>> model = RFDETRModel("rfdetr-medium")
    >>> model.load_model()
    >>> result = model.detect(image)
    """

    def __init__(
        self,
        model_name: str = "rfdetr-medium",
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

        self.base_model_name = self.base_model_name.replace("rf-detr", "rfdetr").replace(
            "rf_detr", "rfdetr"
        )
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
        self.class_names = {i: name for i, name in enumerate(COCO_CLASS_NAMES)}

    def _infer_model_size(self, path: str) -> str:
        """Infer model size from checkpoint path."""
        path = Path(path)
        candidates = [str(path.name).lower()] + [str(p.name).lower() for p in path.parents]
        for candidate in candidates:
            for size in RFDETR_MODELS.keys():
                size_short = size.replace("rfdetr-", "")
                if size_short in candidate:
                    return size
        return "rfdetr-medium"

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load RF-DETR model."""
        checkpoint_path = model_path or self.model_path
        model_kwargs = {}

        if len(self.class_names) != len(COCO_CLASS_NAMES):
            model_kwargs["num_classes"] = len(self.class_names)

        if self.resolution:
            model_kwargs["resolution"] = self.resolution

        if torch and torch.backends.mps.is_available():
            model_kwargs["device"] = "mps"

        if checkpoint_path and Path(checkpoint_path).exists():
            self.logger.info("Loading RF-DETR model from checkpoint: %s", checkpoint_path)
            self.rfdetr_wrapper = self.model_class(pretrain_weights=checkpoint_path, **model_kwargs)
        else:
            if self.from_scratch:
                model_kwargs["pretrain_weights"] = None
            self.logger.info("Loading pre-trained RF-DETR model: %s", self.base_model_name)
            self.rfdetr_wrapper = self.model_class(**model_kwargs)

        self.model = self.rfdetr_wrapper.model.model

        wrapper_names = getattr(self.rfdetr_wrapper, "class_names", None)
        if wrapper_names:
            self.class_names = {i: name for i, name in enumerate(wrapper_names)}

    def update_class_names_from_dataset(self, dataset_path: str) -> None:
        """Update class names from dataset annotations (COCO or YOLO)."""
        dataset_root = Path(dataset_path)
        if dataset_root.suffix in (".yaml", ".yml"):
            dataset_root = dataset_root.parent

        for split in ["train", "valid", "test"]:
            ann_path = dataset_root / split / "_annotations.coco.json"
            if ann_path.exists():
                with open(ann_path) as f:
                    data = json.load(f)
                categories = sorted(data.get("categories", []), key=lambda c: c["id"])
                if categories:
                    self.class_names = {i: cat["name"] for i, cat in enumerate(categories)}
                    self.logger.info(
                        "Loaded %d classes from COCO annotations",
                        len(self.class_names),
                    )
                    return

        yaml_path = dataset_root / "data.yaml"
        if yaml_path.exists():
            import yaml

            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            names = data.get("names", {})
            if isinstance(names, dict):
                self.class_names = {int(k): v for k, v in names.items()}
            elif isinstance(names, list):
                self.class_names = {i: n for i, n in enumerate(names)}
            if self.class_names:
                self.logger.info("Loaded %d classes from data.yaml", len(self.class_names))
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
            pil_image,
            threshold=detection_input.conf_threshold,
            include_source_image=False,
        )
        inference_time = time.time() - start_time

        for key in ("source_shape", "source_image"):
            detections.data.pop(key, None)

        if len(detections) > 0 and detections.class_id is not None:
            valid = detections.class_id < len(self.class_names)
            detections = detections[valid]

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

        if is_main_process:
            detector = FormatDetector(config.dataset_path)
            detected_format = detector.detect()

            if detected_format == "unknown":
                self.logger.warning("Could not auto-detect format, assuming COCO")
                detected_format = "coco"

            if detected_format != "coco":
                converted_dir = output_dir / "datasets" / "converted"
                if (converted_dir / "train" / "_annotations.coco.json").exists():
                    self.logger.info("Using existing COCO conversion: %s", converted_dir)
                else:
                    self.logger.info("Converting dataset from %s to coco", detected_format)
                    converter = FormatConverter(
                        config.dataset_path, str(converted_dir), verbose=True
                    )
                    converter.convert(target_format="coco", copy_images=False)
                config.dataset_path = str(converted_dir)

        self.update_class_names_from_dataset(config.dataset_path)

        if self.rfdetr_wrapper is None:
            self.load_model()

        if is_main_process:
            dataset_path = self._prepare_dataset_subset(config)
        else:
            dataset_path = self._get_subset_path_if_any(config)

        if torch and torch.distributed.is_initialized():
            torch.distributed.barrier()

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

        # Apply ModelConfig overrides before training
        if getattr(config, "gradient_checkpointing", False):
            self.rfdetr_wrapper.model_config.gradient_checkpointing = True
        if getattr(config, "freeze_encoder", False):
            self.rfdetr_wrapper.model_config.freeze_encoder = True
        if getattr(config, "backbone_lora", False):
            self.rfdetr_wrapper.model_config.backbone_lora = True

        lr_scheduler = getattr(config, "lr_scheduler_type", "step")
        if lr_scheduler not in ("step", "cosine"):
            lr_scheduler = "step"

        lr_encoder = getattr(config, "lr_encoder", None)
        esp = config.early_stopping_patience
        train_kwargs: Dict[str, Any] = {
            "dataset_dir": dataset_path,
            "output_dir": str(output_dir),
            "epochs": config.epochs,
            "warmup_epochs": getattr(config, "warmup_epochs", 1),
            "batch_size": config.batch_size,
            "grad_accum_steps": config.gradient_accumulation_steps,
            "lr": float(config.learning_rate),
            "lr_scheduler": lr_scheduler,
            "lr_encoder": float(lr_encoder) if lr_encoder is not None else None,
            "weight_decay": config.weight_decay,
            "use_ema": getattr(config, "use_ema", True),
            "checkpoint_interval": config.save_period,
            "tensorboard": config.tensorboard,
            "early_stopping": esp is not None and esp > 0,
            "early_stopping_min_delta": config.early_stopping_delta,
            "early_stopping_use_ema": getattr(config, "early_stopping_use_ema", False),
            "clip_max_norm": getattr(config, "max_grad_norm", 1.0),
            "drop_path": getattr(config, "drop_path", 0.0),
            "multi_scale": getattr(config, "multi_scale", False),
            "ema_decay": getattr(config, "ema_decay", 0.9997),
            "ema_tau": getattr(config, "ema_tau", 0.0),
            "lr_vit_layer_decay": getattr(config, "lr_vit_layer_decay", 0.8),
            "lr_component_decay": getattr(config, "lr_component_decay", 1.0),
            "sync_bn": getattr(config, "sync_bn", True),
            "num_workers": getattr(config, "num_workers", 2),
            "seed": config.seed,
        }
        if esp is not None:
            train_kwargs["early_stopping_patience"] = esp

        resume_path = None
        if not self.from_scratch and config.model and Path(config.model).exists():
            if getattr(config, "resume", False):
                resume_path = config.model
                self.logger.info("Resuming training from checkpoint: %s", config.model)

        try:
            self._train_with_ptl(config, output_dir, imgsz, train_kwargs, resume_path)
        except RuntimeError as e:
            raise TrainingError(str(e)) from e

        model_path = None
        if is_main_process:
            model_path = self._find_best_checkpoint(output_dir)
            self.logger.info("Using model checkpoint: %s", model_path)

        return {
            "model_path": (
                str(model_path) if model_path and model_path.exists() else str(output_dir)
            ),
            "metrics": {},
        }

    def _train_with_ptl(
        self,
        config: TrainingConfig,
        output_dir: Path,
        resolution: int,
        train_kwargs: Dict[str, Any],
        resume_path: Optional[str] = None,
    ) -> None:
        """Run training via the RF-DETR Custom Training API (PTL)."""
        from rfdetr.config import TrainConfig as RFTrainConfig
        from rfdetr.training import RFDETRDataModule, RFDETRModelModule, build_trainer

        from nectar.ai.detection.utils.callbacks import get_hf_upload_ptl_callback

        model_config = self.rfdetr_wrapper.model_config
        model_config.resolution = resolution
        model_config.num_classes = len(self.class_names)

        filtered = {k: v for k, v in train_kwargs.items() if v is not None}
        rf_train_config = RFTrainConfig(**filtered)

        module = RFDETRModelModule(model_config, rf_train_config)
        datamodule = RFDETRDataModule(model_config, rf_train_config)
        trainer = build_trainer(rf_train_config, model_config)

        if config.push_to_hub and config.hub_model_id:
            hf_cb = get_hf_upload_ptl_callback(config.hub_model_id, output_dir, self.logger)
            trainer.callbacks.extend([hf_cb])

        trainer.fit(module, datamodule, ckpt_path=resume_path)

        self.rfdetr_wrapper.model.model = module.model

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
