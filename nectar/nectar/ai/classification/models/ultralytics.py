"""Ultralytics YOLO classification model implementation."""

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
    from ultralytics import YOLO
    from ultralytics import settings as ultralytics_settings
except ImportError:
    YOLO = None
    ultralytics_settings = None

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


class UltralyticsClsModel(BaseClassificationModel):
    """
    Ultralytics YOLO classification model wrapper.

    Supports YOLO-cls models (e.g. yolo26n-cls.pt, yolov8n-cls.pt).

    Parameters
    ----------
    model_name : str
        Model name or path (e.g., 'yolo26n-cls.pt').
    from_scratch : bool
        Train from scratch without pretrained weights.
    """

    def __init__(self, model_name: str = "yolo26n-cls.pt", from_scratch: bool = False):
        super().__init__(model_name, "ultralytics")
        if YOLO is None:
            raise ImportError("ultralytics is required. Install: pip install ultralytics")

        self.model: Optional[YOLO] = None
        self.from_scratch = from_scratch
        self._actual_save_dir: Optional[Path] = None

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load YOLO classification model."""
        from nectar.ai.core.model_loader import ModelLoader

        path = model_path or self.model_name

        if "/" in path and not Path(path).exists():
            # Hub refs use ``org/repo:file.pt``; bare ``org/repo`` defaults to best.pt
            hub_ref = path if ":" in path else f"{path}:weights/best.pt"
            path = ModelLoader.load(hub_ref)
            self.logger.info("Downloaded model to: %s", path)

        if self.from_scratch and not path.endswith(".pt"):
            yaml_path = path.replace(".pt", ".yaml")
            self.model = YOLO(yaml_path)
        else:
            self.model = YOLO(path)

        if hasattr(self.model, "names") and self.model.names:
            self.class_names = {int(i): name for i, name in self.model.names.items()}
            self.logger.info("Loaded %d classes", len(self.class_names))

    def _predict_single(self, cls_input: ClassificationInput) -> ClsPrediction:
        """Run classification inference on a single image."""
        if self.model is None:
            raise ModelNotLoadedError()

        image = cls_input.image
        device = get_device(cls_input.device)

        if isinstance(image, (str, Path)):
            source = str(image)
            image_path = source
        elif isinstance(image, np.ndarray):
            source = image
            image_path = "array"
        elif isinstance(image, Image.Image):
            source = image
            image_path = "pil"
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")

        predict_kwargs: Dict[str, Any] = {
            "source": source,
            "device": device,
            "save": False,
            "verbose": False,
        }
        if cls_input.imgsz is not None:
            predict_kwargs["imgsz"] = cls_input.imgsz

        start_time = time.time()
        results = self.model.predict(**predict_kwargs)
        inference_time = time.time() - start_time

        if not results or results[0].probs is None:
            result = ClassificationResult(
                inference_time=inference_time,
                image_path=image_path,
                model_name=self.model_name,
            )
        else:
            probs_obj = results[0].probs
            probs = (
                probs_obj.data.cpu().numpy()
                if hasattr(probs_obj.data, "cpu")
                else np.asarray(probs_obj.data)
            )
            if hasattr(results[0], "names") and results[0].names:
                self.class_names = {int(i): name for i, name in results[0].names.items()}
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

    def _prepare_dataset_path(self, config: ClsTrainingConfig) -> str:
        """Resolve ImageFolder root for Ultralytics classification training."""
        dataset_path = Path(config.dataset_path)
        if not dataset_path.exists():
            # Built-in Ultralytics dataset name (e.g. mnist160)
            return str(config.dataset_path)

        for split in ("train", "val", "valid", "test"):
            if (dataset_path / split).is_dir():
                return str(dataset_path)

        # Already pointing at a split that contains class folders
        if any(p.is_dir() for p in dataset_path.iterdir()):
            return str(dataset_path)

        return str(dataset_path)

    def train(self, config: ClsTrainingConfig) -> Dict[str, Any]:
        """Train YOLO classification model."""
        if self.model is None:
            self.load_model()

        output_dir = Path(config.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        config.dataset_path = self._prepare_dataset_path(config)

        if ultralytics_settings:
            ultralytics_settings.update({"tensorboard": config.tensorboard})

        if hasattr(config, "to_ultralytics_args"):
            train_args = config.to_ultralytics_args()
            train_args["project"] = str(output_dir.parent)
            train_args["name"] = output_dir.name
        else:
            train_args = {
                "data": config.dataset_path,
                "epochs": config.epochs,
                "batch": config.batch_size,
                "imgsz": config.imgsz if config.imgsz is not None else 224,
                "save": True,
                "project": str(output_dir.parent),
                "name": output_dir.name,
                "exist_ok": True,
                "lr0": float(config.learning_rate),
                "seed": config.seed,
                "deterministic": True,
                "val": True,
                "plots": config.tensorboard,
                "save_period": config.save_period,
                "patience": config.early_stopping_patience or 0,
                "pretrained": not config.from_scratch,
            }

        if config.multi_gpu and torch and torch.cuda.is_available():
            if torch.cuda.device_count() > 1:
                train_args["device"] = list(range(torch.cuda.device_count()))

        if config.mixed_precision == "fp16":
            train_args["amp"] = True

        self._setup_callbacks(config, output_dir)

        try:
            results = self.model.train(**train_args)
            metrics = self._extract_metrics(results)
            model_path = self._find_best_model(output_dir)
            if hasattr(self.model, "names") and self.model.names:
                self.class_names = {int(i): name for i, name in self.model.names.items()}
            return {"model_path": str(model_path), "metrics": metrics}
        except Exception as e:
            raise TrainingError(str(e)) from e

    def _setup_callbacks(self, config: ClsTrainingConfig, output_dir: Path) -> None:
        """Setup training callbacks for HF upload, GC, and save-dir tracking."""
        from nectar.ai.core.utils.callbacks import (
            setup_ultralytics_gc_callback,
            setup_ultralytics_hf_callbacks,
        )

        def on_train_start(trainer):
            self._actual_save_dir = Path(trainer.save_dir)

        self.model.add_callback("on_train_start", on_train_start)

        if config.push_to_hub and config.hub_model_id:
            setup_ultralytics_hf_callbacks(self.model, config.hub_model_id, output_dir, self.logger)

        if getattr(config, "gc_per_accumulation", True):
            setup_ultralytics_gc_callback(self.model, config.gradient_accumulation_steps)

    def _extract_metrics(self, results) -> Dict[str, Any]:
        """Extract classification metrics from training results."""
        metrics: Dict[str, Any] = {}
        if hasattr(results, "results_dict"):
            rd = results.results_dict
            metrics["top1_accuracy"] = rd.get("metrics/accuracy_top1", rd.get("top1", 0.0))
            metrics["top5_accuracy"] = rd.get("metrics/accuracy_top5", rd.get("top5", 0.0))
        elif results is not None:
            metrics["top1_accuracy"] = getattr(results, "top1", 0.0)
            metrics["top5_accuracy"] = getattr(results, "top5", 0.0)
        return metrics

    def _find_best_model(self, output_dir: Path) -> Path:
        """Find best model checkpoint."""
        if self._actual_save_dir and self._actual_save_dir.exists():
            best_path = self._actual_save_dir / "weights" / "best.pt"
            if best_path.exists():
                return best_path

        if output_dir.exists():
            runs = sorted(
                [d for d in output_dir.iterdir() if d.is_dir()],
                key=os.path.getmtime,
            )
            for run in reversed(runs):
                best_path = run / "weights" / "best.pt"
                if best_path.exists():
                    return best_path

        potential_paths = [
            output_dir / "weights" / "best.pt",
            output_dir / "train" / "weights" / "best.pt",
        ]
        for path in potential_paths:
            if path.exists():
                return path

        raise TrainingError(
            f"No trained model found. Searched in: {output_dir}, {self._actual_save_dir}"
        )

    def save(self, save_path: str) -> str:
        """Save model to path."""
        if self.model is None:
            raise ModelNotLoadedError()

        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        model_path = save_dir / f"{Path(self.model_name).stem}_saved.pt"
        self.model.save(str(model_path))
        return str(model_path)
