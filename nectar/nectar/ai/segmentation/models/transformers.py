"""HuggingFace Transformers segmentation model implementation."""

import gc
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import torch
    from torch import nn
except ImportError:
    torch = None
    nn = None

try:
    import supervision as sv
except ImportError:
    sv = None

try:
    from transformers import (
        AutoConfig,
        AutoImageProcessor,
        AutoModelForInstanceSegmentation,
        AutoModelForSemanticSegmentation,
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

from nectar.ai.detection.datasets.format import FormatDetector
from nectar.ai.detection.utils.device import get_device
from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import SegTrainingConfig
from nectar.ai.segmentation.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.segmentation.core.types import (
    SegmentationInput,
    SegPrediction,
)
from nectar.ai.segmentation.datasets.format import SegFormatConverter

logger = logging.getLogger(__name__)


class TransformersSegModel(BaseSegmentationModel):
    """
    HuggingFace Transformers segmentation model.

    Supports both instance segmentation (Mask2Former, MaskFormer) and
    semantic segmentation (SegFormer, SegGPT, etc.).

    The mode is auto-detected from the model configuration.

    Parameters
    ----------
    model_name : str
        Model name or HuggingFace model ID.
    mode : str, optional
        Segmentation mode ('instance' or 'semantic'). Auto-detected if not given.
    from_scratch : bool
        Train from scratch.
    """

    def __init__(
        self,
        model_name: str = "facebook/mask2former-swin-large-cityscapes-instance",
        mode: Optional[str] = None,
        from_scratch: bool = False,
    ):
        super().__init__(model_name, "transformers")

        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers is required. Install: pip install transformers")

        self.model = None
        self.processor = None
        self.from_scratch = from_scratch
        self._mode = mode  # "instance", "semantic", or None (auto-detect)

    @property
    def mode(self) -> str:
        """Segmentation mode: 'instance' or 'semantic'."""
        if self._mode:
            return self._mode
        return self._detect_mode(self.model_name)

    @staticmethod
    def _detect_mode(model_name: str) -> str:
        """Detect segmentation mode from model name or config."""
        name_lower = model_name.lower()
        instance_keywords = ["mask2former", "maskformer", "instance"]
        if any(kw in name_lower for kw in instance_keywords):
            return "instance"
        return "semantic"

    def load_model(
        self,
        model_path: Optional[str] = None,
        id2label: Optional[Dict[int, str]] = None,
        label2id: Optional[Dict[str, int]] = None,
        imgsz: int = 640,
    ) -> None:
        """Load segmentation model from path or HuggingFace Hub."""
        path = model_path or self.model_name

        self.processor = AutoImageProcessor.from_pretrained(path, use_fast=True)

        model_kwargs = {"ignore_mismatched_sizes": True}
        if id2label and label2id:
            model_kwargs["id2label"] = id2label
            model_kwargs["label2id"] = label2id
            self.class_names = id2label

        mode = self._mode or self._detect_mode(path)
        self._mode = mode

        if mode == "instance":
            model_cls = AutoModelForInstanceSegmentation
        else:
            model_cls = AutoModelForSemanticSegmentation

        if self.from_scratch:
            config = AutoConfig.from_pretrained(path)
            if id2label and label2id:
                config.id2label = id2label
                config.label2id = label2id
                config.num_labels = len(id2label)
            self.model = model_cls.from_config(config)
        else:
            self.model = model_cls.from_pretrained(path, **model_kwargs)

        if not id2label and hasattr(self.model.config, "id2label"):
            self.class_names = {
                int(k) if isinstance(k, str) else k: v
                for k, v in self.model.config.id2label.items()
            }

        self.logger.info("Loaded %s segmentation model: %s", mode, path)

    def _predict_single(self, seg_input: SegmentationInput) -> SegPrediction:
        """Run segmentation inference on a single image."""
        if self.model is None:
            raise ModelNotLoadedError()

        device = get_device(seg_input.device)
        self.model.to(device)
        self.model.eval()

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

        inputs = self.processor(images=pil_image, return_tensors="pt").to(device)

        start_time = time.time()
        with torch.no_grad():
            outputs = self.model(**inputs)
        inference_time = time.time() - start_time

        if self._mode == "instance":
            return self._process_instance_output(
                outputs, pil_image, inference_time, image_path, seg_input.conf_threshold
            )
        else:
            return self._process_semantic_output(outputs, pil_image, inference_time, image_path)

    def _process_instance_output(
        self,
        outputs,
        pil_image: Image.Image,
        inference_time: float,
        image_path: str,
        conf_threshold: float,
    ) -> SegPrediction:
        """Process instance segmentation output (Mask2Former-style)."""
        target_sizes = [pil_image.size[::-1]]
        results = self.processor.post_process_instance_segmentation(
            outputs, target_sizes=target_sizes, threshold=conf_threshold
        )[0]

        segments_info = results["segments_info"]
        segmentation_map = results["segmentation"].cpu().numpy()

        if not segments_info:
            empty = sv.Detections.empty() if sv else None
            return SegPrediction.from_detections(
                detections=empty,
                class_names=self.class_names,
                inference_time=inference_time,
                image_path=image_path,
                model_name=self.model_name,
            )

        xyxy_list = []
        confidence_list = []
        class_id_list = []
        mask_list = []

        for seg_info in segments_info:
            seg_id = seg_info["id"]
            label_id = seg_info["label_id"]
            score = seg_info["score"]

            binary_mask = (segmentation_map == seg_id).astype(np.uint8)

            ys, xs = np.where(binary_mask > 0)
            if len(xs) == 0:
                continue

            x1, y1, x2, y2 = xs.min(), ys.min(), xs.max(), ys.max()
            xyxy_list.append([x1, y1, x2, y2])
            confidence_list.append(score)
            class_id_list.append(label_id)
            mask_list.append(binary_mask.astype(bool))

        if not xyxy_list:
            empty = sv.Detections.empty() if sv else None
            return SegPrediction.from_detections(
                detections=empty,
                class_names=self.class_names,
                inference_time=inference_time,
                image_path=image_path,
                model_name=self.model_name,
            )

        detections = sv.Detections(
            xyxy=np.array(xyxy_list, dtype=np.float32),
            confidence=np.array(confidence_list, dtype=np.float32),
            class_id=np.array(class_id_list, dtype=int),
            mask=np.array(mask_list),
        )

        return SegPrediction.from_detections(
            detections=detections,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def _process_semantic_output(
        self,
        outputs,
        pil_image: Image.Image,
        inference_time: float,
        image_path: str,
    ) -> SegPrediction:
        """Process semantic segmentation output (SegFormer-style)."""
        logits = outputs.logits.cpu()
        upsampled = nn.functional.interpolate(
            logits,
            size=pil_image.size[::-1],
            mode="bilinear",
            align_corners=False,
        )
        semantic_map = upsampled.argmax(dim=1)[0].numpy()

        return SegPrediction.from_semantic(
            semantic_map=semantic_map,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def train(self, config: SegTrainingConfig) -> Dict[str, Any]:
        """Train segmentation model using HuggingFace Trainer."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_name = output_dir.name

        if self._mode == "semantic":
            return self._train_semantic(config, output_dir, run_name)
        return self._train_instance(config, output_dir, run_name)

    def _train_instance(
        self, config: SegTrainingConfig, output_dir: Path, run_name: str
    ) -> Dict[str, Any]:
        """Train instance segmentation model (Mask2Former)."""
        detector = FormatDetector(config.dataset_path)
        detected_format = detector.detect()

        if detected_format != "coco":
            converted_dir = output_dir / "datasets" / "converted"
            if not (converted_dir / "train" / "_annotations.coco.json").exists():
                converter = SegFormatConverter(
                    config.dataset_path, str(converted_dir), verbose=True
                )
                converter.convert(target_format="coco", copy_images=False)
            config.dataset_path = str(converted_dir)

        train_dataset, val_dataset, id2label, label2id = self._load_coco_dataset(config)

        imgsz = config.imgsz if config.imgsz else 640
        self.load_model(self.model_name, id2label=id2label, label2id=label2id, imgsz=imgsz)

        callbacks = self._setup_callbacks(config)

        if hasattr(config, "to_training_args"):
            args_dict = config.to_training_args()
            args_dict["output_dir"] = str(output_dir / run_name)
            args_dict["run_name"] = run_name
            training_args = TrainingArguments(**args_dict)
        else:
            training_args = TrainingArguments(
                output_dir=str(output_dir / run_name),
                num_train_epochs=config.epochs,
                per_device_train_batch_size=config.batch_size,
                per_device_eval_batch_size=config.batch_size,
                gradient_accumulation_steps=config.gradient_accumulation_steps,
                learning_rate=config.learning_rate,
                eval_strategy="epoch",
                save_strategy="epoch",
                save_total_limit=3,
                load_best_model_at_end=True,
                seed=config.seed,
                report_to=["tensorboard"] if config.tensorboard else None,
                run_name=run_name,
                fp16=(config.mixed_precision == "fp16"),
                bf16=(config.mixed_precision == "bf16"),
                remove_unused_columns=False,
                push_to_hub=config.push_to_hub,
                hub_model_id=config.hub_model_id if config.push_to_hub else None,
                hub_strategy="every_save" if config.push_to_hub else None,
                hub_private_repo=True,
            )

        from nectar.ai.detection.models.dataset import collate_fn

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            processing_class=self.processor,
            data_collator=collate_fn,
            callbacks=callbacks,
        )

        try:
            train_result = trainer.train()
            trainer.save_model()
            trainer.save_state()
            metrics = {}
            if hasattr(train_result, "metrics"):
                metrics = dict(train_result.metrics)
            return {"model_path": str(output_dir / run_name), "metrics": metrics}
        except Exception as e:
            raise TrainingError(str(e)) from e

    def _train_semantic(
        self, config: SegTrainingConfig, output_dir: Path, run_name: str
    ) -> Dict[str, Any]:
        """Train semantic segmentation model (SegFormer)."""
        try:
            from datasets import load_dataset as hf_load_dataset
        except ImportError:
            raise ImportError(
                "datasets library is required for semantic segmentation training. "
                "Install: pip install datasets"
            )

        dataset_path = config.dataset_path
        if Path(dataset_path).is_dir():
            ds = hf_load_dataset("imagefolder", data_dir=dataset_path)
        else:
            ds = hf_load_dataset(dataset_path)

        if "validation" not in ds and "test" in ds:
            ds["validation"] = ds["test"]
        elif "validation" not in ds:
            split = ds["train"].train_test_split(test_size=config.val_split, seed=config.seed)
            ds["train"] = split["train"]
            ds["validation"] = split["test"]

        id2label = {}
        label2id = {}
        if hasattr(ds["train"].features.get("label", None), "names"):
            names = ds["train"].features["label"].names
            id2label = {i: n for i, n in enumerate(names)}
            label2id = {n: i for i, n in enumerate(names)}

        self.load_model(self.model_name, id2label=id2label or None, label2id=label2id or None)

        processor = self.processor

        def train_transforms(batch):
            images = [x for x in batch["image"]]
            labels = [x for x in batch.get("annotation", batch.get("label", []))]
            return processor(images, labels)

        def val_transforms(batch):
            images = [x for x in batch["image"]]
            labels = [x for x in batch.get("annotation", batch.get("label", []))]
            return processor(images, labels)

        ds["train"].set_transform(train_transforms)
        ds["validation"].set_transform(val_transforms)

        callbacks = self._setup_callbacks(config)

        training_args = TrainingArguments(
            output_dir=str(output_dir / run_name),
            num_train_epochs=config.epochs,
            per_device_train_batch_size=config.batch_size,
            per_device_eval_batch_size=config.batch_size,
            learning_rate=config.learning_rate,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=3,
            load_best_model_at_end=True,
            seed=config.seed,
            report_to=["tensorboard"] if config.tensorboard else None,
            run_name=run_name,
            fp16=(config.mixed_precision == "fp16"),
            remove_unused_columns=False,
            push_to_hub=config.push_to_hub,
            hub_model_id=config.hub_model_id if config.push_to_hub else None,
            hub_strategy="every_save" if config.push_to_hub else None,
            hub_private_repo=True,
        )

        num_labels = len(id2label) if id2label else len(self.class_names)

        def compute_metrics(eval_pred):
            with torch.no_grad():
                logits, labels = eval_pred
                logits_tensor = torch.from_numpy(logits)
                upsampled = nn.functional.interpolate(
                    logits_tensor,
                    size=labels.shape[-2:],
                    mode="bilinear",
                    align_corners=False,
                ).argmax(dim=1)
                pred = upsampled.numpy()

                intersection = np.zeros(num_labels)
                union = np.zeros(num_labels)
                correct = 0
                total = 0

                for p, gt in zip(pred, labels):
                    valid = gt != 255
                    correct += np.sum((p == gt) & valid)
                    total += np.sum(valid)
                    for cls_id in range(num_labels):
                        pred_mask = (p == cls_id) & valid
                        label_mask = (gt == cls_id) & valid
                        intersection[cls_id] += np.sum(pred_mask & label_mask)
                        union[cls_id] += np.sum(pred_mask | label_mask)

                iou_per_class = np.where(union > 0, intersection / union, 0.0)
                mean_iou = float(np.mean(iou_per_class[union > 0])) if np.any(union > 0) else 0.0
                pixel_acc = float(correct / total) if total > 0 else 0.0

                return {"mean_iou": mean_iou, "pixel_accuracy": pixel_acc}

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=ds["train"],
            eval_dataset=ds["validation"],
            compute_metrics=compute_metrics,
            callbacks=callbacks,
        )

        try:
            train_result = trainer.train()
            trainer.save_model()
            trainer.save_state()
            metrics = {}
            if hasattr(train_result, "metrics"):
                metrics = dict(train_result.metrics)
            return {"model_path": str(output_dir / run_name), "metrics": metrics}
        except Exception as e:
            raise TrainingError(str(e)) from e

    def _load_coco_dataset(self, config: SegTrainingConfig):
        """Load COCO format dataset for instance segmentation training."""
        from nectar.ai.detection.models.dataset import CocoDetectionDataset

        dataset_path = Path(config.dataset_path)

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
                f"Dataset not in expected COCO format at {train_dir}. "
                "Expected train/_annotations.coco.json"
            )

        if not val_dir.exists() or not val_annotations.exists():
            val_dir = train_dir
            val_annotations = train_annotations

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

    def _setup_callbacks(self, config: SegTrainingConfig) -> List:
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
        return callbacks

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
