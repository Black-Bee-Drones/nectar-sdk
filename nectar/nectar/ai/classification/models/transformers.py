"""HuggingFace Transformers classification model implementation."""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
except ImportError:
    torch = None

try:
    from transformers import (
        AutoConfig,
        AutoImageProcessor,
        AutoModelForImageClassification,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from PIL import Image

from nectar.ai.classification.core.base import BaseClassificationModel
from nectar.ai.classification.core.configs import ClsTrainingConfig
from nectar.ai.classification.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.classification.core.types import (
    ClassificationInput,
    ClassificationResult,
    ClsPrediction,
)
from nectar.ai.core.utils.device import get_device

logger = logging.getLogger(__name__)


class TransformersClsModel(BaseClassificationModel):
    """
    HuggingFace Transformers image classification model.

    Uses AutoModelForImageClassification + AutoImageProcessor (ViT, BEiT, etc.).

    Parameters
    ----------
    model_name : str
        HuggingFace model ID (e.g. 'google/vit-base-patch16-224-in21k').
    from_scratch : bool
        Initialize from config without pretrained weights.
    """

    def __init__(
        self,
        model_name: str = "google/vit-base-patch16-224-in21k",
        from_scratch: bool = False,
    ):
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
        imgsz: int = 224,
    ) -> None:
        """Load model and image processor from path or Hub."""
        path = model_path or self.model_name

        self.processor = AutoImageProcessor.from_pretrained(path, use_fast=True)

        model_kwargs: Dict[str, Any] = {"ignore_mismatched_sizes": True}
        if id2label and label2id:
            model_kwargs["id2label"] = {int(k): v for k, v in id2label.items()}
            model_kwargs["label2id"] = label2id
            model_kwargs["num_labels"] = len(id2label)
            self.class_names = {int(k): v for k, v in id2label.items()}

        if self.from_scratch:
            config = AutoConfig.from_pretrained(path)
            if id2label and label2id:
                config.id2label = {int(k): v for k, v in id2label.items()}
                config.label2id = label2id
                config.num_labels = len(id2label)
            self.model = AutoModelForImageClassification.from_config(config)
        else:
            self.model = AutoModelForImageClassification.from_pretrained(path, **model_kwargs)

        if not id2label and hasattr(self.model.config, "id2label"):
            self.class_names = {int(k): v for k, v in self.model.config.id2label.items()}
            self.logger.info("Using model's %d classes", len(self.class_names))

    def _to_pil(self, image) -> Tuple[Image.Image, str]:
        if isinstance(image, (str, Path)):
            image_path = str(image)
            pil_image = Image.open(image_path).convert("RGB")
        elif isinstance(image, np.ndarray):
            image_path = "array"
            arr = image
            if arr.ndim == 3 and arr.shape[2] == 3:
                arr = np.ascontiguousarray(arr[..., ::-1])
            pil_image = Image.fromarray(arr).convert("RGB")
        elif isinstance(image, Image.Image):
            image_path = "pil"
            pil_image = image.convert("RGB")
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
        return pil_image, image_path

    def _predict_single(self, cls_input: ClassificationInput) -> ClsPrediction:
        """Run inference on a single image."""
        if self.model is None or self.processor is None:
            raise ModelNotLoadedError()

        device = get_device(cls_input.device)
        self.model.to(device)
        self.model.eval()

        pil_image, image_path = self._to_pil(cls_input.image)
        inputs = self.processor(images=pil_image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}

        start_time = time.time()
        with torch.no_grad():
            logits = self.model(**inputs).logits
        inference_time = time.time() - start_time

        probs = torch.nn.functional.softmax(logits, dim=-1)[0].cpu().numpy()
        result = ClassificationResult.from_probs(
            probs=probs,
            class_names=self.class_names,
            topk=cls_input.topk,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )
        return ClsPrediction.from_result(
            result=result,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def train(self, config: ClsTrainingConfig) -> Dict[str, Any]:
        """Train using HuggingFace Trainer (official image-classification flow)."""
        output_dir = Path(config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        run_name = output_dir.name

        train_ds, val_ds, id2label, label2id = self._load_datasets(config)
        imgsz = config.imgsz if isinstance(config.imgsz, int) else 224
        self.load_model(self.model_name, id2label=id2label, label2id=label2id, imgsz=imgsz)

        train_ds = self._with_transforms(train_ds, augment=True)
        val_ds = self._with_transforms(val_ds, augment=False) if val_ds is not None else None

        callbacks = []
        if config.early_stopping_patience:
            callbacks.append(
                EarlyStoppingCallback(
                    early_stopping_patience=config.early_stopping_patience,
                    early_stopping_threshold=config.early_stopping_delta,
                )
            )

        if config.push_to_hub and config.hub_model_id:
            from nectar.ai.core.utils.callbacks import get_hf_upload_transformers_callback

            callbacks.append(
                get_hf_upload_transformers_callback(config.hub_model_id, output_dir, self.logger)
            )

        if hasattr(config, "to_training_args"):
            args_dict = config.to_training_args()
            args_dict["output_dir"] = str(output_dir / run_name)
            args_dict["run_name"] = run_name
            args_dict["logging_dir"] = (
                str(output_dir / run_name / "logs") if config.tensorboard else None
            )
            training_args = TrainingArguments(**args_dict)
        else:
            training_args = TrainingArguments(
                output_dir=str(output_dir / run_name),
                num_train_epochs=config.epochs,
                per_device_train_batch_size=config.batch_size,
                per_device_eval_batch_size=config.batch_size,
                learning_rate=config.learning_rate,
                eval_strategy="epoch",
                save_strategy="epoch",
                load_best_model_at_end=True,
                metric_for_best_model="accuracy",
                greater_is_better=True,
                remove_unused_columns=False,
                seed=config.seed,
                report_to=["tensorboard"] if config.tensorboard else None,
                fp16=config.mixed_precision == "fp16",
                bf16=config.mixed_precision == "bf16",
            )

        def compute_metrics(eval_pred):
            predictions, labels = eval_pred
            preds = np.argmax(predictions, axis=1)
            accuracy = float((preds == labels).mean()) if len(labels) else 0.0
            return {"accuracy": accuracy}

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            processing_class=self.processor,
            data_collator=self._collate_fn,
            compute_metrics=compute_metrics,
            callbacks=callbacks or None,
        )

        try:
            train_result = trainer.train()
            trainer.save_model()
            trainer.save_state()
            if self.processor is not None:
                self.processor.save_pretrained(str(output_dir / run_name))

            metrics = {
                "train_loss": float(train_result.training_loss)
                if hasattr(train_result, "training_loss")
                else 0.0,
            }
            if val_ds is not None:
                eval_metrics = trainer.evaluate()
                metrics["top1_accuracy"] = float(eval_metrics.get("eval_accuracy", 0.0))

            return {"model_path": str(output_dir / run_name), "metrics": metrics}
        except Exception as e:
            raise TrainingError(str(e)) from e

    def _load_datasets(self, config: ClsTrainingConfig):
        """Load ImageFolder or HF dataset into train/val splits with ClassLabel."""
        from nectar.ai.classification.datasets.format import ImageFolderDetector
        from nectar.ai.classification.datasets.hf_converter import imagefolder_to_hf

        dataset_path = Path(config.dataset_path)
        if ImageFolderDetector(str(dataset_path)).is_imagefolder():
            ds_dict = imagefolder_to_hf(str(dataset_path))
        else:
            from datasets import load_dataset

            loaded = load_dataset(str(dataset_path))
            ds_dict = loaded if hasattr(loaded, "keys") else {"train": loaded}

        if "train" not in ds_dict:
            first_key = next(iter(ds_dict.keys()))
            ds_dict = ds_dict[first_key].train_test_split(
                test_size=config.val_split, seed=config.seed
            )
            train_ds = ds_dict["train"]
            val_ds = ds_dict["test"]
        else:
            train_ds = ds_dict["train"]
            val_ds = ds_dict.get("validation") or ds_dict.get("val") or ds_dict.get("test")
            if val_ds is None and config.val_split > 0:
                split = train_ds.train_test_split(test_size=config.val_split, seed=config.seed)
                train_ds, val_ds = split["train"], split["test"]

        if config.max_train_samples is not None:
            n = min(config.max_train_samples, len(train_ds))
            train_ds = train_ds.select(range(n))
        if val_ds is not None and config.max_eval_samples is not None:
            n = min(config.max_eval_samples, len(val_ds))
            val_ds = val_ds.select(range(n))

        labels = train_ds.features["label"].names
        id2label = {i: name for i, name in enumerate(labels)}
        label2id = {name: i for i, name in enumerate(labels)}
        return train_ds, val_ds, id2label, label2id

    def _with_transforms(self, dataset, augment: bool):
        """Apply torchvision transforms on the fly"""
        if dataset is None or self.processor is None:
            return dataset

        try:
            from torchvision.transforms import (
                Compose,
                Normalize,
                RandomHorizontalFlip,
                RandomResizedCrop,
                Resize,
                ToTensor,
            )
        except ImportError as e:
            raise ImportError("torchvision is required for TransformersClsModel training") from e

        image_mean = getattr(self.processor, "image_mean", [0.5, 0.5, 0.5])
        image_std = getattr(self.processor, "image_std", [0.5, 0.5, 0.5])
        normalize = Normalize(mean=image_mean, std=image_std)

        size = getattr(self.processor, "size", None) or {}
        if isinstance(size, int):
            resize_size = size
        elif "shortest_edge" in size:
            resize_size = size["shortest_edge"]
        else:
            resize_size = (size.get("height", 224), size.get("width", 224))

        if augment:
            transforms = Compose(
                [
                    RandomResizedCrop(resize_size),
                    RandomHorizontalFlip(),
                    ToTensor(),
                    normalize,
                ]
            )
        else:
            transforms = Compose(
                [
                    Resize(resize_size if isinstance(resize_size, int) else resize_size),
                    ToTensor(),
                    normalize,
                ]
            )

        def _transform(examples):
            examples["pixel_values"] = [transforms(img.convert("RGB")) for img in examples["image"]]
            del examples["image"]
            return examples

        return dataset.with_transform(_transform)

    @staticmethod
    def _collate_fn(examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        pixel_values = torch.stack([ex["pixel_values"] for ex in examples])
        labels = torch.tensor([ex["label"] for ex in examples])
        return {"pixel_values": pixel_values, "labels": labels}

    def save(self, save_path: str) -> str:
        """Save model and processor with save_pretrained."""
        if self.model is None:
            raise ModelNotLoadedError()

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(save_dir))
        if self.processor is not None:
            self.processor.save_pretrained(str(save_dir))
        return str(save_dir)
