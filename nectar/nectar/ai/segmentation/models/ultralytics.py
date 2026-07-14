"""Ultralytics YOLO segmentation model implementation."""

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
    from ultralytics import YOLO
    from ultralytics import settings as ultralytics_settings
except ImportError:
    YOLO = None
    ultralytics_settings = None

from PIL import Image

from nectar.ai.core.utils.device import get_device
from nectar.ai.detection.datasets.format import FormatDetector
from nectar.ai.detection.datasets.subset import SubsetCreator
from nectar.ai.segmentation.core.base import BaseSegmentationModel
from nectar.ai.segmentation.core.configs import SegTrainingConfig
from nectar.ai.segmentation.core.exceptions import ModelNotLoadedError, TrainingError
from nectar.ai.segmentation.core.types import SegmentationInput, SegPrediction
from nectar.ai.segmentation.datasets.format import SegFormatConverter

logger = logging.getLogger(__name__)


class UltralyticsSegModel(BaseSegmentationModel):
    """
    Ultralytics YOLO segmentation model wrapper.

    Supports YOLOv8-seg, YOLO11-seg, YOLO26-seg and other Ultralytics
    segmentation models.

    Parameters
    ----------
    model_name : str
        Model name or path (e.g., 'yolov8n-seg.pt').
    from_scratch : bool
        Train from scratch without pretrained weights.
    """

    def __init__(self, model_name: str = "yolov8n-seg.pt", from_scratch: bool = False):
        super().__init__(model_name, "ultralytics")
        if YOLO is None:
            raise ImportError("ultralytics is required. Install: pip install ultralytics")

        self.model: Optional[YOLO] = None
        self.from_scratch = from_scratch
        self._actual_save_dir: Optional[Path] = None

    def load_model(self, model_path: Optional[str] = None) -> None:
        """Load YOLO segmentation model."""
        path = model_path or self.model_name

        if "/" in path and not Path(path).exists():
            path = self._download_from_huggingface(path)

        if self.from_scratch and not path.endswith(".pt"):
            yaml_path = path.replace(".pt", ".yaml")
            self.model = YOLO(yaml_path)
        else:
            self.model = YOLO(path)

        if hasattr(self.model, "names"):
            self.class_names = {i: name for i, name in enumerate(self.model.names.values())}
            self.logger.info("Loaded %d classes", len(self.class_names))

    def _download_from_huggingface(self, model_path: str) -> str:
        """Download model from HuggingFace Hub."""
        from huggingface_hub import hf_hub_download

        repo_id = model_path.split(":")[0] if ":" in model_path else model_path
        filename = model_path.split(":")[-1] if ":" in model_path else "weights/best.pt"

        local_dir = Path(f"outputs/hf_models/{repo_id.replace('/', '_')}")
        local_dir.mkdir(parents=True, exist_ok=True)

        local_path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(local_dir))
        self.logger.info("Downloaded model to: %s", local_path)
        return local_path

    def _predict_single(self, seg_input: SegmentationInput) -> SegPrediction:
        """Run segmentation inference on a single image."""
        if self.model is None:
            raise ModelNotLoadedError()

        image = seg_input.image
        device = get_device(seg_input.device)

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

        predict_kwargs = {
            "source": source,
            "conf": seg_input.conf_threshold,
            "iou": seg_input.iou_threshold,
            "device": device,
            "save": False,
            "verbose": False,
        }
        if seg_input.imgsz is not None:
            predict_kwargs["imgsz"] = seg_input.imgsz

        start_time = time.time()
        results = self.model.predict(**predict_kwargs)
        inference_time = time.time() - start_time

        if results and len(results) > 0:
            detections = sv.Detections.from_ultralytics(results[0])
        else:
            detections = sv.Detections.empty()

        return SegPrediction.from_detections(
            detections=detections,
            class_names=self.class_names,
            inference_time=inference_time,
            image_path=image_path,
            model_name=self.model_name,
        )

    def _prepare_dataset_config(self, config: SegTrainingConfig) -> str:
        """Prepare dataset configuration, auto-detecting and converting format if needed."""
        dataset_path = Path(config.dataset_path)

        if dataset_path.suffix in (".yaml", ".yml") and dataset_path.exists():
            return str(dataset_path)

        detector = FormatDetector(str(dataset_path))
        detected_format = detector.detect()

        if detected_format == "unknown":
            self.logger.warning("Could not auto-detect format, assuming YOLO")
            detected_format = "yolo"

        if detected_format != "yolo":
            self.logger.info("Converting dataset from %s to yolo", detected_format)
            converted_dir = Path(config.output_dir) / "datasets" / "converted"
            converter = SegFormatConverter(str(dataset_path), str(converted_dir), verbose=True)
            yaml_path = converter.convert(target_format="yolo", copy_images=True)
            return yaml_path

        if (dataset_path / "data.yaml").exists():
            return str(dataset_path / "data.yaml")

        return str(dataset_path)

    def train(self, config: SegTrainingConfig) -> Dict[str, Any]:
        """Train YOLO segmentation model."""
        if self.model is None:
            self.load_model()

        output_dir = Path(config.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        prepared_dataset_path = self._prepare_dataset_config(config)
        config.dataset_path = prepared_dataset_path

        if config.max_train_samples is not None or config.max_eval_samples is not None:
            subset_output_dir = output_dir / "datasets" / "subset"
            dataset_dir = config.dataset_path
            if Path(dataset_dir).suffix in [".yaml", ".yml"]:
                dataset_dir = str(Path(dataset_dir).parent)
            subset_creator = SubsetCreator(
                dataset_dir,
                str(subset_output_dir),
                seed=config.seed,
                verbose=True,
            )
            subset_path = subset_creator.create(
                max_train_samples=config.max_train_samples,
                max_eval_samples=config.max_eval_samples,
                max_test_samples=config.max_test_samples,
            )
            if Path(config.dataset_path).suffix in [".yaml", ".yml"]:
                config.dataset_path = str(Path(subset_path) / "data.yaml")
            else:
                config.dataset_path = subset_path

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
                "imgsz": config.imgsz if config.imgsz is not None else 640,
                "save": True,
                "project": str(output_dir.parent),
                "name": output_dir.name,
                "exist_ok": True,
                "lr0": float(config.learning_rate),
                "seed": config.seed,
                "deterministic": True,
                "val": True,
                "weight_decay": float(config.weight_decay),
                "warmup_epochs": float(config.warmup_epochs),
                "warmup_momentum": float(config.warmup_momentum),
                "lrf": float(config.lrf),
                "cos_lr": bool(config.cos_lr),
                "dropout": float(config.dropout),
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
            return {"model_path": str(model_path), "metrics": metrics}
        except Exception as e:
            raise TrainingError(str(e)) from e

    def _setup_callbacks(self, config: SegTrainingConfig, output_dir: Path) -> None:
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
        """Extract metrics from training results."""
        metrics = {}
        if hasattr(results, "results_dict"):
            rd = results.results_dict
            metrics["map50_box"] = rd.get("metrics/mAP50(B)", 0.0)
            metrics["map50_95_box"] = rd.get("metrics/mAP50-95(B)", 0.0)
            metrics["map50_mask"] = rd.get("metrics/mAP50(M)", 0.0)
            metrics["map50_95_mask"] = rd.get("metrics/mAP50-95(M)", 0.0)
            metrics["precision"] = rd.get("metrics/precision(B)", 0.0)
            metrics["recall"] = rd.get("metrics/recall(B)", 0.0)
        return metrics

    def _find_best_model(self, output_dir: Path) -> Path:
        """Find best model checkpoint."""
        if self._actual_save_dir and self._actual_save_dir.exists():
            best_path = self._actual_save_dir / "weights" / "best.pt"
            if best_path.exists():
                return best_path

        if output_dir.exists():
            runs = sorted(
                [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("train")],
                key=os.path.getmtime,
            )
            if runs:
                best_path = runs[-1] / "weights" / "best.pt"
                if best_path.exists():
                    return best_path

        potential_paths = [
            output_dir / "train" / "weights" / "best.pt",
            output_dir / "weights" / "best.pt",
            output_dir.parent / "segment" / output_dir.name / "train" / "weights" / "best.pt",
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
        self.model.export(format="pt")
        return str(model_path)
