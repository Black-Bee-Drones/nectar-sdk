"""HuggingFace Transformers detection model implementation."""

import gc
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    from transformers import (
        AutoConfig,
        AutoImageProcessor,
        AutoModelForObjectDetection,
        EarlyStoppingCallback,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    TrainerCallback = object

from PIL import Image

from nectar.ai.core.utils.device import get_device
from nectar.ai.detection.core.base import BaseDetectionModel
from nectar.ai.detection.core.configs import TrainingConfig
from nectar.ai.detection.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.detection.core.types import DetectionInput, Prediction
from nectar.ai.detection.datasets.format import FormatConverter, FormatDetector
from nectar.ai.detection.datasets.subset import SubsetCreator

logger = logging.getLogger(__name__)


class TransformersModel(BaseDetectionModel):
    """
    HuggingFace Transformers detection model.

    Supports DETR, RT-DETR, Conditional DETR and other transformer-based
    object detection models from HuggingFace.

    Parameters
    ----------
    model_name : str
        Model name or HuggingFace model ID (e.g., 'facebook/detr-resnet-50').
    from_scratch : bool, optional
        Train from scratch. Defaults to False.

    Examples
    --------
    >>> model = TransformersModel("facebook/detr-resnet-50")
    >>> model.load_model()
    >>> result = model.detect(image)
    """

    def __init__(self, model_name: str = "facebook/detr-resnet-50", from_scratch: bool = False):
        super().__init__(model_name, "transformers")

        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers is required. Install: pip install transformers")

        self.model = None
        self.processor = None
        self.from_scratch = from_scratch

    def load_model(
        self,
        model_path: Optional[str] = None,
        id2label: Optional[Dict[int, str]] = None,
        label2id: Optional[Dict[str, int]] = None,
        imgsz: int = 640,
    ) -> None:
        """
        Load model from path or HuggingFace Hub.

        Parameters
        ----------
        model_path : str, optional
            Model path or HuggingFace ID.
        id2label : dict, optional
            Class ID to label mapping.
        label2id : dict, optional
            Label to class ID mapping.
        imgsz : int, optional
            Image size. Defaults to 640.
        """
        path = model_path or self.model_name
        size = {"height": imgsz, "width": imgsz}

        self.processor = AutoImageProcessor.from_pretrained(
            path, do_resize=True, use_fast=True, size=size
        )

        model_kwargs = {"ignore_mismatched_sizes": True}

        if id2label and label2id:
            model_kwargs["id2label"] = id2label
            model_kwargs["label2id"] = label2id
            self.class_names = id2label
            self.logger.info(f"Using custom label mappings: {len(id2label)} classes")

        if self.from_scratch:
            self.logger.info("Initializing model from scratch")
            config = AutoConfig.from_pretrained(path)
            if id2label and label2id:
                config.id2label = id2label
                config.label2id = label2id
                config.num_labels = len(id2label)
            self.model = AutoModelForObjectDetection.from_config(config)
        else:
            self.model = AutoModelForObjectDetection.from_pretrained(path, **model_kwargs)

        if not id2label and hasattr(self.model.config, "id2label"):
            self.class_names = self.model.config.id2label
            self.logger.info(f"Using model's {len(self.class_names)} classes")

    def _predict_single(self, detection_input: DetectionInput) -> Prediction:
        """Run inference on a single image."""
        if self.model is None:
            raise ModelNotLoadedError()

        device = get_device(detection_input.device)
        self.model.to(device)
        self.model.eval()

        image = detection_input.image

        # Convert to PIL Image
        if isinstance(image, (str, Path)):
            image_path = str(image)
            pil_image = Image.open(image_path).convert("RGB")
        elif isinstance(image, np.ndarray):
            image_path = "array"
            if image.ndim == 3 and image.shape[2] == 3:
                image = np.ascontiguousarray(image[..., ::-1])
            pil_image = Image.fromarray(image).convert("RGB")
        elif isinstance(image, Image.Image):
            image_path = "pil"
            pil_image = image.convert("RGB")
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        inputs = self.processor(images=pil_image, return_tensors="pt").to(device)

        start_time = time.time()
        with torch.no_grad():
            outputs = self.model(**inputs)
        inference_time = time.time() - start_time

        target_sizes = torch.tensor([pil_image.size[::-1]])
        results = self.processor.post_process_object_detection(
            outputs,
            target_sizes=target_sizes,
            threshold=detection_input.conf_threshold,
        )[0]

        detections = sv.Detections.from_transformers(results).with_nms(
            threshold=detection_input.iou_threshold
        )

        return Prediction.from_detections(
            detections=detections,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def train(self, config: TrainingConfig) -> Dict[str, Any]:
        """Train transformer model using HuggingFace Trainer."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_name = output_dir.name

        # Auto-detect and convert format if needed (Transformers needs COCO)
        detector = FormatDetector(config.dataset_path)
        detected_format = detector.detect()

        if detected_format == "unknown":
            self.logger.warning("Could not auto-detect format, assuming COCO")
            detected_format = "coco"

        target_format = "coco"

        if detected_format != target_format:
            converted_dir = output_dir / "datasets" / "converted"
            if (converted_dir / "train" / "_annotations.coco.json").exists():
                self.logger.info("Using existing COCO conversion: %s", converted_dir)
            else:
                self.logger.info(f"Converting dataset from {detected_format} to {target_format}")
                converter = FormatConverter(config.dataset_path, str(converted_dir), verbose=True)
                converter.convert(target_format=target_format, copy_images=False)
            config.dataset_path = str(converted_dir)

        # Create subset if max_samples specified
        if config.max_train_samples is not None or config.max_eval_samples is not None:
            subset_dir = output_dir / "datasets" / "subset"
            source_dir = Path(config.dataset_path)
            subset_creator = SubsetCreator(
                config.dataset_path, str(subset_dir), seed=config.seed, verbose=True
            )
            subset_path = subset_creator.create(
                max_train_samples=config.max_train_samples,
                max_eval_samples=config.max_eval_samples,
                max_test_samples=config.max_test_samples,
            )
            # Symlink missing splits so evaluation can find them
            for split in ["train", "valid", "val", "test"]:
                subset_split = subset_dir / split
                source_split = source_dir / split
                if not subset_split.exists() and source_split.exists():
                    import os

                    os.symlink(source_split.resolve(), subset_split)
            config.dataset_path = subset_path

        # Load dataset
        train_dataset, val_dataset, id2label, label2id = self._load_coco_dataset(config)

        # Load model with dataset classes
        imgsz = getattr(config, "imgsz", 640)
        self.load_model(self.model_name, id2label=id2label, label2id=label2id, imgsz=imgsz)

        # Setup callbacks
        callbacks = self._setup_callbacks(config, output_dir)

        # Training arguments - use framework-specific config if available
        if hasattr(config, "to_training_args"):
            args_dict = config.to_training_args()
            args_dict["output_dir"] = str(output_dir / run_name)
            args_dict["run_name"] = run_name
            args_dict["logging_dir"] = (
                str(output_dir / run_name / "logs") if config.tensorboard else None
            )
            training_args = TrainingArguments(**args_dict)
        else:
            # Fallback for base TrainingConfig
            training_args = TrainingArguments(
                output_dir=str(output_dir / run_name),
                num_train_epochs=config.epochs,
                per_device_train_batch_size=config.batch_size,
                per_device_eval_batch_size=config.batch_size,
                gradient_accumulation_steps=config.gradient_accumulation_steps,
                learning_rate=config.learning_rate,
                logging_dir=(str(output_dir / run_name / "logs") if config.tensorboard else None),
                logging_steps=5,
                eval_strategy="epoch",
                save_strategy="epoch",
                save_total_limit=3,
                load_best_model_at_end=True,
                metric_for_best_model=config.early_stopping_metric or "eval_loss",
                greater_is_better=(config.early_stopping_mode == "max"),
                seed=config.seed,
                report_to=["tensorboard"] if config.tensorboard else None,
                run_name=run_name,
                fp16=(config.mixed_precision == "fp16"),
                bf16=(config.mixed_precision == "bf16"),
                dataloader_pin_memory=False,
                remove_unused_columns=False,
                warmup_ratio=getattr(config, "warmup_ratio", 0.1),
                warmup_steps=getattr(config, "warmup_steps", 0),
                weight_decay=getattr(config, "weight_decay", 0.0001),
                lr_scheduler_type=getattr(config, "lr_scheduler_type", "linear"),
                max_grad_norm=getattr(config, "max_grad_norm", 1.0),
            )
            optimizer = getattr(config, "optimizer_type", None)
            if optimizer is not None:
                training_args.optim = optimizer

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            processing_class=self.processor,
            data_collator=self._collate_fn,
            callbacks=callbacks,
        )

        # Check if we're resuming from a checkpoint
        resume_from_checkpoint = None
        if not config.from_scratch and config.model and "checkpoint" in config.model:
            resume_from_checkpoint = config.model
            if getattr(config, "resume", False):
                self.logger.info(f"Resuming from checkpoint: {resume_from_checkpoint}")
                self.logger.info(
                    "This will load optimizer and scheduler states to continue training "
                    "from the same point"
                )

        try:
            train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)

            trainer.save_model()
            trainer.save_state()

            metrics = self._extract_training_metrics(train_result)

            return {"model_path": str(output_dir / run_name), "metrics": metrics}

        except Exception as e:
            raise TrainingError(str(e)) from e

    def _load_coco_dataset(self, config: TrainingConfig):
        """
        Load COCO format dataset from the given path.

        Expects Roboflow format (train/valid/test with _annotations.coco.json).
        Standard COCO format (images/ + dataset.json) should be converted first
        using FormatConverter or Stratifier.
        """
        from .dataset import CocoDetectionDataset

        dataset_path = Path(config.dataset_path)

        # Check for standard COCO format - should be converted first
        images_dir = dataset_path / "images"
        dataset_json = dataset_path / "dataset.json"
        if not dataset_json.exists():
            potential_files = list(dataset_path.glob("*.json"))
            if potential_files:
                dataset_json = potential_files[0]

        if images_dir.exists() and dataset_json.exists():
            self.logger.info(
                f"Standard COCO format detected at {dataset_path}. "
                f"Creating splits using Stratifier..."
            )
            from nectar.ai.detection.datasets.stratify import Stratifier

            stratified_dir = Path(config.output_dir) / "datasets" / "stratified"
            stratifier = Stratifier(
                str(dataset_path),
                str(stratified_dir),
                seed=config.seed,
                verbose=True,
            )
            train_ratio = getattr(config, "train_split", 0.8)
            val_ratio = getattr(config, "val_split", 0.2)
            test_ratio = getattr(config, "test_split", 0.0)
            stratified_path = stratifier.stratify(
                train_ratio, val_ratio, test_ratio, target_format="coco"
            )
            dataset_path = Path(stratified_path)

        train_dir = dataset_path / "train"
        train_annotations = train_dir / "_annotations.coco.json"

        val_dir = dataset_path / "valid"
        if not val_dir.exists():
            val_dir = dataset_path / "val"
        if not val_dir.exists():
            val_dir = dataset_path / "validation"

        val_annotations = val_dir / "_annotations.coco.json"

        if not train_dir.exists() or not train_annotations.exists():
            raise TrainingError(
                f"Dataset not in expected format. Expected Roboflow COCO format at {train_dir} "
                f"with _annotations.coco.json. "
                f"If you have standard COCO format (images/ + dataset.json), "
                f"use Stratifier to create splits first."
            )

        if not val_dir.exists() or not val_annotations.exists():
            self.logger.warning(
                f"Validation data not found at {val_dir}, using training data for validation"
            )
            val_dir = train_dir
            val_annotations = train_annotations

        # Create datasets
        train_dataset = CocoDetectionDataset(
            img_dir=str(train_dir),
            annotations_file=str(train_annotations),
            image_processor=self.processor,
            train=True,
            max_samples=config.max_train_samples,
            seed=config.seed,
        )

        val_dataset = CocoDetectionDataset(
            img_dir=str(val_dir),
            annotations_file=str(val_annotations),
            image_processor=self.processor,
            train=False,
            max_samples=config.max_eval_samples,
            seed=config.seed,
        )

        return (
            train_dataset,
            val_dataset,
            train_dataset.id2label,
            train_dataset.label2id,
        )

    def _setup_callbacks(self, config: TrainingConfig, output_dir: Path) -> List:
        """Setup training callbacks."""
        callbacks = []

        if config.early_stopping_patience:
            callbacks.append(
                EarlyStoppingCallback(
                    early_stopping_patience=config.early_stopping_patience,
                    early_stopping_threshold=config.early_stopping_delta,
                )
            )

        if getattr(config, "gc_per_accumulation", True):
            callbacks.append(_GCCallback(config.gradient_accumulation_steps))

        if config.push_to_hub and config.hub_model_id:
            from nectar.ai.core.utils.callbacks import get_hf_upload_transformers_callback

            callbacks.append(
                get_hf_upload_transformers_callback(config.hub_model_id, output_dir, self.logger)
            )

        return callbacks

    @staticmethod
    def _collate_fn(batch):
        """Collate function for DataLoader."""
        from .dataset import collate_fn

        return collate_fn(batch)

    def _extract_training_metrics(self, train_result) -> Dict[str, Any]:
        """Extract metrics from training result."""
        metrics = {}
        if hasattr(train_result, "training_loss"):
            metrics["train_loss"] = train_result.training_loss
        if hasattr(train_result, "metrics"):
            for key, value in train_result.metrics.items():
                metrics[key] = value
        return metrics

    def save(self, save_path: str) -> str:
        """Save model and processor."""
        if self.model is None:
            raise ModelNotLoadedError()

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        self.model.save_pretrained(str(save_dir))
        self.processor.save_pretrained(str(save_dir))

        return str(save_dir)


class _GCCallback(TrainerCallback):
    """Garbage collection callback."""

    def __init__(self, accumulation_steps: int = 1):
        self.accumulation_steps = accumulation_steps

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step % self.accumulation_steps == 0:
            gc.collect()

    def on_epoch_end(self, args, state, control, **kwargs):
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
